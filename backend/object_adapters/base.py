from abc import ABC, abstractmethod
import sys
from utils.helpers import (
    camel_case,
)
from models.enums import ContentType, ResourceType
from utils.settings import settings
import models.core as core
from typing import TypeVar, Any
import models.api as api
import os
import json
from pathlib import Path
import aiofiles
from utils.regex import ATTACHMENT_PATTERN
from fastapi.logger import logger


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
        branch_name: str | None = settings.default_branch,
    ):
        pass


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
                match = ATTACHMENT_PATTERN.search(str(attachments_file.path))
                if not match or not attachments_file.is_file():
                    continue

                attach_shortname = match.group(2)
                attach_resource_name = match.group(1).lower()
                if filter_shortnames and attach_shortname not in filter_shortnames:
                    continue

                if filter_types and ResourceType(attach_resource_name) not in filter_types:
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
                            f"Bad attachment ... {attachments_file.path=}. Resource class: {resource_class}"
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
