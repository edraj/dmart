from datetime import datetime
import json
import sys
from db.redis_db import RedisDB
from repositories.base_repo import BaseRepo
from typing import Any

from models.api import Query, Exception as api_exception, Error as api_error
from models.core import EntityDTO, Meta, Permission, Role, User
from models.enums import ConditionType, ResourceType, SortType
from utils.helpers import camel_case, trans_magic_words
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
from utils import db
from fastapi import status

class RedisRepo(BaseRepo):
    redis_db: RedisDB = RedisDB()
    
    async def get_user(self, user_shortname: str) -> User:
        user_doc: None | dict[str, Any] = await self.redis_db.find(EntityDTO(
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            schema_shortname="meta",
            subpath="users",
            shortname=user_shortname,
            resource_type=ResourceType.user
        ))
        
        if user_doc:
            return User(**user_doc)
        
        user: User = await db.load(
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            shortname=user_shortname,
            subpath="users",
            class_type=User,
            user_shortname=user_shortname,
        )
        
        await self.redis_db.create(
            entity=EntityDTO(
                space_name=settings.management_space,
                branch_name=settings.management_space_branch,
                schema_shortname="meta",
                subpath="users",
                shortname=user_shortname,
            ),
            meta=user
        )
        return user
    
    def generate_user_acl_doc_id(self, user_shortname: str) -> str:
        return f"users_permissions_{user_shortname}"
    
    async def get_user_acl_doc(self, user_shortname: str) -> dict[str, Any]:
        user_permissions: dict[str, Any] = await self.redis_db.find_by_id(
            self.generate_user_acl_doc_id(user_shortname)
        )
        
        if not user_permissions:
            return await self.generate_user_acl_doc(user_shortname)
           
        return user_permissions
    
    async def generate_user_acl_doc(self, user_shortname: str) -> dict[str, Any]:
        """
        User's Access Control List Document should be
        a dict of: key = "{space}:{subpath}:{resource_type}"
        and the value is another dict of
        1. list of allowed actions
        2. list of permission conditions
        3. list of restricted fields
        4. dict of allowed fields values
        
        """
        user_acl : dict[str, Any] = {}

        user_roles = await self.get_user_roles(user_shortname)
        for _, role in user_roles.items():
            role_permissions = await self.get_role_permissions(role)

            for permission in role_permissions:
                for space_name, permission_subpaths in permission.subpaths.items():
                    for permission_subpath in permission_subpaths:
                        permission_subpath = trans_magic_words(permission_subpath, user_shortname)
                        for permission_resource_types in permission.resource_types:
                            actions = permission.actions
                            conditions = permission.conditions
                            if (
                                f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                in user_acl
                            ):
                                old_perm = user_acl[
                                    f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                ]
                                actions |= set(old_perm["allowed_actions"])
                                conditions |= set(old_perm["conditions"])

                            user_acl[
                                f"{space_name}:{permission_subpath}:{permission_resource_types}"
                            ] = {
                                "allowed_actions": list(actions),
                                "conditions": list(conditions),
                                "restricted_fields": permission.restricted_fields,
                                "allowed_fields_values": permission.allowed_fields_values
                            }
                            
        await self.redis_db.save_at_id(
            self.generate_user_acl_doc_id(user_shortname), user_acl
        )

        return user_acl
    
    async def get_user_roles(self, user_shortname: str) -> dict[str, Role]:
        user_meta: User = await self.get_user(user_shortname)
        user_associated_roles: list[str] = user_meta.roles
        user_associated_roles.append("logged_in")
        
        roles_search = await self.redis_db.search(
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
            all_user_roles_from_redis.append(redis_document)

        all_user_roles_from_redis.extend(user_roles_from_groups)
        for role_json in all_user_roles_from_redis:
            role = Role.model_validate(json.loads(role_json))
            user_roles[role.shortname] = role

        return user_roles
    
    async def get_user_roles_from_groups(self, user_meta: User) -> list[Role]:
        if not user_meta.groups:
            return []
        
        groups_search = await self.redis_db.search(
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            search="@shortname:(" + "|".join(user_meta.groups) + ")",
            filters={"subpath": ["groups"]},
            limit=10000,
            offset=0,
        )
        if not groups_search:
            return []

        roles: list[Role] = []
        for group in groups_search["data"]:
            group_json = json.loads(group)
            for role_shortname in group_json["roles"]:
                role_doc: None | dict[str, Any] = await self.redis_db.find(
                    EntityDTO(
                        space_name=settings.management_space, 
                        branch_name=settings.management_space_branch,
                        schema_shortname="meta",
                        shortname=role_shortname,
                        subpath="roles"
                    )
                )
                if role_doc:
                    roles.append(Role(**role_doc))

        return roles
    
    async def get_role_permissions(self, role: Role) -> list[Permission]:
        permissions_options = "|".join(role.permissions)
        
        permissions_search = await self.redis_db.search(
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
            permission = Permission.model_validate(json.loads(permission_doc))
            role_permissions.append(permission)

        return role_permissions
    
    async def user_query_policies(self, user_shortname: str, space: str, subpath: str) -> list[str]:
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
        user_permissions = await self.get_user_acl_doc(user_shortname)
        user_groups = (await self.get_user(user_shortname)).groups or []
        user_groups.append(user_shortname)

        redis_query_policies = []
        for perm_key, permission in user_permissions.items():
            if(
                not perm_key.startswith(space) and 
                not perm_key.startswith(settings.all_spaces_mw)
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
    
    async def search(self, query: Query, user_shortname: str) -> tuple[list[Any], int]:
        search_res: list[Any] = []
        total: int = 0

        if not query.filter_schema_names:
            query.filter_schema_names = ["meta"]

        created_at_search = ""

        if query.from_date and query.to_date:
            created_at_search = (
                "[" + f"{query.from_date.timestamp()} {query.to_date.timestamp()}" + "]"
            )

        elif query.from_date:
            created_at_search = (
                "["
                + f"{query.from_date.timestamp()} {datetime(2199, 12, 31).timestamp()}"
                + "]"
            )

        elif query.to_date:
            created_at_search = (
                "["
                + f"{datetime(2010, 1, 1).timestamp()} {query.to_date.timestamp()}"
                + "]"
            )

        limit = query.limit
        offset = query.offset
        if len(query.filter_schema_names) > 1 and query.sort_by:
            limit += offset
            offset = 0

        query_policies: list[str] = await self.user_query_policies(
            user_shortname=user_shortname, 
            space=query.space_name,
            subpath=query.subpath
        )
        for schema_name in query.filter_schema_names:
            redis_res = await self.redis_db.search(
                space_name=query.space_name,
                branch_name=query.branch_name,
                schema_name=schema_name,
                search=str(query.search),
                filters={
                    "resource_type": query.filter_types or [],
                    "shortname": query.filter_shortnames or [],
                    "tags": query.filter_tags or [],
                    "subpath": [query.subpath],
                    "query_policies": query_policies,
                    "user_shortname": user_shortname,
                    "created_at": created_at_search,
                },
                exact_subpath=query.exact_subpath,
                limit=limit,
                offset=offset,
                highlight_fields=list(query.highlight_fields.keys()),
                sort_by=query.sort_by,
                sort_type=query.sort_type or SortType.ascending,
            )

            if redis_res:
                search_res.extend(redis_res["data"])
                total += redis_res["total"]
        return search_res, total

    async def find(self, entity: EntityDTO) -> None | Meta:
        """Return an object of the corresponding class of the entity.resource_type
        default entity.resource_type is ResourceType.content
        """
        user_document = await self.redis_db.find(entity)
        
        if not user_document:
            return None
        
        try:
            resource_cls = getattr(sys.modules["models.core"], camel_case(entity.resource_type))
            return resource_cls(**user_document)
        except Exception as _:
            return None

    async def find_or_fail(self, entity: EntityDTO) -> Meta:
        item: None | Meta = await self.find(entity)
        
        if not item:
            raise api_exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api_error(
                    type="delete", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"),
            )
        
        return item
            
    
    