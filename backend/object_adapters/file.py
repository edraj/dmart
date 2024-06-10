from copy import copy
import shutil
import sys
from object_adapters.base import BaseObjectAdapter
from utils.helpers import (
    arr_remove_common,
    branch_path,
    camel_case,
    flatten_all,
    snake_case,
)
from datetime import datetime
from models.enums import ContentType, ResourceType
from utils.internal_error_code import InternalErrorCode
from utils.middleware import get_request_data
from utils.settings import settings
import models.core as core
from typing import TypeVar, Any
import models.api as api
import os
import json
from pathlib import Path
from fastapi import status
import aiofiles
from utils.regex import ATTACHMENT_PATTERN, FILE_PATTERN, FOLDER_PATTERN
from shutil import copy2 as copy_file
from fastapi.logger import logger

MetaChild = TypeVar("MetaChild", bound=core.Meta)


class FileAdapter(BaseObjectAdapter):
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

        locators: list[core.Locator] = []
        total: int = 0
        match query.type:
            case api.QueryType.subpath:
                path = (
                        settings.spaces_folder
                        / query.space_name
                        / branch_path(query.branch_name)
                        / query.subpath
                )

                if query.include_fields is None:
                    query.include_fields = []

                # Gel all matching entries
                meta_path = path / ".dm"
                if not meta_path.is_dir():
                    return total, locators

                path_iterator = os.scandir(meta_path)
                for entry in path_iterator:
                    if not entry.is_dir():
                        continue

                    subpath_iterator = os.scandir(entry)
                    for one in subpath_iterator:
                        # for one in path.glob(entries_glob):
                        match = FILE_PATTERN.search(str(one.path))
                        if not match or not one.is_file():
                            continue

                        total += 1
                        if len(locators) >= query.limit or total < query.offset:
                            continue

                        shortname = match.group(1)
                        resource_name = match.group(2).lower()
                        if (
                                query.filter_types
                                and ResourceType(resource_name) not in query.filter_types
                        ):
                            continue

                        if (
                                query.filter_shortnames
                                and shortname not in query.filter_shortnames
                        ):
                            continue

                        locators.append(
                            core.Locator(
                                space_name=query.space_name,
                                branch_name=query.branch_name,
                                subpath=query.subpath,
                                shortname=shortname,
                                type=ResourceType(resource_name),
                            )
                        )

                # Get all matching sub folders
                subfolders_iterator = os.scandir(path)
                for one in subfolders_iterator:
                    if not one.is_dir():
                        continue

                    subfolder_meta = Path(one.path + "/.dm/meta.folder.json")

                    match = FOLDER_PATTERN.search(str(subfolder_meta))

                    if not match or not subfolder_meta.is_file():
                        continue

                    total += 1
                    if len(locators) >= query.limit or total < query.offset:
                        continue

                    shortname = match.group(1)
                    if query.filter_shortnames and shortname not in query.filter_shortnames:
                        continue

                    locators.append(
                        core.Locator(
                            space_name=query.space_name,
                            branch_name=query.branch_name,
                            subpath=query.subpath,
                            shortname=shortname,
                            type=core.ResourceType.folder,
                        )
                    )

        return total, locators

    def folder_path(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            branch_name: str | None = settings.default_branch,
    ):
        if branch_name:
            return (
                f"{settings.spaces_folder}/{space_name}/{branch_name}/{subpath}/{shortname}"
            )
        else:
            return f"{settings.spaces_folder}/{space_name}{subpath}/{shortname}"

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
                print(f"{attachments_file=}")
                match = ATTACHMENT_PATTERN.search(str(attachments_file.path))
                print(f"{match=}")
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
                print(f"{attachments_file=}")
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

    def metapath(self, dto: core.EntityDTO) -> tuple[Path, str]:
        """Construct the full path of the meta file"""
        path = settings.spaces_folder / dto.space_name / branch_path(dto.branch_name)

        filename = ""
        subpath = copy(dto.subpath)
        if subpath[0] == "/":
            subpath = f".{subpath}"

        if issubclass(dto.class_type, core.Folder):
            path = path / subpath / dto.shortname / ".dm"
            filename = f"meta.{dto.class_type.__name__.lower()}.json"
        elif issubclass(dto.class_type, core.Space):
            path = settings.spaces_folder / dto.space_name / ".dm"
            filename = "meta.space.json"
        elif issubclass(dto.class_type, core.Attachment):
            [parent_subpath, parent_name] = subpath.rsplit("/", 1)
            # schema_shortname = "." + schema_shortname if schema_shortname else ""
            attachment_folder = (
                f"{parent_name}/attachments.{dto.class_type.__name__.lower()}"
            )
            path = path / parent_subpath / ".dm" / attachment_folder
            filename = f"meta.{dto.shortname}.json"
        elif issubclass(dto.class_type, core.History):
            [parent_subpath, parent_name] = subpath.rsplit("/", 1)
            path = path / parent_subpath / ".dm" / f"{parent_name}/history"
            filename = f"{dto.shortname}.json"
        elif issubclass(dto.class_type, core.Branch):
            path = settings.spaces_folder / dto.space_name / dto.shortname / ".dm"
            filename = "meta.branch.json"
        else:
            path = path / subpath / ".dm" / dto.shortname
            filename = f"meta.{snake_case(dto.class_type.__name__)}.json"
        return path, filename

    def payload_path(self, dto: core.EntityDTO) -> Path:
        """Construct the full path of the meta file"""
        path = settings.spaces_folder / dto.space_name / branch_path(dto.branch_name)

        subpath = copy(dto.subpath)
        if subpath[0] == "/":
            subpath = f".{subpath}"
        if issubclass(dto.class_type, core.Attachment):
            [parent_subpath, parent_name] = subpath.rsplit("/", 1)
            # schema_shortname = (
            #     "." + dto.schema_shortname if dto.schema_shortname != "meta" else ""
            # )
            schema_shortname = ""
            attachment_folder = f"{parent_name}/attachments{schema_shortname}.{dto.class_type.__name__.lower()}"
            path = path / parent_subpath / ".dm" / attachment_folder
        else:
            path = path / subpath
        return path

    async def load_or_none(self, dto: core.EntityDTO) -> MetaChild | None:  # type: ignore
        """Load a Meta Json according to the reuqested Class type"""
        path, filename = self.metapath(dto)
        if not (path / filename).is_file():
            # Remove the folder
            if path.is_dir() and len(os.listdir(path)) == 0:
                shutil.rmtree(path)

            return None

        path /= filename
        async with aiofiles.open(path, "r") as file:
            content = await file.read()
            try:
                return dto.class_type.model_validate_json(content)  # type: ignore
            except Exception as e:
                logger.error(f"Failed parsing an entry. {dto=}. Error: {e.args}")
                return None

    async def load(self, dto: core.EntityDTO) -> MetaChild:  # type: ignore
        meta: core.Meta | None = await self.load_or_none(dto)  # type: ignore
        if not meta:
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(
                    type="db",
                    code=InternalErrorCode.OBJECT_NOT_FOUND,
                    message=f"Request object is not available @{dto.space_name}/{dto.subpath}/{dto.shortname} {dto.resource_type=} {dto.schema_shortname=}",
                ),
            )

        return meta

    async def load_resource_payload(self, dto: core.EntityDTO) -> dict[str, Any]:
        """Load a Meta class payload file"""

        path = self.payload_path(dto)

        meta: core.Meta = await self.load(dto)

        if not meta:
            return {}

        if not meta.payload or not isinstance(meta.payload.body, str):
            return {}

        path /= meta.payload.body
        if not path.is_file():
            return {}

        async with aiofiles.open(path, "r") as file:
            content = await file.read()
            return json.loads(content)

    async def save(
            self, dto: core.EntityDTO, meta: core.Meta, payload_data: dict[str, Any] | None = None
    ):
        """Save Meta Json to respectiv file"""
        path, filename = self.metapath(dto)

        if not path.is_dir():
            os.makedirs(path)

        async with aiofiles.open(path / filename, "w") as file:
            await file.write(meta.model_dump_json(exclude_none=True))

        if payload_data:
            payload_file_path = self.payload_path(dto)

            payload_filename = f"{meta.shortname}.json"

            async with aiofiles.open(payload_file_path / payload_filename, "w") as file:
                await file.write(json.dumps(payload_data))

    async def create(
            self, dto: core.EntityDTO, meta: core.Meta, payload_data: dict[str, Any] | None = None
    ):
        path, filename = self.metapath(dto)

        if (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create",
                    code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
                    message="already exists",
                ),
            )

        await self.save(dto, meta, payload_data)

    async def save_payload(self, dto: core.EntityDTO, meta: core.Meta, attachment):
        path, filename = self.metapath(dto)
        payload_file_path = self.payload_path(dto)
        payload_filename = meta.shortname + Path(attachment.filename).suffix

        if not (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create",
                    code=InternalErrorCode.MISSING_METADATA,
                    message="metadata is missing",
                ),
            )

        async with aiofiles.open(payload_file_path / payload_filename, "wb") as file:
            content = await attachment.read()
            await file.write(content)

    async def save_payload_from_json(
            self, dto: core.EntityDTO, meta: core.Meta, payload_data: dict[str, Any]
    ):
        path, filename = self.metapath(dto)
        payload_file_path = self.payload_path(dto)

        payload_filename = f"{meta.shortname}.json"

        if not (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create",
                    code=InternalErrorCode.MISSING_METADATA,
                    message="metadata is missing",
                ),
            )

        async with aiofiles.open(payload_file_path / payload_filename, "w") as file:
            await file.write(json.dumps(payload_data))

    async def update(
            self, dto: core.EntityDTO, meta: core.Meta, payload_data: dict[str, Any] | None = None
    ) -> dict:
        """Update the entry, store the difference and return it
        1. load the current file
        3. store meta at the file location
        4. store the diff between old and new file
        """
        old_meta: core.Meta = await self.load(dto)
        old_payload = await self.load_resource_payload(dto)

        meta.updated_at = datetime.now()

        await self.save(dto, meta, payload_data)

        if (
                meta.payload
                and meta.payload.body
                and meta.payload.content_type == ContentType.json
                and not payload_data
        ):
            payload_data = await self.load_resource_payload(dto)

        history_diff = await self.store_entry_diff(
            dto=dto,
            old_meta=old_meta,
            new_meta=meta,
            old_payload=old_payload,
            new_payload=payload_data,
        )

        return history_diff

    async def store_entry_diff(
            self,
            dto: core.EntityDTO,
            old_meta: core.Meta,
            new_meta: core.Meta,
            old_payload: dict[str, Any] | None = None,
            new_payload: dict[str, Any] | None = None,
    ) -> dict:

        old_flattened = flatten_all(old_meta.model_dump(exclude_none=True))
        if old_payload:
            old_flattened.update(flatten_all(old_payload))

        new_flattened = flatten_all(new_meta.model_dump(exclude_none=True))
        if new_payload:
            new_flattened.update(flatten_all(new_payload))

        diff_keys = list(old_flattened.keys())
        diff_keys.extend(list(new_flattened.keys()))
        history_diff = {}
        for key in set(diff_keys):
            if key in ["updated_at"]:
                continue
            # if key in updated_attributes_flattend:
            old = copy(old_flattened.get(key, "null"))

            new = copy(new_flattened.get(key, "null"))

            if old != new:
                if isinstance(old, list) and isinstance(new, list):
                    old, new = arr_remove_common(old, new)
                history_diff[key] = {
                    "old": old,
                    "new": new,
                }
        if not history_diff:
            return {}

        history_obj = core.History(
            shortname="history",
            owner_shortname=dto.user_shortname or "__system__",
            timestamp=datetime.now(),
            request_headers=get_request_data().get("request_headers", {}),
            diff=history_diff,
        )
        history_path = (
                settings.spaces_folder / dto.space_name / branch_path(dto.branch_name)
        )

        if dto.subpath == "/" and dto.resource_type == core.Space:
            history_path = Path(f"{history_path}/.dm")
        else:
            if issubclass(dto.class_type, core.Attachment):
                history_path = Path(f"{history_path}/.dm/{dto.subpath}")
            else:
                if dto.subpath == "/":
                    history_path = Path(f"{history_path}/.dm/{dto.shortname}")
                else:
                    history_path = Path(
                        f"{history_path}/{dto.subpath}/.dm/{dto.shortname}"
                    )

        if not os.path.exists(history_path):
            os.makedirs(history_path)

        async with aiofiles.open(
                f"{history_path}/history.jsonl",
                "a",
        ) as events_file:
            await events_file.write(f"{history_obj.model_dump_json()}\n")

        return history_diff

    async def move(
            self,
            dto: core.EntityDTO,
            meta: core.Meta,
            dest_subpath: str | None,
            dest_shortname: str | None,
    ):
        """Move the file that match the criteria given, remove source folder if empty"""
        dest_dto = copy(dto)

        if dest_subpath:
            dest_dto.subpath = dest_subpath
        if dest_shortname:
            dest_dto.shortname = dest_shortname

        src_path, src_filename = self.metapath(dto)
        dest_path, dest_filename = self.metapath(dest_dto)

        meta_updated = False
        dest_path_without_dm = dest_path
        if dest_shortname:
            meta.shortname = dest_shortname
            meta_updated = True

        if src_path.parts[-1] == ".dm":
            src_path = Path("/".join(src_path.parts[:-1]))

        if dest_path.parts[-1] == ".dm":
            dest_path_without_dm = Path("/".join(dest_path.parts[:-1]))

        if dest_path_without_dm.is_dir() and len(os.listdir(dest_path_without_dm)):
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(
                    type="move",
                    code=InternalErrorCode.NOT_ALLOWED_LOCATION,
                    message="The destination folder is not empty",
                ),
            )

        # Create dest dir if there's a change in the subpath AND the shortname
        # and the subpath shortname folder doesn't exist,
        if (
                dto.shortname != dest_shortname
                and dto.subpath != dest_subpath
                and not os.path.isdir(dest_path_without_dm)
        ):
            os.makedirs(dest_path_without_dm)

        os.rename(src=src_path, dst=dest_path_without_dm)

        # Move payload file with the meta file
        if (
                meta.payload
                and meta.payload.content_type != ContentType.text
                and isinstance(meta.payload.body, str)
        ):
            src_payload_file_path = self.payload_path(dto) / meta.payload.body
            meta.payload.body = meta.shortname + "." + meta.payload.body.split(".")[-1]
            dist_payload_file_path = self.payload_path(dest_dto) / meta.payload.body
            if src_payload_file_path.is_file():
                os.rename(src=src_payload_file_path, dst=dist_payload_file_path)

        if meta_updated:
            async with aiofiles.open(dest_path / dest_filename, "w") as opened_file:
                await opened_file.write(meta.model_dump_json(exclude_none=True))

        # Delete Src path if empty
        if src_path.parent.is_dir():
            self.delete_empty(src_path)

    def delete_empty(self, path: Path):
        if path.is_dir() and len(os.listdir(path)) == 0:
            os.removedirs(path)

        if path.parent.is_dir() and len(os.listdir(path.parent)) == 0:
            self.delete_empty(path.parent)

    async def clone(
            self,
            src_dto: core.EntityDTO,
            dest_dto: core.EntityDTO,
    ):

        meta_obj: core.Meta = await self.load(src_dto)

        src_path, src_filename = self.metapath(src_dto)
        dest_path, dest_filename = self.metapath(dest_dto)

        # Create dest dir if not exist
        if not os.path.isdir(dest_path):
            os.makedirs(dest_path)

        copy_file(src=src_path / src_filename, dst=dest_path / dest_filename)

        # Move payload file with the meta file
        if (
                meta_obj.payload
                and meta_obj.payload.content_type != ContentType.text
                and isinstance(meta_obj.payload.body, str)
        ):
            src_payload_file_path = self.payload_path(src_dto) / meta_obj.payload.body
            dist_payload_file_path = self.payload_path(dest_dto) / meta_obj.payload.body
            copy_file(src=src_payload_file_path, dst=dist_payload_file_path)

    async def delete(self, dto: core.EntityDTO):
        """Delete the file that match the criteria given, remove folder if empty"""

        path, filename = self.metapath(dto)
        if not path.is_dir() or not (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(
                    type="delete",
                    code=InternalErrorCode.OBJECT_NOT_FOUND,
                    message=f"Request object is not available {(path / filename)}",
                ),
            )

        meta: core.Meta = await self.load(dto)

        pathname = path / filename
        if pathname.is_file():
            os.remove(pathname)

            # Delete payload file
            if meta.payload and meta.payload.content_type not in ContentType.inline_types():
                payload_file_path = self.payload_path(dto) / str(meta.payload.body)
                if payload_file_path.exists() and payload_file_path.is_file():
                    os.remove(payload_file_path)

        history_path = (
                f"{settings.spaces_folder}/{dto.space_name}/{branch_path(dto.branch_name)}"
                + f"{dto.subpath}/.dm/{meta.shortname}"
        )

        if path.is_dir() and (
                not isinstance(meta, core.Attachment) or len(os.listdir(path)) == 0
        ):
            shutil.rmtree(path)
            # in case of folder the path = {folder_name}/.dm
            if isinstance(meta, core.Folder) and path.parent.is_dir():
                shutil.rmtree(path.parent)
            if isinstance(meta, core.Folder) and Path(history_path).is_dir():
                shutil.rmtree(history_path)

    def is_entry_exist(self, dto: core.EntityDTO) -> bool:
        subpath = copy(dto.subpath)
        if subpath[0] == "/":
            subpath = f".{subpath}"

        payload_file = (
                settings.spaces_folder
                / dto.space_name
                / branch_path(dto.branch_name)
                / subpath
                / f"{dto.shortname}.json"
        )
        if payload_file.is_file():
            return True

        for r_type in ResourceType:
            # Spaces compared with each others only
            if r_type == ResourceType.space and r_type != dto.resource_type:
                continue
            meta_path, meta_file = self.metapath(dto)
            if (meta_path / meta_file).is_file():
                return True

        return False
