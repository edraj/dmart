from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Tuple, Type, TypeVar
from starlette.datastructures import UploadFile
import models.api as api
import models.core as core
from models.enums import LockAction
import io
from models.core import Record
from models.enums import RequestType

MetaChild = TypeVar("MetaChild", bound=core.Meta)


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
    ) -> str:
        pass

    @abstractmethod
    async def save_otp(
        self,
        key: str,
        otp: str,
    ):
        pass
    
    @abstractmethod
    async def otp_created_since(self, key: str) -> int | None:
        pass

    @abstractmethod
    async def get_otp(
        self,
        key: str,
    ):
        pass

    @abstractmethod
    async def delete_otp(self, key):
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
        """Construct the full path of the meta file"""
        pass

    @abstractmethod
    def payload_path(
            self,
            space_name: str,
            subpath: str,
            class_type: Type[MetaChild],
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
            class_type: Type[MetaChild],
            user_shortname: str | None = None,
            schema_shortname: str | None = None,
    ) -> MetaChild | None:
        """Load a Meta Json according to the reuqested Class type"""
        pass

    @abstractmethod
    async def get_latest_history(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
    ) -> Any | None:
        pass

    @abstractmethod
    async def get_entry_by_criteria(self, criteria: dict, table: Any = None) -> core.Record | None:
        pass

    @abstractmethod
    async def query(self, query: api.Query, user_shortname: str | None = None) \
            -> Tuple[int, list[core.Record]]:
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
    async def load_resource_payload(
            self,
            space_name: str,
            subpath: str,
            filename: str,
            class_type: Type[MetaChild],
            schema_shortname: str | None = None,
    ) -> dict[str, Any] | None:
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
            owner_shortname: str,
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
            src_space_name: str,
            src_subpath: str,
            src_shortname: str,
            dest_space_name: str,
            dest_subpath: str,
            dest_shortname: str,
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
            class_type: Type[MetaChild],
    ):
        pass


    @abstractmethod
    async def is_entry_exist(self,
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

    @abstractmethod
    async def lock_handler(
            self, space_name: str, subpath: str, shortname: str, user_shortname: str, action: LockAction
    ) -> dict|None:
        pass

    @abstractmethod
    async def fetch_space(self, space_name: str) -> core.Space | None:
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
        return {}

    @abstractmethod
    async def set_user_session(self, user_shortname: str, token: str) -> bool:
        pass

    @abstractmethod
    async def get_user_session(self, user_shortname: str, token: str) -> Tuple[int, str | None]:
        pass

    @abstractmethod
    async def remove_user_session(self, user_shortname: str) -> bool:
        pass

    @abstractmethod
    async def set_invitation(self, invitation_token: str, invitation_value):
        pass

    @abstractmethod
    async def get_invitation(self, invitation_token: str) -> str | None:
        pass

    @abstractmethod
    async def delete_invitation(self, invitation_token: str) -> bool:
        pass

    @abstractmethod
    async def set_url_shortner(self, token_uuid: str, url: str):
        pass

    @abstractmethod
    async def get_url_shortner(self, token_uuid: str) -> str | None:
        pass

    @abstractmethod
    async def delete_url_shortner(self, token_uuid: str) -> bool:
        pass

    @abstractmethod
    async def delete_url_shortner_by_token(self, invitation_token: str) -> bool:
        pass

    @abstractmethod
    async def clear_failed_password_attempts(self, user_shortname: str) -> bool:
        pass

    @abstractmethod
    async def get_failed_password_attempt_count(self, user_shortname: str) -> int:
        return 0

    @abstractmethod
    async def set_failed_password_attempt_count(self, user_shortname: str, attempt_count: int) -> bool:
        pass

    @abstractmethod
    async def get_spaces(self) -> dict:
        return {}

    @abstractmethod
    async def get_media_attachment(self, space_name: str, subpath: str, shortname: str) -> io.BytesIO | None:
        pass

    @abstractmethod
    async def validate_uniqueness(
        self, space_name: str, record: Record, action: str = RequestType.create, user_shortname=None
    ) -> bool:
        pass

    @abstractmethod
    async def validate_payload_with_schema(
        self,
        payload_data: UploadFile | dict,
        space_name: str,
        schema_shortname: str,
    ):
        pass

    @abstractmethod
    async def get_schema(self, space_name: str, schema_shortname: str, owner_shortname: str) -> dict:
        pass

    @abstractmethod
    async def check_uniqueness(self, unique_fields, search_str, redis_escape_chars) -> dict:
        pass

    @abstractmethod
    async def get_role_permissions(self, role: core.Role) -> list[core.Permission]:
        pass

    @abstractmethod
    async def get_user_roles(self, user_shortname: str) -> dict[str, core.Role]:
        pass

    @abstractmethod
    async def load_user_meta(self, user_shortname: str) -> Any:
        pass

    @abstractmethod
    async def generate_user_permissions(self, user_shortname: str) -> dict:
        pass

    @abstractmethod
    async def get_user_permissions(self, user_shortname: str) -> dict:
        pass

    @abstractmethod
    async def get_user_by_criteria(self, key: str, value: str) -> str | None:
        pass

    @abstractmethod
    async def get_payload_from_event(self, event) -> dict:
        pass

    @abstractmethod
    async def get_user_roles_from_groups(self, user_meta: core.User) -> list:
        pass

    @abstractmethod
    async def drop_index(self, space_name):
        pass

    @abstractmethod
    async def initialize_spaces(self) -> None:
        pass

    @abstractmethod
    async def create_user_premission_index(self) -> None:
        pass

    @abstractmethod
    async def store_modules_to_redis(self, roles, groups, permissions) -> None:
        pass

    @abstractmethod
    async def delete_user_permissions_map_in_redis(self) -> None:
        pass

    @abstractmethod
    async def get_entry_by_var(
            self,
            key: str,
            val: str,
            logged_in_user,
            retrieve_json_payload: bool = False,
            retrieve_attachments: bool = False,
            retrieve_lock_status: bool = False,
    ) -> core.Record | None:
        pass

    @abstractmethod
    async def internal_save_model(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload: dict | None = None
    ):
        pass

    @abstractmethod
    async def internal_sys_update_model(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            updates: dict,
            sync_redis: bool = True,
            payload_dict: dict[str, Any] = {},
    ):
        pass

    @abstractmethod
    async def delete_space(self, space_name, record, owner_shortname):
        pass

    @abstractmethod
    async def get_last_updated_entry(
            self,
            space_name: str,
            schema_names: list,
            retrieve_json_payload: bool,
            logged_in_user: str,
    ):
        pass

    @abstractmethod
    async def get_group_users(self, group_name: str) -> list:
        pass

    @abstractmethod
    async def is_user_verified(self, user_shortname: str | None, identifier: str | None) -> bool:
        pass

    @abstractmethod
    async def test_connection(self):
        pass