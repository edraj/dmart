from abc import ABC, abstractmethod
from typing import Any, Type

from models.api import Query, Exception as api_exception, Error as api_error
from models.core import EntityDTO, Meta, MetaChild, Record, User
from models.enums import SortType
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
        filters: dict[str, str | list],
        limit: int,
        offset: int,
        exact_subpath: bool = False,
        sort_type: SortType = SortType.ascending,
        sort_by: str | None = None,
        highlight_fields: list[str] | None = None,
        schema_name: str = "meta",
        return_fields: list = [],
    ) -> dict[str, Any]:
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
                    type="delete", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"),
            )
        
        return item
            
    
    @abstractmethod
    async def find_by_id(self, id: str) -> dict[str, Any]:
        pass

    @abstractmethod
    async def save_at_id(self, id: str, doc: dict[str, Any] = {}) -> bool:
        pass
    
    @abstractmethod
    async def create(self, entity: EntityDTO, meta: Meta, payload: dict[str, Any] = {}) -> bool:
        pass

    @abstractmethod
    async def update(self, entity: EntityDTO, meta: Meta, payload: dict[str, Any] = {}) -> bool:
        pass

    @abstractmethod
    async def delete(self, entity: EntityDTO, meta: Meta)-> bool:
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
    async def clone(
        self,
        src_space: str,
        dest_space: str,
        src_subpath: str,
        src_shortname: str,
        dest_subpath: str,
        dest_shortname: str,
        class_type: Type[MetaChild],
        branch_name: str | None = settings.default_branch,
    ) -> bool:
        pass
    
    