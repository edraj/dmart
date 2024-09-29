# type: ignore
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Tuple, Type

import models.api as api
import models.core as core
from models.enums import LockAction


class BaseDataAdapter(ABC):
    @abstractmethod
    def locators_query(self, query: api.Query) -> tuple[int, list[core.Locator]]:
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
    def metapath(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[core.Meta],
            schema_shortname: str | None = None,
    ) -> tuple[Path, str]:
        """Construct the full path of the meta file"""
        pass

    @abstractmethod
    def payload_path(
            self,
            space_name: str,
            subpath: str,
            class_type: Type[core.Meta],
            schema_shortname: str | None = None,
    ) -> Path:
        """Construct the full path of the meta file"""
        pass

    @abstractmethod
    async def load_or_none(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type,
            user_shortname: str | None = None,
            schema_shortname: str | None = None,
    ) -> core.Meta | None:  # type: ignore
        """Load a Meta Json according to the reuqested Class type"""
        pass

    async def get_entry_by_criteria(self, criteria: dict, table: Any = None) -> core.Meta:  # type: ignore
        pass

    async def query(self, query: api.Query | None = None, user_shortname: str | None = None) \
            -> Tuple[int, list[core.Record]]:
        pass

    @abstractmethod
    async def load(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[core.Meta],
            user_shortname: str | None = None,
            schema_shortname: str | None = None,
    ) -> core.Meta:  # type: ignore
        pass

    @abstractmethod
    async def load_resource_payload(
            self,
            space_name: str,
            subpath: str,
            filename: str,
            class_type: Type[core.Meta],
            schema_shortname: str | None = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def save(
            self, space_name: str, subpath: str, meta: core.Meta
    ):
        """Save Meta Json to respectiv file"""
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
    async def update_payload(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload_data: dict[str, Any],
            owner_shortname: str = None,
    ):
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
        """Move the file that match the criteria given, remove source folder if empty"""
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
            class_type: Type[core.Meta],
    ):
        pass


    @abstractmethod
    def is_entry_exist(self,
                       space_name: str,
                       subpath: str,
                       shortname: str,
                       resource_type: core.ResourceType,
                       schema_shortname: str | None = None, ) -> bool:
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

    async def lock_handler(
            self, space_name: str, subpath: str, shortname: str, user_shortname: str, action: LockAction
    ) -> dict | None:
        pass

    async def fetch_space(self, space_name: str) -> core.Space | None:
        pass

    async def get_entry_attachments(
            sefl,
            subpath: str,
            attachments_path: Path,
            filter_types: list | None = None,
            include_fields: list | None = None,
            filter_shortnames: list | None = None,
            retrieve_json_payload: bool = False,
    ) -> dict:
        pass

    async def set_sql_active_session(self, user_shortname: str, token: str) -> bool:
        pass

    async def set_sql_user_session(self, user_shortname: str, token: str) -> bool:
        pass

    async def get_sql_active_session(self, user_shortname: str):
        pass

    async def get_sql_user_session(self, user_shortname: str):
        pass

    async def remove_sql_active_session(self, user_shortname: str) -> bool:
        pass

    async def remove_sql_user_session(self, user_shortname: str) -> bool:
        pass

    async def set_invitation(self, user_shortname: str, token):
        pass

    async def get_invitation_token(self, token: str):
        pass

    async def set_url_shortner(self, token_uuid: str, url: str) -> bool:
        pass

    async def get_url_shortner(self, token_uuid: str) -> str:
        pass

    async def delete_url_shortner(self, token_uuid: str) -> bool:
        pass

    async def clear_failed_password_attempts(self, user_shortname: str) -> bool:
        pass

    async def get_failed_password_attempt_count(self, user_shortname: str) -> int:
        pass

    async def set_failed_password_attempt_count(self, user_shortname: str, attempt_count: int) -> bool:
        pass

    async def get_spaces(self) -> dict:
        pass
