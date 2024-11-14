import json
import re
import sys
from typing import Any

from redis.commands.search.field import TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

from models.core import Meta, ACL, ActionType, ConditionType, Group, Permission, Role, User
from models.enums import ResourceType
from utils.database.create_tables import Users
from utils.helpers import camel_case, flatten_dict
from utils.settings import settings
from data_adapters.adapter import data_adapter as db
from utils.regex import FILE_PATTERN
from utils.redis_services import RedisServices


class AccessControl:
    permissions: dict[str, Permission] = {}
    groups: dict[str, Group] = {}
    roles: dict[str, Role] = {}
    users: dict[str, User] = {}

    async def load_permissions_and_roles(self) -> None:
        if settings.active_data_db == "file":
            management_path = settings.spaces_folder / settings.management_space

            management_modules: dict[str, type[Meta]] = {
                "groups": Group,
                "roles": Role,
                "permissions": Permission
            }

            for module_name, module_value in management_modules.items():
                self_module = getattr(self, module_name)
                self_module = {}
                path = management_path / module_name
                entries_glob = ".dm/*/meta.*.json"
                for one in path.glob(entries_glob):
                    match = FILE_PATTERN.search(str(one))
                    if not match or not one.is_file():
                        continue
                    shortname = match.group(1)
                    try:
                        resource_obj: Meta = await db.load(
                            settings.management_space,
                            module_name,
                            shortname,
                            module_value,
                            "anonymous",
                        )
                        if resource_obj.is_active:
                            self_module[shortname] = resource_obj  # store in redis doc
                    except Exception as ex:
                        # print(f"Error processing @{settings.management_space}/{module_name}/{shortname} ... ", ex)
                        raise ex

            await self.create_user_premission_index()
            await self.store_modules_to_redis()
            await self.delete_user_permissions_map_in_redis()

    async def create_user_premission_index(self) -> None:
        async with RedisServices() as redis_services:
            try:
                # Check if index already exist
                await redis_services.ft("user_permission").info()
            except Exception:
                await redis_services.ft("user_permission").create_index(
                    fields=[TextField("name")],
                    definition=IndexDefinition(
                        prefix=["users_permissions"],
                        index_type=IndexType.JSON,
                    )
                )

    async def store_modules_to_redis(self) -> None:
        modules = [
            "roles",
            "groups",
            "permissions",
        ]
        async with RedisServices() as redis_services:
            for module_name in modules:
                class_var = getattr(self, module_name)
                for _, object in class_var.items():
                    await redis_services.save_meta_doc(
                        space_name=settings.management_space,
                        subpath=module_name,
                        meta=object,
                    )

    async def delete_user_permissions_map_in_redis(self) -> None:
        async with RedisServices() as redis_services:
            search_query = Query("*").no_content()
            redis_res = await redis_services.ft("user_permission").search(search_query)
            if redis_res and isinstance(redis_res, dict) and "results" in redis_res:
                results = redis_res["results"]
                keys = [doc["id"] for doc in results]
                if len(keys) > 0:
                    await redis_services.del_keys(keys)

    def generate_user_permission_doc_id(self, user_shortname: str):
        return f"users_permissions_{user_shortname}"

    async def is_user_verified(self, user_shortname: str | None, identifier: str | None):
        async with RedisServices() as redis_services:
            user: dict = await redis_services.get_doc_by_id(f"management:master:meta:users/{user_shortname}")
            if identifier == "msisdn":
                return user.get("is_msisdn_verified", True)
            if identifier == "email":
                return user.get("is_email_verified", True)
            return False

    async def get_user_permissions(self, user_shortname: str) -> dict:
        # file: fetch from op if not found
        #       get from files then save it in op db
        # sql: fetch directly thought db
        if settings.active_data_db == "file":
            async with RedisServices() as redis_services:
                user_permissions: dict = await redis_services.get_doc_by_id(
                    self.generate_user_permission_doc_id(user_shortname)
                )

                if not user_permissions:
                    return await self.generate_user_permissions(user_shortname)

                return user_permissions
        else:
            return await self.generate_user_permissions(user_shortname)


    async def check_access(
            self,
            user_shortname: str,
            space_name: str,
            subpath: str,
            resource_type: ResourceType,
            action_type: ActionType,
            resource_is_active: bool = False,
            resource_owner_shortname: str | None = None,
            resource_owner_group: str | None = None,
            record_attributes: dict = {},
            entry_shortname: str | None = None
    ):
        # print("Checking access for", user_shortname, space_name, subpath, resource_type, action_type)
        if resource_type == ResourceType.space and entry_shortname:
            return await self.check_space_access(
                user_shortname,
                entry_shortname
            )
        # print("Checking check_space_access access")
        user_permissions = await self.get_user_permissions(user_shortname)

        user_groups = (await self.load_user_meta(user_shortname)).groups or []

        # Generate set of achevied conditions on the resource
        # ex: {"is_active", "own"}
        resource_achieved_conditions: set[ConditionType] = set()
        if resource_is_active:
            resource_achieved_conditions.add(ConditionType.is_active)
        if resource_owner_shortname == user_shortname or resource_owner_group in user_groups:
            resource_achieved_conditions.add(ConditionType.own)

        # Allow checking for root permissions
        subpath_parts = ["/"]
        subpath_parts += list(filter(None, subpath.strip("/").split("/")))
        if resource_type == ResourceType.folder and entry_shortname:
            subpath_parts.append(entry_shortname)

        search_subpath = ""
        for subpath_part in subpath_parts:
            search_subpath += subpath_part
            # Check if the user has global access
            global_access = self.has_global_access(
                space_name,
                user_permissions,
                search_subpath,
                action_type,
                resource_type,
                resource_achieved_conditions,
                record_attributes
            )
            if global_access:
                return True

            permission_key = f"{space_name}:{search_subpath}:{resource_type}"
            if (
                permission_key in user_permissions
                and action_type in user_permissions[permission_key]["allowed_actions"]
                and self.check_access_conditions(
                    set(user_permissions[permission_key]["conditions"]),
                    set(resource_achieved_conditions),
                    action_type,
                )
                and self.check_access_restriction(
                    user_permissions[permission_key]["restricted_fields"],
                    user_permissions[permission_key]["allowed_fields_values"],
                    action_type,
                    record_attributes
                )
            ):
                return True

            if search_subpath == "/":
                search_subpath = ""
            else:
                search_subpath += "/"

        return False

    async def check_access_control_list(
            self,
            space_name: str,
            subpath: str,
            resource_type: ResourceType,
            entry_shortname: str,
            action_type: ActionType,
            user_shortname: str,
    ) -> bool:
        resource_cls = getattr(
            sys.modules["models.core"], camel_case(resource_type)
        )
        entry = await db.load(
            space_name=space_name,
            subpath=subpath,
            shortname=entry_shortname,
            class_type=resource_cls
        )
        if not entry.acl:
            return False

        user_acl: ACL | None = None
        for access in entry.acl:
            if access.user_shortname == user_shortname:
                user_acl = access
                break

        if not user_acl:
            return False

        return action_type in user_acl.allowed_actions

    def has_global_access(
            self,
            space_name: str,
            user_permissions: dict,
            search_subpath: str,
            action_type: ActionType,
            resource_type: str,
            resource_achieved_conditions: set,
            record_attributes: dict
    ) -> bool:
        """
        check if has access to global subpath by replacing the following
        subpath = / => __all_subpaths__
        subpath = {subpath} => __all_subpaths__
        subpath = {subpath}/protected => __all_subpaths__/protected
        subpath = {subpath}/protected/mine => {subpath}/__all_subpaths__/mine
        """
        original_subpath = search_subpath
        search_subpath_parts = search_subpath.split("/")
        if len(search_subpath_parts) > 1:
            search_subpath_parts[-2] = settings.all_subpaths_mw
            search_subpath = "/".join(search_subpath_parts)
        elif len(search_subpath_parts) == 1:
            search_subpath = settings.all_subpaths_mw
        if search_subpath[-1] == "/" and len(search_subpath) > 1:
            search_subpath = search_subpath[:-1]

        permission_key = None
        # check if has access to all spaces
        if f"{settings.all_spaces_mw}:{search_subpath}:{resource_type}" in user_permissions:
            permission_key = f"{settings.all_spaces_mw}:{search_subpath}:{resource_type}"

        # check if has access to current spaces
        if f"{space_name}:{search_subpath}:{resource_type}" in user_permissions:
            permission_key = f"{space_name}:{search_subpath}:{resource_type}"

        # check if has access to current subpath
        if f"{settings.all_spaces_mw}:{original_subpath}:{resource_type}" in user_permissions:
            permission_key = f"{settings.all_spaces_mw}:{original_subpath}:{resource_type}"

        if not permission_key:
            return False

        if (
                action_type in user_permissions[permission_key]["allowed_actions"]
                and self.check_access_conditions(
            set(user_permissions[permission_key]["conditions"]),
            set(resource_achieved_conditions),
            action_type,
        )
                and self.check_access_restriction(
            user_permissions[permission_key]["restricted_fields"],
            user_permissions[permission_key]["allowed_fields_values"],
            action_type,
            record_attributes
        )
        ):
            return True

        return False

    def check_access_conditions(
            self,
            premission_conditions: set,
            resource_achieved_conditions: set,
            action_type: ActionType,
    ):
        # actions of type query will be handled in the query function
        # actions of type create shouldn't check for permission conditions
        if action_type in [ActionType.create, ActionType.query]:
            return True

        return premission_conditions.issubset(resource_achieved_conditions)

    def check_access_restriction(
            self,
            restricted_fields: list,
            allowed_fields_values: dict,
            action_type: ActionType,
            record_attributes: dict
    ):
        """
        in case of create or update action, check access for the record fields
        via permission.restricted_fields and permission.allowed_fields_values
        """
        if action_type not in [ActionType.create, ActionType.update]:
            return True

        flattened_attributes = flatten_dict(record_attributes)

        for restricted_field in restricted_fields:
            if restricted_field in flattened_attributes:
                return False

        for field_name, field_values in allowed_fields_values.items():
            if field_name not in flattened_attributes:
                continue
            if (
                    isinstance(flattened_attributes[field_name], list) and
                    isinstance(field_values[0], list) and
                    not all(i in field_values[0] for i in flattened_attributes[field_name])
            ):
                return False
            elif (
                    not isinstance(flattened_attributes[field_name], list) and
                    flattened_attributes[field_name] not in field_values
            ):
                return False

        return True

    async def check_space_access(self, user_shortname: str, space_name: str) -> bool:
        user_permissions = await access_control.get_user_permissions(user_shortname)
        prog = re.compile(f"{space_name}:*|{settings.all_spaces_mw}:*")
        return bool(list(filter(prog.match, user_permissions.keys())))

    def trans_magic_words(self, subpath: str, user_shortname: str):
        subpath = subpath.replace(settings.current_user_mw, user_shortname)
        subpath = subpath.replace("//", "/")

        if len(subpath) == 0:
            subpath = "/"
        if subpath[0] == "/" and len(subpath) > 1:
            subpath = subpath[1:]
        if subpath[-1] == "/" and len(subpath) > 1:
            subpath = subpath[:-1]
        return subpath

    async def generate_user_permissions(self, user_shortname: str) -> dict:
        user_permissions: dict = {}

        user_roles = await self.get_user_roles(user_shortname)

        for _, role in user_roles.items():
            role_permissions = await self.get_role_permissions(role)
            permission_world_record = await db.load_or_none( settings.management_space, 'permissions', "world", Permission)
            if permission_world_record:
                role_permissions.append(permission_world_record)

            for permission in role_permissions:
                for space_name, permission_subpaths in permission.subpaths.items():
                    for permission_subpath in permission_subpaths:
                        permission_subpath = self.trans_magic_words(permission_subpath, user_shortname)
                        for permission_resource_types in permission.resource_types:
                            actions = set(permission.actions)
                            conditions = set(permission.conditions)
                            if (
                                    f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                    in user_permissions
                            ):
                                old_perm = user_permissions[
                                    f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                ]

                                if isinstance(actions, list):
                                    actions = set(actions)
                                actions |= set(old_perm["allowed_actions"])

                                if isinstance(conditions, list):
                                    conditions = set(conditions)
                                conditions |= set(old_perm["conditions"])

                            user_permissions[
                                f"{space_name}:{permission_subpath}:{permission_resource_types}"
                            ] = {
                                "allowed_actions": list(actions),
                                "conditions": list(conditions),
                                "restricted_fields": permission.restricted_fields,
                                "allowed_fields_values": permission.allowed_fields_values
                            }
        if settings.active_data_db == "file":
            async with RedisServices() as redis_services:
                await redis_services.save_doc(
                    self.generate_user_permission_doc_id(user_shortname), user_permissions
                )
        return user_permissions

    async def get_role_permissions(self, role: Role) -> list[Permission]:
        if settings.active_data_db == "file":
            return await self.get_role_permissions_operational(role)
        else:
            return await self.get_role_permissions_database(role)

    async def get_role_permissions_operational(self, role: Role) -> list[Permission]:
        permissions_options = "|".join(role.permissions)
        async with RedisServices() as redis_services:
            permissions_search = await redis_services.search(
                space_name=settings.management_space,
                search=f"@shortname:{permissions_options}",
                filters={"subpath": ["permissions"]},
                limit=10000,
                offset=0,
            )
        if not permissions_search:
            return []

        role_permissions: list[Permission] = []

        for permission_doc in permissions_search["data"]:
            permission = Permission.model_validate(json.loads(permission_doc))
            role_permissions.append(permission)

        return role_permissions

    async def get_role_permissions_database(self, role: Role) -> list[Permission]:
        role_records = await db.load_or_none(
            settings.management_space, 'roles', role.shortname, Role
        )

        if role_records is None:
            return []

        role_permissions: list[Permission] = []

        for permission in role_records.permissions:
            permission_record = await db.load_or_none(
                settings.management_space, 'permissions', permission, Permission
            )
            if permission_record is None:
                continue
            role_permissions.append(permission_record)

        return role_permissions

    async def get_user_roles(self, user_shortname: str) -> dict[str, Role]:
        if settings.active_data_db == "file":
            return await self.get_user_roles_operational(user_shortname)
        else:
            return await self.get_user_roles_database(user_shortname)

    async def get_user_roles_operational(self, user_shortname: str) -> dict[str, Role]:
        user_meta: User = await self.load_user_meta(user_shortname)
        user_associated_roles = user_meta.roles
        user_associated_roles.append("logged_in")
        async with RedisServices() as redis_services:
            roles_search = await redis_services.search(
                space_name=settings.management_space,
                search="@shortname:(" + "|".join(user_associated_roles) + ")",
                filters={"subpath": ["roles"]},
                limit=10000,
                offset=0,
            )

        user_roles_from_groups = await self.get_user_roles_from_groups(user_meta)
        if not roles_search and not user_roles_from_groups:
            return {}

        user_roles: dict[str, Role] = {}

        all_user_roles_from_redis = []
        for redis_document in roles_search["data"]:
            all_user_roles_from_redis.append(redis_document)

        all_user_roles_from_redis.extend(user_roles_from_groups)
        for role_json in all_user_roles_from_redis:
            role = Role.model_validate(json.loads(role_json))
            user_roles[role.shortname] = role

        return user_roles

    async def get_user_roles_database(self, user_shortname: str) -> dict[str, Role]:
        try:
            user = await db.load_or_none(
                settings.management_space, settings.users_subpath, user_shortname, User
            )

            if user is None:
                return {}

            user_roles: dict[str, Role] = {}
            for role in user.roles:
                role_record = await db.load_or_none(
                    settings.management_space, 'roles', role, Role
                )
                if role_record is None:
                    continue

                user_roles[role] = role_record
            return user_roles
        except Exception as e:
            print(f"Error: {e}")
            return {}

    async def load_user_meta(self, user_shortname: str) -> Any:
        async with RedisServices() as redis_services:
            # file: fetch from op if not found
            #       get from files then save it in op db
            # sql: fetch directly thought db
            if settings.active_data_db == "file":
                user_meta_doc_id = redis_services.generate_doc_id(
                    space_name=settings.management_space,
                    schema_shortname="meta",
                    subpath="users",
                    shortname=user_shortname,
                )
                value: dict = await redis_services.get_doc_by_id(user_meta_doc_id)
            else:
                value = {}
            if not value:
                user = await db.load(
                    space_name=settings.management_space,
                    shortname=user_shortname,
                    subpath="users",
                    class_type=User,
                    user_shortname=user_shortname,
                )
                if settings.active_data_db == "file":
                    await redis_services.save_meta_doc(
                        settings.management_space,
                        "users",
                        user,
                    )
                return user
            else:
                user = User(**value)
                return user

    async def get_user_by_criteria(self, key: str, value: str) -> str | None:
        if settings.active_data_db == "file":
            async with RedisServices() as redis_services:
                user_search = await redis_services.search(
                    space_name=settings.management_space,
                    search=f"@{key}:({value.replace('@', '?')})",
                    filters={"subpath": ["users"]},
                    limit=10000,
                    offset=0,
                )
            if not user_search["data"]:
                return None

            data = json.loads(user_search["data"][0])
            if data.get("shortname") and isinstance(data["shortname"], str):
                return data["shortname"]
            else:
                return None
        else:
            _user = await db.get_entry_by_criteria(
                {key: value},
                Users
            )
            if _user is None or len(_user) == 0:
                return None
            return str(_user[0].shortname)

    async def get_user_roles_from_groups(self, user_meta: User) -> list:

        if not user_meta.groups:
            return []

        async with RedisServices() as redis_services:
            groups_search = await redis_services.search(
                space_name=settings.management_space,
                search="@shortname:(" + "|".join(user_meta.groups) + ")",
                filters={"subpath": ["groups"]},
                limit=10000,
                offset=0,
            )
            if not groups_search:
                return []

            roles = []
            for group in groups_search["data"]:
                group_json = json.loads(group)
                for role_shortname in group_json["roles"]:
                    role = await redis_services.get_doc_by_id(
                        redis_services.generate_doc_id(
                            space_name=settings.management_space,
                            schema_shortname="meta",
                            shortname=role_shortname,
                            subpath="roles"
                        )
                    )
                    if role:
                        roles.append(role)

        return roles

    async def get_user_query_policies(
            self,
            user_shortname: str,
            space_name: str,
            subpath: str
    ) -> list:
        """
        Generate list of query policies based on user's permissions
        ex: [
            "products:offers:content:true:admin_shortname", # IF conditions = {"is_active", "own"}
            "products:offers:content:true:*", # IF conditions = {"is_active"}
            "products:offers:content:false:admin_shortname|products:offers:content:true:admin_shortname",
            # ^^^ IF conditions = {"own"}
            "products:offers:content:*", # IF conditions = {}
        ]
        """
        user_permissions = await self.get_user_permissions(user_shortname)
        user_groups = (await self.load_user_meta(user_shortname)).groups or []
        user_groups.append(user_shortname)

        redis_query_policies = []
        for perm_key, permission in user_permissions.items():
            if (
                    not perm_key.startswith(space_name) and
                    not perm_key.startswith(settings.all_spaces_mw)
            ):
                continue
            perm_key = perm_key.replace(settings.all_spaces_mw, space_name)
            perm_key = perm_key.replace(settings.all_subpaths_mw, subpath.strip("/"))
            perm_key = perm_key.strip("/")
            if (
                    ConditionType.is_active in permission["conditions"]
                    and ConditionType.own in permission["conditions"]
            ):
                for user_group in user_groups:
                    redis_query_policies.append(f"{perm_key}:true:{user_group}")
            elif ConditionType.is_active in permission["conditions"]:
                redis_query_policies.append(f"{perm_key}:true:*")
            elif ConditionType.own in permission["conditions"]:
                for user_group in user_groups:
                    redis_query_policies.append(
                        f"{perm_key}:true:{user_shortname}|{perm_key}:false:{user_group}"
                    )
            else:
                redis_query_policies.append(f"{perm_key}:*")
        return redis_query_policies


access_control = AccessControl()
