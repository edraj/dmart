import models.api as api
import models.core as core

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Type, TypeVar


MetaChild = TypeVar("MetaChild", bound=core.Meta)

class BaseObjectAdapter(ABC):
    @abstractmethod
    def locators_query(self, query: api.Query) -> tuple[int, list[core.Locator]]:
        pass

    @abstractmethod
    def folder_path(
        self,
        space_name: str,
        subpath: str,
        shortname: str,
    ) -> str:
        pass

    @abstractmethod
    def metapath(
        self,
        space_name: str,
        subpath: str,
        shortname: str,
        class_type: Type[MetaChild],
        schema_shortname: str | None = None,
    ) -> tuple[Path, str]:
        pass

    @abstractmethod
    def payload_path(
        self,
        space_name: str,
        subpath: str,
        class_type: Type[MetaChild],
        schema_shortname: str | None = None,
    ) -> Path:
        pass

    @abstractmethod
    async def load(
        self,
        space_name: str,
        subpath: str,
        shortname: str,
        class_type: Type[MetaChild],
        user_shortname: str | None = None,
        schema_shortname: str | None = None,
    ) -> MetaChild:
        pass

    @abstractmethod
    def load_resource_payload(
        self,
        space_name: str,
        subpath: str,
        filename: str,
        class_type: Type[MetaChild],
        schema_shortname: str | None = None,
    ) -> Any:
        pass

    @abstractmethod
    async def save(
            self, space_name: str, subpath: str, meta: core.Meta
    ):
        pass

    @abstractmethod
    async def create(
        self, space_name: str, subpath: str, meta: core.Meta
    ):
        pass

    @abstractmethod
    async def save_payload(
        self, space_name: str, subpath: str, meta: core.Meta, attachment
    ):
        pass

    @abstractmethod
    async def save_payload_from_json(
        self,
        space_name: str,
        subpath: str,
        meta: core.Meta,
        payload_data: dict[str, Any],
    ):
        pass

    @abstractmethod
    async def update(
        self,
        space_name: str,
        subpath: str,
        meta: core.Meta,
        old_version_flattend: dict,
        new_version_flattend: dict,
        updated_attributes_flattend: list,
        user_shortname: str,
        schema_shortname: str | None = None,
        retrieve_lock_status: bool | None = False,
    ) -> dict:
        pass

    @abstractmethod
    async def store_entry_diff(
        self,
        space_name: str,
        subpath: str,
        shortname: str,
        owner_shortname: str,
        old_version_flattend: dict,
        new_version_flattend: dict,
        updated_attributes_flattend: list,
        resource_type,
    ) -> dict:
        pass

    @abstractmethod
    async def move(
        self,
        space_name: str,
        src_subpath: str,
        src_shortname: str,
        dest_subpath: str | None,
        dest_shortname: str | None,
        meta: core.Meta,
    ):
        pass

    @abstractmethod
    def delete_empty(self, path: Path):
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
    ):
        pass

    @abstractmethod
    async def delete(
        self,
        space_name: str,
        subpath: str,
        meta: core.Meta,
        user_shortname: str,
        schema_shortname: str | None = None,
        retrieve_lock_status: bool | None = False,
    ):
        pass
