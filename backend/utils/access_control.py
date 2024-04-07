import re
from typing import Any
from models.api import Query
from models.enums import QueryType, ResourceType, ActionType, ConditionType
from utils.helpers import flatten_dict
from utils.settings import settings
import models.core as core
from utils.operational_repo import operational_repo


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
        user_permissions = await operational_repo.get_user_permissions_doc(entity.user_shortname)

        user_groups: list[str] = (await operational_repo.get_user(entity.user_shortname)).groups or []

        # Generate set of achevied conditions on the resource
        # ex: {"is_active", "own"}
        # meta: None | core.Meta = await operational_repo.find(entity)
        
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
        user_permissions = await operational_repo.get_user_permissions_doc(user_shortname)
        prog = re.compile(f"{space_name}:*|{settings.all_spaces_mw}:*")
        return bool(list(filter(prog.match, user_permissions.keys())))




    async def get_user_by_criteria(self, key: str, value: str) -> core.User | None:
        search_res: tuple[int, list[dict[str, Any]]] = await operational_repo.search(Query(
            type=QueryType.search,
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            subpath=settings.users_subpath,
            search=f"@{key}:({value.replace('@','?')})",
            limit=2,
            offset=0,
        ))
        try:
            if search_res[0] == 1 and len(search_res[1]) == 1:
                return core.User(**search_res[1][0])
            
            return None
        except Exception as _:
            return None



access_control = AccessControl()
