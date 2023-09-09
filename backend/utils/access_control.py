import json
import re
from redis.commands.search.field import TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redis.commands.search.result import Result
from models.core import ActionType, ConditionType, Group, Permission, Role, User
from models.enums import ResourceType
from utils.helpers import flatten_dict
from utils.settings import settings
import utils.db as db
import models.core as core
from utils.regex import FILE_PATTERN
from utils.redis_services import RedisServices

class AccessControl:
    permissions: dict[str, Permission] = {}
    groups: dict[str, Group] = {}
    roles: dict[str, Role] = {}
    users: dict[str, User] = {}

    async def load_permissions_and_roles(self) -> None:
        management_branch = settings.management_space_branch
        management_path = settings.spaces_folder / settings.management_space

        management_modules : dict[str, type[core.Meta]] = {
            "groups": core.Group,
            "roles": core.Role,
            "permissions": core.Permission
        }

        for module_name, module_value in management_modules.items():
            path = management_path / module_name
            entries_glob = ".dm/*/meta.*.json"
            for one in path.glob(entries_glob):
                match = FILE_PATTERN.search(str(one))
                if not match or not one.is_file():
                    continue
                shortname = match.group(1)
                try:
                    resource_obj : core.Meta = await db.load(
                        settings.management_space,
                        module_name,
                        shortname,
                        module_value,
                        "anonymous",
                        management_branch,
                    )
                    module = getattr(self, module_name)
                    if resource_obj.is_active:
                        module[shortname] = resource_obj  # store in redis doc
                except Exception as ex:
                    print(f"Error processing @{settings.management_space}/{module_name}/{shortname} ... ", ex)
                    raise ex

        await self.create_user_premission_index()
        await self.store_modules_to_redis()
        await self.delete_user_permissions_map_in_redis()


    async def create_user_premission_index(self) -> None:
        async with RedisServices() as redis_services:
            try:
                # Check if index already exist
                await redis_services.client.ft("user_permission").info()
            except Exception:
                await redis_services.client.ft("user_permission").create_index(
                    fields=(TextField("name")),
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
                        branch_name=settings.management_space_branch,
                        subpath=module_name,
                        meta=object,
                    )

    async def delete_user_permissions_map_in_redis(self) -> None:
        async with RedisServices() as redis_services:
            search_query = Query("*").no_content()
            docs = await redis_services.client.\
                ft("user_permission").\
                search(search_query) # type: ignore
            if docs and isinstance(docs, Result): 
                keys = [doc.id for doc in docs.docs]
                if len(keys) > 0:
                    await redis_services.del_keys(keys)

    def generate_user_permission_doc_id(self, user_shortname: str):
        return f"users_permissions_{user_shortname}"

    async def get_user_premissions(self, user_shortname: str) -> dict:
        async with RedisServices() as redis_services:
            user_premissions = await redis_services.get_doc_by_id(
                self.generate_user_permission_doc_id(user_shortname)
            )

        if not user_premissions:
            value = await self.generate_user_permissions(user_shortname)
            if isinstance(value, dict):
                return value
            else:
                return {}

        if isinstance(user_premissions, dict):
            return user_premissions
        else:
            return {}

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
        if resource_type == ResourceType.space and entry_shortname:
            return await self.check_space_access(
                user_shortname,
                entry_shortname
            )
        user_permissions = await self.get_user_premissions(user_shortname)

        user_groups = (await self.load_user_meta(user_shortname)).groups or []

        # Generate set of achevied conditions on the resource
        # ex: {"is_active", "own"}
        resource_achieved_conditions: set[ConditionType] = set()
        if resource_is_active:
            resource_achieved_conditions.add(ConditionType.is_active)
        if resource_owner_shortname == user_shortname or resource_owner_group in user_groups:
            resource_achieved_conditions.add(ConditionType.own)

        subpath_parts = list(filter(None, subpath.split("/")))
        # Allow checking for root permissions
        subpath_parts.insert(0, "/")
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
                resource_achieved_conditions
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

    def has_global_access(
        self, 
        space_name: str,
        user_permissions: dict, 
        search_subpath: str,
        action_type: ActionType, 
        resource_type: str, 
        resource_achieved_conditions: set
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
            if(
                isinstance(flattened_attributes[field_name], list) and
                isinstance(field_values[0], list) and
                not all(i in field_values[0] for i in flattened_attributes[field_name])
            ):
                return False
            elif(
                not isinstance(flattened_attributes[field_name], list) and
                flattened_attributes[field_name] not in field_values
            ):
                return False

        return True
        
    
    async def check_space_access(self, user_shortname: str, space_name: str) -> bool:
        user_permissions = await access_control.get_user_premissions(user_shortname)
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


    async def generate_user_permissions(self, user_shortname: str):
        user_permissions : dict = {}

        user_roles = await self.get_user_roles(user_shortname)
        for _, role in user_roles.items():
            role_permissions = await self.get_role_permissions(role)

            for permission in role_permissions:
                for space_name, permission_subpaths in permission.subpaths.items():
                    for permission_subpath in permission_subpaths:
                        permission_subpath = self.trans_magic_words(permission_subpath, user_shortname)
                        for permission_resource_types in permission.resource_types:
                            actions = permission.actions
                            conditions = permission.conditions
                            if (
                                f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                in user_permissions
                            ):
                                old_perm = user_permissions[
                                    f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                ]
                                actions |= set(old_perm["allowed_actions"])
                                conditions |= set(old_perm["conditions"])

                            user_permissions[
                                f"{space_name}:{permission_subpath}:{permission_resource_types}"
                            ] = {
                                "allowed_actions": list(actions),
                                "conditions": list(conditions),
                                "restricted_fields": permission.restricted_fields,
                                "allowed_fields_values": permission.allowed_fields_values
                            }

        async with RedisServices() as redis_services:
            await redis_services.save_doc(
                self.generate_user_permission_doc_id(user_shortname), user_permissions
            )
        return user_permissions

    async def get_role_permissions(self, role: Role) -> list[Permission]:
        permissions_options = "|".join(role.permissions)
        async with RedisServices() as redis_services:
            permissions_search = await redis_services.search(
                space_name=settings.management_space,
                branch_name=settings.management_space_branch,
                search=f"@shortname:{permissions_options}",
                filters={"subpath": ["permissions"]},
                limit=10000,
                offset=0,
            )
        if not permissions_search:
            return []

        role_permissions: list[Permission] = []

        for permission_doc in permissions_search["data"]:
            permission = Permission.model_validate(json.loads(permission_doc.json))
            role_permissions.append(permission)

        return role_permissions

    async def get_user_roles(self, user_shortname: str) -> dict[str, Role]:
        user_meta: core.User = await self.load_user_meta(user_shortname)
        user_associated_roles = user_meta.roles
        user_associated_roles.append("logged_in")
        async with RedisServices() as redis_services:
            roles_search = await redis_services.search(
                space_name=settings.management_space,
                branch_name=settings.management_space_branch,
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
            all_user_roles_from_redis.append(json.loads(redis_document.json))

        all_user_roles_from_redis.extend(user_roles_from_groups)
        for role_json in all_user_roles_from_redis:
            role = Role.model_validate(role_json)
            user_roles[role.shortname] = role

        return user_roles

    async def load_user_meta(self, user_shortname: str) -> core.User:
        async with RedisServices() as redis_services:
            user_meta_doc_id = redis_services.generate_doc_id(
                space_name=settings.management_space,
                branch_name=settings.management_space_branch,
                schema_shortname="meta",
                subpath="users",
                shortname=user_shortname,
            )
            user = await redis_services.get_doc_by_id(user_meta_doc_id)
            if not user:
                user = await db.load(
                    space_name=settings.management_space,
                    branch_name=settings.management_space_branch,
                    shortname=user_shortname,
                    subpath="users",
                    class_type=core.User,
                    user_shortname=user_shortname,
                )
                await redis_services.save_meta_doc(
                    settings.management_space,
                    settings.management_space_branch,
                    "users",
                    user,
                )
            else:
                user = core.User(**user)
            return user


    async def get_user_by_criteria(self, key: str, value: str) -> str | None:
        async with RedisServices() as redis_services:
            user_search = await redis_services.search(
                space_name=settings.management_space,
                branch_name=settings.management_space_branch,
                search=f"@{key}:({value.replace('@','?')})",
                filters={"subpath": ["users"]},
                limit=10000,
                offset=0,
            )
        if not user_search["data"]:
            return None
        data = json.loads(user_search["data"][0].json)
        if "shortname" in data and data["shortname"] and isinstance (data["shortname"], str): 
            return data["shortname"]
        else:
            return None


    async def get_user_roles_from_groups(self, user_meta: core.User) -> list:

        if not user_meta.groups:
            return []

        async with RedisServices() as redis_services:
            groups_search = await redis_services.search(
                space_name=settings.management_space,
                branch_name=settings.management_space_branch,
                search="@shortname:(" + "|".join(user_meta.groups) + ")",
                filters={"subpath": ["groups"]},
                limit=10000,
                offset=0,
            )
            if not groups_search:
                return []

            roles = []
            for group in groups_search["data"]:
                group_json = json.loads(group.json)
                for role_shortname in group_json["roles"]:
                    role = await redis_services.get_doc_by_id(
                        redis_services.generate_doc_id(
                            space_name=settings.management_space, 
                            branch_name=settings.management_space_branch,
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
            "products:offers:content:false:admin_shortname|products:offers:content:true:admin_shortname", # IF conditions = {"own"}
            "products:offers:content:*", # IF conditions = {}
        ]
        """
        user_permissions = await self.get_user_premissions(user_shortname)
        user_groups = (await self.load_user_meta(user_shortname)).groups or []
        user_groups.append(user_shortname)

        redis_query_policies = []
        for perm_key, permission in user_permissions.items():
            if(
                not perm_key.startswith(space_name) and 
                not perm_key.startswith(settings.all_spaces_mw)
            ):
                continue
            perm_key = perm_key.replace(settings.all_spaces_mw, space_name)
            perm_key = perm_key.replace(settings.all_subpaths_mw, subpath.strip("/"))
            if (
                core.ConditionType.is_active in permission["conditions"]
                and core.ConditionType.own in permission["conditions"]
            ):
                for user_group in user_groups:
                    redis_query_policies.append(f"{perm_key}:true:{user_group}")
            elif core.ConditionType.is_active in permission["conditions"]:
                redis_query_policies.append(f"{perm_key}:true:*")
            elif core.ConditionType.own in permission["conditions"]:
                for user_group in user_groups:
                    redis_query_policies.append(
                        f"{perm_key}:true:{user_shortname}|{perm_key}:false:{user_group}"
                    )
            else:
                redis_query_policies.append(f"{perm_key}:*")
        return redis_query_policies


access_control = AccessControl()
