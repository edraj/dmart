# test pull
from abc import ABC, abstractmethod
import datetime
from typing import Any

import api
from models.api import Exception as api_exception, Error as api_error
from models.core import EntityDTO, Group, Meta, Permission, Role, User
from models.enums import LockAction, ResourceType, SortType
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
from fastapi import status


class BaseDB(ABC):
    
    SYS_ATTRIBUTES: list[str] = [
        "payload_string",
        "branch_name",
        "query_policies",
        "subpath",
        "resource_type",
        "meta_doc_id",
        "payload_doc_id",
        "payload_string",
        "view_acl",
    ]
    SYS_INDEXES: list[dict[str, Any]] = [
        {
            "space": "management",
            "branch": settings.management_space_branch,
            "subpath": "roles",
            "class": Role,
            "exclude_from_index": [
                "relationships",
                "acl",
                "is_active",
                "description",
                "displayname",
                "payload",
            ],
        },
        {
            "space": "management",
            "branch": settings.management_space_branch,
            "subpath": "groups",
            "class": Group,
            "exclude_from_index": [
                "relationships",
                "acl",
                "is_active",
                "description",
                "displayname",
                "payload",
            ],
        },
        {
            "space": "management",
            "branch": settings.management_space_branch,
            "subpath": "users",
            "class": User,
            "exclude_from_index": [
                "relationships",
                "acl",
                "is_active",
                "description",
                "displayname",
                "payload",
                "password",
                "is_email_verified",
                "is_msisdn_verified",
                "type",
                "force_password_change",
                "social_avatar_url",
            ],
        },
        {
            "space": "management",
            "branch": settings.management_space_branch,
            "subpath": "permissions",
            "class": Permission,
            "exclude_from_index": [
                "relationships",
                "acl",
                "is_active",
                "description",
                "displayname",
                "payload",
                "subpaths",
                "resource_types",
                "actions",
                "conditions",
                "restricted_fields",
                "allowed_fields_values",
            ],
        },
    ]


    # ================================================================================
    # Core CRUD Functions
    # ================================================================================
    @abstractmethod
    async def search(
        self,
        space_name: str,
        search: str,
        filters: dict[str, str | list | None],
        limit: int,
        offset: int,
        exact_subpath: bool = False,
        sort_type: SortType = SortType.ascending,
        branch_name: str | None = None,
        sort_by: str | None = None,
        highlight_fields: list[str] | None = None,
        schema_name: str = "meta",
        return_fields: list = [],
    ) -> tuple[int, list[dict[str, Any]]]:
        pass
    
    @abstractmethod
    async def aggregate(
        self,
        space_name: str,
        filters: dict[str, str | list | None],
        group_by: list[str],
        reducers: list[Any],
        search: str | None = None,
        max: int = 10,
        branch_name: str = settings.default_branch,
        exact_subpath: bool = False,
        sort_type: SortType = SortType.ascending,
        sort_by: str | None = None,
        schema_name: str = "meta",
        load: list = [],
    ) -> list[Any]:
        pass
    
    @abstractmethod
    async def get_count(self, space_name: str, schema_shortname: str, branch_name: str = settings.default_branch) -> int:
        pass

    @abstractmethod
    async def free_search(
        self, index_name: str, search_str: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def dto_doc_id(self, dto: EntityDTO) -> str:
        pass

    @abstractmethod
    async def find(self, dto: EntityDTO) -> None | dict[str, Any]:
        pass

    async def find_or_fail(self, dto: EntityDTO) -> dict[str, Any]:
        item = await self.find(dto)

        if not item:
            raise api_exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api_error(
                    type="find",
                    code=InternalErrorCode.OBJECT_NOT_FOUND,
                    message="Request object is not available",
                ),
            )

        return item

    @abstractmethod
    async def find_key(self, key: str) -> str | None:
        pass

    @abstractmethod
    async def set_key(self, key: str, value: str, ex=None, nx: bool = False) -> bool:
        pass

    @abstractmethod
    async def find_by_id(self, id: str) -> dict[str, Any]:
        pass
    
    @abstractmethod
    async def list_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        pass
    
    @abstractmethod
    async def delete_keys(self, keys: list[str]) -> bool:
        pass

    @abstractmethod
    async def find_payload_data_by_id(
        self, id: str, resource_type: ResourceType
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def save_at_id(self, id: str, doc: dict[str, Any] = {}) -> bool:
        pass

    @abstractmethod
    async def prepare_meta_doc(
        self, space_name: str, branch_name: str | None, subpath: str, meta: Meta
    ) -> tuple[str, dict[str, Any]]:
        pass

    @abstractmethod
    async def prepare_payload_doc(
        self,
        dto: EntityDTO,
        meta: Meta,
        payload: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        pass
    

    @abstractmethod
    async def delete(self, dto: EntityDTO) -> bool:
        pass 

    @abstractmethod
    async def delete_doc_by_id(self, id: str) -> bool:
        pass

    @abstractmethod
    async def move(
        self,
        space_name: str,
        src_subpath: str,
        src_shortname: str,
        dest_subpath: str | None,
        dest_shortname: str | None,
        meta: Meta,
        branch_name: str | None = settings.default_branch,
    ) -> bool:
        pass
    # ================================== END =========================================


    # ================================================================================
    # Indexes Functions
    # ================================================================================
    @abstractmethod
    async def list_indexes(self) -> set[str]:
        pass

    @abstractmethod
    async def drop_index(self, name: str, delete_docs: bool) -> bool:
        pass
    
    @abstractmethod
    async def flush_all(self) -> None:
        pass
    
    @abstractmethod
    async def create_index(self, name: str, fields: list[Any], **kwargs) -> bool:
        pass

    @abstractmethod
    async def create_application_indexes(
        self,
        for_space: str | None = None,
        for_schemas: list | None = None,
        for_custom_indices: bool = True,
        del_docs: bool = True,
    ) -> None:
        """Loop over all spaces, and for each one we create: (only if indexing_enabled is true for the space)
        1-index for meta file called space_name:meta
        2-indices for schema files called space_name:{schema_shortname}

        Args:
            for_space (str | None, optional): spaces filter. Defaults to None.
            for_schemas (list | None, optional): schemas filter. Defaults to None.
            for_custom_indices (bool, optional): _description_. Defaults to True.
            del_docs (bool, optional): _description_. Defaults to True.
        """
        pass
    
    @abstractmethod
    async def create_custom_indices(self, for_space: str | None = None) -> None:
        """Create indexes for each class defines in self.SYS_INDEXES
        
        Args:
            for_space (str | None, optional): spaces filter. Defaults to None.
        """
        pass
    # ================================== END =========================================


    # ================================================================================
    # Locking Functions
    # ================================================================================
    @abstractmethod
    async def save_lock_doc(
        self, dto: EntityDTO, owner_shortname: str, ttl: int = settings.lock_period
    ) -> LockAction | None:
        lock_doc_id = self.generate_doc_id(
            dto.space_name, dto.branch_name, "lock", dto.payload_shortname, dto.subpath
        )
        lock_data = await self.get_lock_doc(
            dto.space_name, dto.branch_name, dto.subpath, dto.payload_shortname
        )
        if not lock_data:
            payload = {
                "owner_shortname": owner_shortname,
                "lock_time": str(datetime.now().isoformat()),
            }
            result = await self.save_doc(lock_doc_id, payload, nx=True)
            if result is None:
                lock_payload = await self.get_lock_doc(
                    dto.space_name, dto.branch_name, dto.subpath, dto.payload_shortname
                )
                if lock_payload["owner_shortname"] != owner_shortname:
                    raise api.Exception(
                        status_code=status.HTTP_403_FORBIDDEN,
                        error=api.Error(
                            type="lock",
                            code=InternalErrorCode.LOCKED_ENTRY,
                            message=f"Entry is already locked by {lock_payload['owner_shortname']}",
                        ),
                    )
            lock_type = LockAction.lock
        else:
            lock_type = LockAction.extend
        await self.set_ttl(lock_doc_id, ttl)
        return lock_type

 
    @abstractmethod
    async def get_lock_doc(self, dto: EntityDTO) -> dict[str, Any]:
        lock_doc_id = self.generate_doc_id(
            dto.space_name, dto.branch_name, "lock", dto.payload_shortname, dto.subpath
        )
        return await self.get_doc_by_id(lock_doc_id)


    @abstractmethod
    async def is_locked_by_other_user( self, dto: EntityDTO ) -> bool:
        pass
    
    @abstractmethod
    async def delete_lock_doc(self, dto: EntityDTO) -> None:
        await self.delete_doc( # ??
            dto.space_name, dto.branch_name, "lock", dto.payload_shortname, dto.subpath
        )

    # ================================== END =========================================


    def generate_doc_id(
        self,
        space_name: str,
        branch_name: str | None,
        schema_shortname: str,
        shortname: str,
        subpath: str,
    ) -> str:
        subpath = subpath.strip("/")
        return f"{space_name}:{branch_name}:{schema_shortname}:{subpath}/{shortname}"


    def generate_query_policies(
        self,
        space_name: str,
        subpath: str,
        resource_type: str,
        is_active: bool,
        owner_shortname: str,
        owner_group_shortname: str | None,
        entry_shortname: str | None = None,
    ) -> list:
        subpath_parts = ["/"]
        subpath_parts += subpath.strip("/").split("/")

        if resource_type == ResourceType.folder and entry_shortname:
            subpath_parts.append(entry_shortname)

        query_policies: list = []
        full_subpath = ""
        for subpath_part in subpath_parts:
            full_subpath += subpath_part
            query_policies.append(
                f"{space_name}:{full_subpath.strip('/')}:{resource_type}:{str(is_active).lower()}:{owner_shortname}"
            )
            if owner_group_shortname is None:
                query_policies.append(
                    f"{space_name}:{full_subpath.strip('/')}:{resource_type}:{str(is_active).lower()}"
                )
            else:
                query_policies.append(
                    f"{space_name}:{full_subpath.strip('/')}:{resource_type}:{str(is_active).lower()}:{owner_group_shortname}"
                )

            full_subpath_parts = full_subpath.split("/")
            if len(full_subpath_parts) > 1:
                subpath_with_magic_keyword = (
                    "/".join(full_subpath_parts[:1]) + "/" + settings.all_subpaths_mw
                )
                if len(full_subpath_parts) > 2:
                    subpath_with_magic_keyword += "/" + "/".join(full_subpath_parts[2:])
                query_policies.append(
                    f"{space_name}:{subpath_with_magic_keyword.strip('/')}:{resource_type}:{str(is_active).lower()}"
                )

            if full_subpath == "/":
                full_subpath = ""
            else:
                full_subpath += "/"

        return query_policies
    
    def generate_view_acl(self, acl: list[dict[str, Any]] | None) -> list[str] | None:
        if not acl:
            return None

        view_acl: list[str] = []

        for access in acl:
            if ActionType.view in access.get(
                "allowed_actions", []
            ) or ActionType.query in access.get("allowed_actions", []):
                view_acl.append(access["user_shortname"])

        return view_acl
