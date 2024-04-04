from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
import sys
from typing import Any

import aiofiles

from db.base_db import BaseDB
from models.api import Query, Exception as api_exception, Error as api_error
from models.core import EntityDTO, Group, Meta, Permission, Role, User
from models.enums import ContentType, LockAction, ResourceType
from utils.helpers import camel_case
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
from fastapi import status
from fastapi.logger import logger
from utils import regex


class BaseRepo(ABC):
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

    def __init__(self, db: BaseDB) -> None:
        self.db = db

    # ================================================================================
    # Core CRUD Functions
    # ================================================================================
    @abstractmethod
    async def search(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[dict[str, Any]]]:
        pass

    async def free_search(
        self, index_name: str, search_str: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        return await self.db.free_search(index_name, search_str, limit, offset)

    async def entity_doc_id(self, entity: EntityDTO) -> str:
        return await self.db.entity_doc_id(entity)

    @abstractmethod
    async def find(self, entity: EntityDTO) -> None | Meta:
        pass

    async def find_or_fail(self, entity: EntityDTO) -> Meta:
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

    async def find_by_id(self, id: str) -> dict[str, Any]:
        return await self.db.find_by_id(id)

    async def find_payload_data_by_id(
        self, id: str, resource_type: ResourceType
    ) -> dict[str, Any]:
        return await self.db.find_payload_data_by_id(id, resource_type)

    async def set_key(self, key: str, value: str, ex=None, nx: bool = False) -> bool:
        return await self.db.set_key(key, value, ex, nx)

    async def delete_keys(self, keys: list[str]) -> bool:
        return await self.db.delete_keys(keys)

    async def find_key(self, key: str) -> str | None:
        return await self.db.find_key(key)

    @abstractmethod
    async def create(self, entity: EntityDTO, meta: Meta) -> None:
        pass

    @abstractmethod
    async def generate_payload_string(
        self,
        entity: EntityDTO,
        payload: dict[str, Any],
    ) -> str:
        pass

    async def save_at_id(self, id: str, doc: dict[str, Any] = {}) -> bool:
        return await self.db.save_at_id(id, doc)

    async def update(
        self, entity: EntityDTO, meta: Meta, payload: dict[str, Any] = {}
    ) -> bool:
        return await self.db.update(entity, meta, payload)

    async def delete(self, entity: EntityDTO) -> bool:
        return await self.db.delete(entity)

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
        return await self.db.move(
            space_name,
            src_subpath,
            src_shortname,
            dest_subpath,
            dest_shortname,
            meta,
            branch_name,
        )

    # @abstractmethod
    # async def clone(
    #     self,
    #     src_space: str,
    #     dest_space: str,
    #     src_subpath: str,
    #     src_shortname: str,
    #     dest_subpath: str,
    #     dest_shortname: str,
    #     resource_type: ResourceType,
    #     branch_name: str | None = settings.default_branch,
    # ) -> bool:
    #     pass

    async def get_entry_attachments(
        self,
        subpath: str,
        attachments_path: Path,
        branch_name: str | None = None,
        filter_types: list | None = None,
        include_fields: list | None = None,
        filter_shortnames: list | None = None,
        retrieve_json_payload: bool = False,
    ) -> dict:
        if not attachments_path.is_dir():
            return {}
        attachments_iterator = os.scandir(attachments_path)
        attachments_dict: dict[str, list] = {}
        for attachment_entry in attachments_iterator:
            # TODO: Filter types on the parent attachment type folder layer
            if not attachment_entry.is_dir():
                continue

            attachments_files = os.scandir(attachment_entry)
            for attachments_file in attachments_files:
                match = regex.ATTACHMENT_PATTERN.search(str(attachments_file.path))
                if not match or not attachments_file.is_file():
                    continue

                attach_shortname = match.group(2)
                attach_resource_name = match.group(1).lower()
                if filter_shortnames and attach_shortname not in filter_shortnames:
                    continue

                if (
                    filter_types
                    and ResourceType(attach_resource_name) not in filter_types
                ):
                    continue

                resource_class = getattr(
                    sys.modules["models.core"], camel_case(attach_resource_name)
                )
                resource_obj = None
                async with aiofiles.open(attachments_file, "r") as meta_file:
                    try:
                        resource_obj = resource_class.model_validate_json(
                            await meta_file.read()
                        )
                    except Exception as e:
                        raise Exception(
                            f"Bad attachment ... {attachments_file=}"
                        ) from e

                resource_record_obj = resource_obj.to_record(
                    subpath, attach_shortname, include_fields, branch_name
                )
                if (
                    retrieve_json_payload
                    and resource_obj
                    and resource_record_obj
                    and resource_obj.payload
                    and resource_obj.payload.content_type
                    and resource_obj.payload.content_type == ContentType.json
                    and Path(
                        f"{attachment_entry.path}/{resource_obj.payload.body}"
                    ).is_file()
                ):
                    async with aiofiles.open(
                        f"{attachment_entry.path}/{resource_obj.payload.body}", "r"
                    ) as payload_file_content:
                        resource_record_obj.attributes["payload"].body = json.loads(
                            await payload_file_content.read()
                        )

                if attach_resource_name in attachments_dict:
                    attachments_dict[attach_resource_name].append(resource_record_obj)
                else:
                    attachments_dict[attach_resource_name] = [resource_record_obj]
            attachments_files.close()
        attachments_iterator.close()

        # SORT ALTERATION ATTACHMENTS BY ALTERATION.CREATED_AT
        for attachment_name, attachments in attachments_dict.items():
            try:
                if attachment_name == ResourceType.alteration:
                    attachments_dict[attachment_name] = sorted(
                        attachments, key=lambda d: d.attributes["created_at"]
                    )
            except Exception as e:
                logger.error(
                    f"Invalid attachment entry:{attachments_path/attachment_name}. Error: {e.args}"
                )

        return attachments_dict

    # ================================== END =========================================

    # ================================================================================
    # Locking Functions
    # ================================================================================
    async def save_lock_doc(
        self, entity: EntityDTO, owner_shortname: str, ttl: int = settings.lock_period
    ) -> LockAction | None:
        return await self.db.save_lock_doc(entity, owner_shortname, ttl)

    async def get_lock_doc(self, entity: EntityDTO) -> dict[str, Any]:
        return await self.db.get_lock_doc(entity)

    async def delete_lock_doc(self, entity: EntityDTO) -> dict[str, Any]:
        return await self.db.get_lock_doc(entity)

    # ================================== END =========================================

    # ================================================================================
    # Indexes Functions
    # ================================================================================
    async def is_index_exist(self, name: str) -> bool:
        return name in (await self.db.list_indexes())

    async def list_indexes(self):
        return await self.db.list_indexes()

    async def drop_index(self, name: str, delete_docs: bool) -> bool:
        return await self.db.drop_index(name, delete_docs)

    async def create_index(self, name: str, fields: list[Any], **kwargs) -> bool:
        return await self.db.create_index(name, fields, **kwargs)

    async def create_index_if_not_exist(
        self, name: str, fields: list[Any], **kwargs
    ) -> bool:
        if await self.is_index_exist(name):
            return True

        return await self.create_index(name, fields, **kwargs)

    async def create_index_drop_existing(
        self, name: str, fields: list[Any], **kwargs
    ) -> bool:
        if await self.is_index_exist(name):
            await self.drop_index(name, kwargs.get("delete_docs", True))

        return await self.create_index(name, fields, **kwargs)

    # ================================== END =========================================

    # ================================================================================
    # Custom Functions
    # ================================================================================
    @abstractmethod
    async def get_user(self, user_shortname: str) -> User:
        pass

    @abstractmethod
    def generate_user_permissions_doc_id(self, user_shortname: str) -> str:
        pass

    @abstractmethod
    async def get_user_permissions_doc(self, user_shortname: str) -> dict[str, Any]:
        pass

    @abstractmethod
    async def generate_user_permissions_doc(
        self, user_shortname: str
    ) -> dict[str, Any]:
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
    async def user_query_policies(
        self, user_shortname: str, space: str, subpath: str
    ) -> list[str]:
        pass
