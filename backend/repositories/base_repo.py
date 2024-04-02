

from abc import ABC, abstractmethod
from typing import Any

from models.api import Query, Exception as api_exception, Error as api_error
from models.core import EntityDTO, Meta, Permission, Role, User
from models.enums import ResourceType
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
from fastapi import status


class BaseRepo(ABC):
    
    @abstractmethod
    async def get_user(self, user_shortname: str) -> User:
        pass
    
    @abstractmethod
    def generate_user_acl_doc_id(self, user_shortname: str) -> str:
        pass
    
    @abstractmethod
    async def get_user_acl_doc(self, user_shortname: str) -> dict[str, Any]:
        pass
    
    @abstractmethod
    async def generate_user_acl_doc(self, user_shortname: str) -> dict[str, Any]:
        pass
    
    @abstractmethod
    async def get_user_roles(self, user_shortname: str) -> dict[str, Role]:
        pass
    
    @abstractmethod
    async def get_user_roles_from_groups(self, user_meta: User) -> list[Role]:
        pass
    
    @abstractmethod
    async def get_role_permissions(self, role: Role) -> list[Permission]:
        pass
    
    @abstractmethod
    async def user_query_policies(self, user_shortname: str, space: str, subpath: str) -> list[str]:
        pass
    
    
    @abstractmethod
    async def search(self, query: Query, user_shortname: str) -> tuple[list[Any], int]:
        pass
    
    @abstractmethod
    async def find(self, entity: EntityDTO) -> None | Meta:
        pass

    async def find_or_fail(self, entity: EntityDTO) -> Meta:
        item = await self.find(entity)
        
        if not item:
            raise api_exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api_error(
                    type="delete", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"),
            )
        
        return item
            
    
    @abstractmethod
    async def find_by_id(self, id: str) -> Meta:
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
        resource_type: ResourceType,
        branch_name: str | None = settings.default_branch,
    ) -> bool:
        pass

