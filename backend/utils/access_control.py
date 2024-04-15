import json
import re
from typing import Any
from models.enums import ResourceType, ActionType, ConditionType
from utils.helpers import flatten_dict, trans_magic_words
from utils.settings import settings
import models.core as core
from utils.operational_database import operational_db

class AccessControl:

    async def check_access(
        self,
        entity: core.EntityDTO,
        action_type: ActionType, #XX
        record_attributes: dict = {}, #XX
        meta: core.Meta | None = None,
    ) -> bool:
        if not entity.user_shortname:
            return False
        
        if entity.resource_type == ResourceType.space and entity.shortname:
            return await self.check_space_access(
                entity.user_shortname,
                entity.shortname
            )
        user_permissions = await self.get_user_permissions_doc(entity.user_shortname)

        user_groups: list[str] = (await self.get_user(entity.user_shortname)).groups or []

        # Generate set of achevied conditions on the resource
        # ex: {"is_active", "own"}
        # meta: None | core.Meta = await self.find(entity)
        
        resource_achieved_conditions: set[ConditionType] = set()
        if meta and meta.is_active:
            resource_achieved_conditions.add(ConditionType.is_active)
        if meta and (meta.owner_shortname == entity.user_shortname or meta.owner_group_shortname in user_groups):
            resource_achieved_conditions.add(ConditionType.own)
        
        # Allow checking for root permissions
        subpath_parts = ["/"]
        subpath_parts += list(filter(None, entity.subpath.strip("/").split("/")))
        if entity.resource_type == ResourceType.folder and entity.shortname:
            subpath_parts.append(entity.shortname)
        
        search_subpath = ""
        for subpath_part in subpath_parts:
            search_subpath += subpath_part
            # Check if the user has global access
            global_access = self.has_global_access(
                entity.space_name,
                user_permissions, 
                search_subpath,
                action_type, 
                entity.resource_type, 
                resource_achieved_conditions,
                record_attributes
            )
            if global_access:
                return True
            
            permission_key = f"{entity.space_name}:{search_subpath}:{entity.resource_type}"
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

        if entity.shortname and meta:
            return await self.check_access_control_list(
                meta, entity.user_shortname, action_type
            )
            
        return False

    async def check_access_control_list(
        self,
        entry: core.Meta,
        user_shortname: str,
        action_type: ActionType,
    ) -> bool:
        if not entry.acl:
            return False
        
        user_acl: core.ACL | None = None
        for access in entry.acl:
            if access.user_shortname == user_shortname:
                user_acl = access
                break
            
        if not user_acl:
            return False
        
        return (action_type in user_acl.allowed_actions)
            
            
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
        user_permissions = await self.get_user_permissions_doc(user_shortname)
        prog = re.compile(f"{space_name}:*|{settings.all_spaces_mw}:*")
        return bool(list(filter(prog.match, user_permissions.keys())))


    async def get_user(self, user_shortname: str) -> core.User:
        user_doc: dict[str, Any] = await operational_db.find_or_fail(core.EntityDTO(
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            schema_shortname="meta",
            subpath="users",
            shortname=user_shortname,
            resource_type=ResourceType.user,
        ))
        
        return core.User(**user_doc)


    async def user_query_policies(
        self, user_shortname: str, space: str, subpath: str
    ) -> list[str]:
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
        user_permissions = await self.get_user_permissions_doc(user_shortname)
        user_groups = (await self.get_user(user_shortname)).groups or []
        user_groups.append(user_shortname)

        redis_query_policies = []
        for perm_key, permission in user_permissions.items():
            if not perm_key.startswith(space) and not perm_key.startswith(
                settings.all_spaces_mw
            ):
                continue
            perm_key = perm_key.replace(settings.all_spaces_mw, space)
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


    async def get_user_by_criteria(self, key: str, value: str) -> core.User | None:
        search_res: tuple[int, list[dict[str, Any]]] = await operational_db.search(
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            search=f"@{key}:({value.replace('@','?')})",
            limit=2,
            offset=0,
            filters={"subpath": [settings.users_subpath]}
        )
        try:
            if search_res[0] == 1 and len(search_res[1]) == 1:
                return core.User(**search_res[1][0])
            
            return None
        except Exception as _:
            return None

    async def get_user_roles_from_groups(self, user_meta: core.User) -> list[core.Role]:
        if not user_meta.groups:
            return []

        groups_search = await operational_db.search(
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            search="@shortname:(" + "|".join(user_meta.groups) + ")",
            filters={"subpath": ["groups"]},
            limit=10000,
            offset=0,
        )
        if not groups_search:
            return []

        roles: list[core.Role] = []
        for group_json in groups_search[1]:
            for role_shortname in group_json["roles"]:
                role_doc: None | dict[str, Any] = await operational_db.find(
                    core.EntityDTO(
                        space_name=settings.management_space,
                        branch_name=settings.management_space_branch,
                        schema_shortname="meta",
                        shortname=role_shortname,
                        subpath="roles",
                    )
                )
                if role_doc:
                    roles.append(core.Role(**role_doc))

        return roles
    
    async def get_role_permissions(self, role: core.Role) -> list[core.Permission]:
        permissions_options = "|".join(role.permissions)

        permissions_search = await operational_db.search(
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            search=f"@shortname:{permissions_options}",
            filters={"subpath": ["permissions"]},
            limit=10000,
            offset=0,
        )
        if not permissions_search:
            return []

        role_permissions: list[core.Permission] = []

        for permission_doc in permissions_search[1]:
            permission = core.Permission.model_validate(permission_doc)
            role_permissions.append(permission)

        return role_permissions
    
    async def get_user_roles(self, user_shortname: str) -> dict[str, core.Role]:
        user_meta: core.User = await self.get_user(user_shortname)
        user_associated_roles: list[str] = user_meta.roles
        user_associated_roles.append("logged_in")

        roles_search = await operational_db.search(
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

        user_roles: dict[str, core.Role] = {}

        all_user_roles_from_redis = []
        for redis_document in roles_search[1]:
            all_user_roles_from_redis.append(redis_document)

        all_user_roles_from_redis.extend(user_roles_from_groups)
        for role_json in all_user_roles_from_redis:
            role = core.Role.model_validate(json.loads(role_json))
            user_roles[role.shortname] = role

        return user_roles

    def generate_user_permissions_doc_id(self, user_shortname: str) -> str:
        return f"users_permissions_{user_shortname}"
    
    async def generate_user_permissions_doc(
        self, user_shortname: str
    ) -> dict[str, Any]:
        """
        User's Access Control List Document should be
        a dict of: key = "{space}:{subpath}:{resource_type}"
        and the value is another dict of
        1. list of allowed actions
        2. list of permission conditions
        3. list of restricted fields
        4. dict of allowed fields values

        """
        user_permissions: dict[str, Any] = {}

        user_roles = await self.get_user_roles(user_shortname)
        for _, role in user_roles.items():
            role_permissions = await self.get_role_permissions(role)

            for permission in role_permissions:
                for space_name, permission_subpaths in permission.subpaths.items():
                    for permission_subpath in permission_subpaths:
                        permission_subpath = trans_magic_words(
                            permission_subpath, user_shortname
                        )
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
                                "allowed_fields_values": permission.allowed_fields_values,
                            }

        await operational_db.save_at_id(
            self.generate_user_permissions_doc_id(user_shortname), user_permissions
        )

        return user_permissions
    
    async def get_user_permissions_doc(self, user_shortname: str) -> dict[str, Any]:
        user_permissions: dict[str, Any] = await operational_db.find_by_id(
            self.generate_user_permissions_doc_id(user_shortname)
        )

        if not user_permissions:
            return await self.generate_user_permissions_doc(user_shortname)

        return user_permissions

access_control = AccessControl()
