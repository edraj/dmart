import sys
from models.core import Meta, ACL, ActionType, ConditionType, Group, Permission, Role, User
from models.enums import ResourceType
from utils.helpers import camel_case, flatten_dict
from utils.settings import settings
from data_adapters.adapter import data_adapter as db
from utils.regex import FILE_PATTERN


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
                if path.exists():
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

            await db.create_user_premission_index()
            await db.store_modules_to_redis(self.roles, self.groups, self.permissions)
            await db.delete_user_permissions_map_in_redis()


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
        effective_space = (
            entry_shortname
            if (resource_type == ResourceType.space and entry_shortname)
            else space_name
        )

        if entry_shortname:
            acl_space, acl_subpath = (effective_space, "/") if resource_type == ResourceType.space else (space_name, subpath)
            acl_access = await self.check_access_control_list(
                acl_space,
                acl_subpath,
                resource_type,
                entry_shortname,
                action_type,
                user_shortname
            )
            if acl_access:
                return True
        user_permissions = await db.get_user_permissions(user_shortname)

        user_groups = (await db.load_user_meta(user_shortname)).groups or []

        # Generate set of achevied conditions on the resource
        # ex: {"is_active", "own"}
        resource_achieved_conditions: set[ConditionType] = set()
        if resource_is_active:
            resource_achieved_conditions.add(ConditionType.is_active)
        if resource_owner_shortname == user_shortname or resource_owner_group in user_groups:
            resource_achieved_conditions.add(ConditionType.own)

        subpath_parts = ["/"]
        subpath_parts += list(filter(None, subpath.strip("/").split("/")))
        if resource_type == ResourceType.folder and entry_shortname:
            subpath_parts.append(entry_shortname)

        search_subpath = ""
        for subpath_part in subpath_parts:
            search_subpath += subpath_part
            # Check if the user has global access
            global_access = self.has_global_access(
                effective_space,
                user_permissions,
                search_subpath,
                action_type,
                resource_type,
                resource_achieved_conditions,
                record_attributes
            )
            if global_access:
                return True

            permission_key = f"{effective_space}:{search_subpath}:{resource_type}"
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
            elif settings.debug_perm and permission_key in user_permissions:
                print(f"Debug Access: Permission found for {permission_key} but access denied.")
                if action_type not in user_permissions[permission_key]["allowed_actions"]:
                    print(f"Debug Access: Action {action_type} not in allowed actions: {user_permissions[permission_key]['allowed_actions']}")
                if not self.check_access_conditions(
                    set(user_permissions[permission_key]["conditions"]),
                    set(resource_achieved_conditions),
                    action_type,
                ):
                    print(f"Debug Access: Conditions check failed. Required: {user_permissions[permission_key]['conditions']}, Achieved: {resource_achieved_conditions}")
                if not self.check_access_restriction(
                    user_permissions[permission_key]["restricted_fields"],
                    user_permissions[permission_key]["allowed_fields_values"],
                    action_type,
                    record_attributes
                ):
                    print("Debug Access: Restrictions check failed.")

            if search_subpath == "/":
                search_subpath = ""
            else:
                search_subpath += "/"

        if settings.debug_perm:
            print(f"Debug Access: No valid permission found for user {user_shortname} accessing {effective_space}/{subpath} ({resource_type})")
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
        
        try:
            entry = await db.load(
                space_name=space_name,
                subpath=subpath,
                shortname=entry_shortname,
                class_type=resource_cls
            )
        except Exception:
            return False
            
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
            for flattened_key in flattened_attributes.keys():
                if flattened_key == restricted_field or flattened_key.startswith(f"{restricted_field}."):
                    return False

        for field_name, field_values in allowed_fields_values.items():
            if field_name not in flattened_attributes:
                continue
            if (
                    isinstance(flattened_attributes[field_name], list) and
                    isinstance(field_values[0], list) and
                    not any(all(i in allowed_values for i in flattened_attributes[field_name]) for allowed_values in field_values)
            ):
                return False
            elif (
                    not isinstance(flattened_attributes[field_name], list) and
                    flattened_attributes[field_name] not in field_values
            ):
                return False

        return True

access_control = AccessControl()
