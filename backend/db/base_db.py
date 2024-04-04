from abc import ABC, abstractmethod
from typing import Any

from models.api import Exception as api_exception, Error as api_error
from models.core import EntityDTO, Meta
from models.enums import LockAction, ResourceType, SortType
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
from fastapi import status


class BaseDB(ABC):

    @abstractmethod
    async def search(
        self,
        space_name: str,
        branch_name: str | None,
        search: str,
        filters: dict[str, str | list | None],
        limit: int,
        offset: int,
        exact_subpath: bool = False,
        sort_type: SortType = SortType.ascending,
        sort_by: str | None = None,
        highlight_fields: list[str] | None = None,
        schema_name: str = "meta",
        return_fields: list = [],
    ) -> tuple[int, list[dict[str, Any]]]:
        pass

    @abstractmethod
    async def free_search(
        self, index_name: str, search_str: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def entity_doc_id(self, entity: EntityDTO) -> str:
        pass

    @abstractmethod
    async def find(self, entity: EntityDTO) -> None | dict[str, Any]:
        pass

    async def find_or_fail(self, entity: EntityDTO) -> dict[str, Any]:
        item = await self.find(entity)

        if not item:
            raise api_exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api_error(
                    type="delete",
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
    async def delete_keys(self, keys: list[str]) -> bool:
        pass

    @abstractmethod
    async def find_by_id(self, id: str) -> dict[str, Any]:
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
        space_name: str,
        branch_name: str | None,
        subpath: str,
        meta: Meta,
        payload: dict[str, Any],
        resource_type: ResourceType | None = ResourceType.content,
    ) -> tuple[str, dict[str, Any]]:
        pass

    @abstractmethod
    async def update(
        self, entity: EntityDTO, meta: Meta, payload: dict[str, Any] = {}
    ) -> bool:
        pass

    @abstractmethod
    async def delete(self, entity: EntityDTO) -> bool:
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

    @abstractmethod
    async def list_indexes(self) -> set[str]:
        pass

    @abstractmethod
    async def drop_index(self, name: str, delete_docs: bool) -> bool:
        pass

    @abstractmethod
    async def create_index(self, name: str, fields: list[Any], **kwargs) -> bool:
        pass

    @abstractmethod
    async def save_lock_doc(
        self, entity: EntityDTO, owner_shortname: str, ttl: int = settings.lock_period
    ) -> LockAction | None:
        pass

    @abstractmethod
    async def get_lock_doc(self, entity: EntityDTO) -> dict[str, Any]:
        pass

    @abstractmethod
    async def delete_lock_doc(self, entity: EntityDTO) -> None:
        pass
