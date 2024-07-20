from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypeVar, Any, Tuple

import models.api as api
import models.core as core
from database.create_tables import Locks
from models.enums import LockActions

MetaChild = TypeVar("MetaChild", bound=core.Meta)


class BaseObjectAdapter(ABC):
    @abstractmethod
    def locators_query(self, query: api.Query) -> tuple[int, list[core.Locator]]:
        """Given a query return the total and the locators
        Parameters
        ----------
        query: api.Query
            Query of type subpath

        Returns
        -------
        Total, Locators

        """
        pass

    @abstractmethod
    def folder_path(
        self,
        space_name: str,
        subpath: str,
        shortname: str,
    ):
        pass

    @abstractmethod
    async def get_entry_attachments(
        self,
        subpath: str,
        attachments_path: Path,
        filter_types: list | None = None,
        include_fields: list | None = None,
        filter_shortnames: list | None = None,
        retrieve_json_payload: bool = False,
    ) -> dict:
        pass

    @abstractmethod
    def metapath(self, dto: core.EntityDTO) -> tuple[Path, str]:
        """Construct the full path of the meta file"""
        pass

    @abstractmethod
    def payload_path(self, dto: core.EntityDTO) -> Path:
        """Construct the full path of the meta file"""
        pass

    @abstractmethod
    async def load_or_none(self, dto: core.EntityDTO) -> MetaChild | None:  # type: ignore
        """Load a Meta Json according to the reuqested Class type"""
        pass

    async def get_entry_by_criteria(self, criteria: dict) -> MetaChild | None:  # type: ignore
        pass

    async def query(self, query: api.Query | None = None, user_shortname: str | None = None) -> Tuple[int, list[core.MetaChild]]:
        pass

    @abstractmethod
    async def load(self, dto: core.EntityDTO) -> MetaChild:  # type: ignore
        pass

    @abstractmethod
    async def load_resource_payload(self, dto: core.EntityDTO) -> dict[str, Any]:
        """Load a Meta class payload file"""
        pass

    @abstractmethod
    async def save(
        self, dto: core.EntityDTO, meta: core.Meta, payload_data: dict[str, Any] | None = None
    ):
        """Save Meta Json to respectiv file"""
        pass

    @abstractmethod
    async def create(
        self, dto: core.EntityDTO, meta: core.Meta, payload_data: dict[str, Any] | None = None
    ):
        pass

    @abstractmethod
    async def save_payload(self, dto: core.EntityDTO, meta: core.Meta, attachment):
        pass

    @abstractmethod
    async def save_payload_from_json(
        self, dto: core.EntityDTO, meta: core.Meta, payload_data: dict[str, Any]
    ):
        pass

    @abstractmethod
    async def update(
        self, dto: core.EntityDTO, meta: core.Meta, payload_data: dict[str, Any] | None = None
    ) -> dict:
        """Update the entry, store the difference and return it
        1. load the current file
        3. store meta at the file location
        4. store the diff between old and new file
        """
        pass

    @abstractmethod
    async def store_entry_diff(
        self,
        dto: core.EntityDTO,
        old_meta: core.Meta,
        new_meta: core.Meta,
        old_payload: dict[str, Any] | None = None,
        new_payload: dict[str, Any] | None = None,
    ) -> dict:
        pass

    @abstractmethod
    async def move(
        self,
        dto: core.EntityDTO,
        meta: core.Meta,
        dest_subpath: str | None,
        dest_shortname: str | None,
    ):
        """Move the file that match the criteria given, remove source folder if empty"""
        pass

    @abstractmethod
    def delete_empty(self, path: Path):
        pass

    @abstractmethod
    async def clone(
        self,
        src_dto: core.EntityDTO,
        dest_dto: core.EntityDTO,
    ):
        pass

    @abstractmethod
    async def delete(self, dto: core.EntityDTO):
        """Delete the file that match the criteria given, remove folder if empty"""
        pass

    @abstractmethod
    def is_entry_exist(self, dto: core.EntityDTO) -> bool:
        pass

    async def lock_handler(self, dto: core.EntityDTO, action: LockActions) -> Locks | None:
        pass
