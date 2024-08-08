# type: ignore
import json
import os
import shutil
import sys
from copy import copy
from datetime import datetime
from pathlib import Path
from shutil import copy2 as copy_file
from typing import Type, Any, Tuple

import aiofiles
from fastapi import status
from fastapi.logger import logger

import models.api as api
import models.core as core
from utils import regex
from utils.spaces import get_spaces
from .base_data_adapter import BaseDataAdapter
from models.enums import ContentType, ResourceType, LockAction
from utils.helpers import arr_remove_common, read_jsonl_file, snake_case, camel_case
from utils.internal_error_code import InternalErrorCode
from utils.middleware import get_request_data
from utils.redis_services import RedisServices
from utils.regex import FILE_PATTERN, FOLDER_PATTERN
from utils.settings import settings


def sort_alteration(attachments_dict, attachments_path):
    for attachment_name, attachments in attachments_dict.items():
        try:
            if attachment_name == ResourceType.alteration:
                attachments_dict[attachment_name] = sorted(
                    attachments, key=lambda d: d.attributes["created_at"]
                )
        except Exception as e:
            logger.error(
                f"Invalid attachment entry:{attachments_path / attachment_name}.\
            Error: {e.args}"
            )


def is_file_check(retrieve_json_payload, resource_obj, resource_record_obj, attachment_entry):
    return (
        retrieve_json_payload
        and resource_obj
        and resource_record_obj
        and resource_obj.payload
        and resource_obj.payload.content_type
        and resource_obj.payload.content_type == ContentType.json
        and Path(
            f"{attachment_entry.path}/{resource_obj.payload.body}"
        ).is_file()
    )


def locator_query_path_sub_folder(locators, query, subpath_iterator, total):
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
                subpath=query.subpath,
                shortname=shortname,
                type=ResourceType(resource_name),
            )
        )
    return locators, total


def locator_query_sub_folder(locators, query, subfolders_iterator, total):
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
                subpath=query.subpath,
                shortname=shortname,
                type=core.ResourceType.folder,
            )
        )

    return locators, total


class FileAdapter(BaseDataAdapter):
    def locators_query(self, query: api.Query) -> tuple[int, list[core.Locator]]:
        locators: list[core.Locator] = []
        total: int = 0
        if query.type != api.QueryType.subpath:
            return total, locators
        path = (
            settings.spaces_folder
            / query.space_name
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
            locators, total = locator_query_path_sub_folder(locators, query, subpath_iterator, total)

        # Get all matching sub folders
        subfolders_iterator = os.scandir(path)
        locators, total = locator_query_sub_folder(locators, query, subfolders_iterator, total)

        return total, locators

    def folder_path(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
    ):
        return f"{settings.spaces_folder}/{space_name}/{subpath}/{shortname}"


    def metapath(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[core.Meta],
            schema_shortname: str | None = None,
    ) -> tuple[Path, str]:
        """Construct the full path of the meta file"""
        path = settings.spaces_folder / space_name

        filename = ""
        if subpath[0] == "/":
            subpath = f".{subpath}"
        if issubclass(class_type, core.Folder):
            path = path / subpath / shortname / ".dm"
            filename = f"meta.{class_type.__name__.lower()}.json"
        elif issubclass(class_type, core.Space):
            path = settings.spaces_folder / space_name / ".dm"
            filename = "meta.space.json"
        elif issubclass(class_type, core.Attachment):
            [parent_subpath, parent_name] = subpath.rsplit("/", 1)
            # schema_shortname = "." + schema_shortname if schema_shortname else ""
            attachment_folder = (
                f"{parent_name}/attachments.{class_type.__name__.lower()}"
            )
            path = path / parent_subpath / ".dm" / attachment_folder
            filename = f"meta.{shortname}.json"
        elif issubclass(class_type, core.History):
            [parent_subpath, parent_name] = subpath.rsplit("/", 1)
            path = path / parent_subpath / ".dm" / f"{parent_name}/history"
            filename = f"{shortname}.json"
        else:
            path = path / subpath / ".dm" / shortname
            filename = f"meta.{snake_case(class_type.__name__)}.json"
        return path, filename

    def payload_path(
            self,
            space_name: str,
            subpath: str,
            class_type: Type[core.Meta],
            schema_shortname: str | None = None,
    ) -> Path:
        """Construct the full path of the meta file"""
        path = settings.spaces_folder / space_name

        if subpath[0] == "/":
            subpath = f".{subpath}"
        if issubclass(class_type, core.Attachment):
            [parent_subpath, parent_name] = subpath.rsplit("/", 1)
            schema_shortname = "." + schema_shortname if schema_shortname else ""
            attachment_folder = (
                f"{parent_name}/attachments{schema_shortname}.{class_type.__name__.lower()}"
            )
            path = path / parent_subpath / ".dm" / attachment_folder
        else:
            path = path / subpath
        return path

    async def load_or_none(self,
                           space_name: str,
                           subpath: str,
                           shortname: str,
                           class_type: Type[core.Meta],
                           user_shortname: str | None = None,
                           schema_shortname: str | None = None
                           ) -> core.Meta | None:  # type: ignore
        """Load a Meta Json according to the reuqested Class type"""
        try:
            return await self.load(space_name, subpath, shortname, class_type, user_shortname, schema_shortname)
        except Exception as _:
            return None

    async def query(self, query: api.Query | None = None, user_shortname: str | None = None) \
            -> Tuple[int, list[core.Record]]:
        pass

    async def load(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[core.Meta],
            user_shortname: str | None = None,
            schema_shortname: str | None = None,
    ) -> core.Meta:
        """Load a Meta Json according to the requested Class type"""
        if subpath == shortname and class_type is core.Folder:
            shortname = ""
        path, filename = self.metapath(
            space_name, subpath, shortname, class_type, schema_shortname
        )
        if not (path / filename).is_file():
            # Remove the folder
            if path.is_dir() and len(os.listdir(path)) == 0:
                shutil.rmtree(path)

            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(
                    type="db",
                    code=InternalErrorCode.OBJECT_NOT_FOUND,
                    message=f"Request object is not available @{space_name}/{subpath}/{shortname} {class_type=} {schema_shortname=}",
                ),
            )

        path /= filename
        content = ""
        try:
            async with aiofiles.open(path, "r") as file:
                content = await file.read()
                return class_type.model_validate_json(content)
        except Exception as e:
            raise Exception(f"Error Invalid Entry At: {path}. Error {e} {content=}")

    async def load_resource_payload(
            self,
            space_name: str,
            subpath: str,
            filename: str,
            class_type: Type[core.Meta],
            schema_shortname: str | None = None,
    ):
        """Load a Meta class payload file"""

        path = self.payload_path(space_name, subpath, class_type, schema_shortname)
        path /= filename
        if not path.is_file():
            return {}
        try:
            if class_type == core.Log:
                return {"log_entry_items": read_jsonl_file(path)}

            bytes = path.read_bytes()
            return json.loads(bytes)
        except Exception as _:
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(type="db", code=12, message=f"Request object is not available {path}"),
            )

    async def save(
            self, space_name: str, subpath: str, meta: core.Meta
    ):
        """Save Meta Json to respectiv file"""
        path, filename = self.metapath(
            space_name,
            subpath,
            meta.shortname,
            meta.__class__,
            meta.payload.schema_shortname if meta.payload else None,
        )

        if not path.is_dir():
            os.makedirs(path)

        meta_json = meta.model_dump_json(exclude_none=True, warnings="error")
        with open(path / filename, "w") as file:
            file.write(meta_json)
            file.flush()
            os.fsync(file)

    async def create(
            self, space_name: str, subpath: str, meta: core.Meta
    ):
        path, filename = self.metapath(
            space_name, subpath, meta.shortname, meta.__class__
        )

        if (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create", code=InternalErrorCode.SHORTNAME_ALREADY_EXIST, message="already exists"),
            )

        if not path.is_dir():
            os.makedirs(path)

        with open(path / filename, "w") as file:
            file.write(meta.model_dump_json(exclude_none=True, warnings="error"))
            file.flush()
            os.fsync(file)

    async def save_payload(
            self, space_name: str, subpath: str, meta: core.Meta, attachment
    ):
        path, filename = self.metapath(
            space_name, subpath, meta.shortname, meta.__class__
        )
        payload_file_path = self.payload_path(
            space_name, subpath, meta.__class__)
        payload_filename = meta.shortname + Path(attachment.filename).suffix

        if not (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create", code=InternalErrorCode.MISSING_METADATA, message="metadata is missing"),
            )

        content = await attachment.read()
        with open(payload_file_path / payload_filename, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file)

    async def save_payload_from_json(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload_data: dict[str, Any],
    ):
        path, filename = self.metapath(
            space_name,
            subpath,
            meta.shortname,
            meta.__class__,
            meta.payload.schema_shortname if meta.payload else None,
        )
        payload_file_path = self.payload_path(
            space_name,
            subpath,
            meta.__class__,
            meta.payload.schema_shortname if meta.payload else None,
        )

        payload_filename = f"{meta.shortname}.json" if not issubclass(meta.__class__,
                                                                      core.Log) else f"{meta.shortname}.jsonl"

        if not (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create", code=InternalErrorCode.MISSING_METADATA, message="metadata is missing"),
            )

        payload_json = json.dumps(payload_data)
        if issubclass(meta.__class__, core.Log) and (payload_file_path / payload_filename).is_file():
            with open(payload_file_path / payload_filename, "a") as file:
                file.write(f"\n{payload_json}")
                file.flush()
                os.fsync(file)
        else:
            with open(payload_file_path / payload_filename, "w") as file:
                file.write(payload_json)
                file.flush()
                os.fsync(file)

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
        """Update the entry, store the difference and return it"""
        path, filename = self.metapath(
            space_name,
            subpath,
            meta.shortname,
            meta.__class__,

            schema_shortname,
        )
        if not (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(type="update", code=InternalErrorCode.OBJECT_NOT_FOUND,
                                message="Request object is not available"),
            )
        if retrieve_lock_status:
            async with RedisServices() as redis_services:
                if await redis_services.is_entry_locked(
                        space_name, subpath, meta.shortname, user_shortname
                ):
                    raise api.Exception(
                        status_code=status.HTTP_403_FORBIDDEN,
                        error=api.Error(
                            type="update", code=InternalErrorCode.LOCKED_ENTRY, message="This entry is locked"),
                    )
                elif await redis_services.get_lock_doc(
                        space_name, subpath, meta.shortname
                ):
                    # if the current can release the lock that means he is the right user
                    await redis_services.delete_lock_doc(
                        space_name, subpath, meta.shortname
                    )
                    await self.store_entry_diff(
                        space_name,
                        "/" + subpath,
                        meta.shortname,
                        user_shortname,
                        {},
                        {"lock_type": LockAction.unlock},
                        ["lock_type"],
                        core.Content,
                    )

        meta.updated_at = datetime.now()
        meta_json = meta.model_dump_json(exclude_none=True, warnings="error")
        with open(path / filename, "w") as file:
            file.write(meta_json)
            file.flush()
            os.fsync(file)

        if issubclass(meta.__class__, core.Log):
            return {}

        history_diff = await self.store_entry_diff(
            space_name,
            subpath,
            meta.shortname,
            user_shortname,
            old_version_flattend,
            new_version_flattend,
            updated_attributes_flattend,
            meta.__class__,
        )

        return history_diff

    async def update_payload(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload_data: dict[str, Any],
            owner_shortname: str = None,
    ):
        await self.save_payload_from_json(
            space_name,
            subpath,
            meta,
            payload_data,
        )

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
        diff_keys = list(old_version_flattend.keys())
        diff_keys.extend(list(new_version_flattend.keys()))
        history_diff = {}
        for key in set(diff_keys):
            if key in ["updated_at"]:
                continue
            if key in updated_attributes_flattend:
                old = (
                    copy(old_version_flattend[key])
                    if key in old_version_flattend
                    else "null"
                )
                new = (
                    copy(new_version_flattend[key])
                    if key in new_version_flattend
                    else "null"
                )

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
            owner_shortname=owner_shortname,
            timestamp=datetime.now(),
            request_headers=get_request_data().get('request_headers', {}),
            diff=history_diff,
        )
        history_path = settings.spaces_folder / space_name

        if subpath == "/" and resource_type == core.Space:
            history_path = Path(f"{history_path}/.dm")
        else:
            if issubclass(resource_type, core.Attachment):
                history_path = Path(f"{history_path}/.dm/{subpath}")
            else:
                if subpath == "/":
                    history_path = Path(f"{history_path}/.dm/{shortname}")
                else:
                    history_path = Path(
                        f"{history_path}/{subpath}/.dm/{shortname}")

        if not os.path.exists(history_path):
            os.makedirs(history_path)

        async with aiofiles.open(
                f"{history_path}/history.jsonl",
                "a",
        ) as events_file:
            await events_file.write(f"{history_obj.model_dump_json(exclude_none=True, warnings='error')}\n")

        return history_diff

    async def move(
            self,
            space_name: str,
            src_subpath: str,
            src_shortname: str,
            dest_subpath: str | None,
            dest_shortname: str | None,
            meta: core.Meta,
    ):
        src_path, src_filename = self.metapath(
            space_name,
            src_subpath,
            src_shortname,
            meta.__class__,
        )
        dest_path, dest_filename = self.metapath(
            space_name,
            dest_subpath or src_subpath,
            dest_shortname or src_shortname,
            meta.__class__,

        )

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
                src_shortname != dest_shortname
                and src_subpath != dest_subpath
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
            src_payload_file_path = (
                    self.payload_path(space_name, src_subpath, meta.__class__)
                    / meta.payload.body
            )
            meta.payload.body = meta.shortname + \
                                "." + meta.payload.body.split(".")[-1]
            dist_payload_file_path = (
                    self.payload_path(
                        space_name, dest_subpath or src_subpath, meta.__class__
                    )
                    / meta.payload.body
            )
            if src_payload_file_path.is_file():
                os.rename(src=src_payload_file_path, dst=dist_payload_file_path)

        if meta_updated:
            meta_json = meta.model_dump_json(exclude_none=True, warnings="error")
            with open(dest_path / dest_filename, "w") as opened_file:
                opened_file.write(meta_json)
                opened_file.flush()
                os.fsync(opened_file)

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
            src_space: str,
            dest_space: str,
            src_subpath: str,
            src_shortname: str,
            dest_subpath: str,
            dest_shortname: str,
            class_type: Type[core.Meta],
    ):

        meta_obj = await self.load(
            space_name=src_space,
            subpath=src_subpath,
            shortname=src_shortname,
            class_type=class_type,
        )

        src_path, src_filename = self.metapath(
            src_space, src_subpath, src_shortname, class_type
        )
        dest_path, dest_filename = self.metapath(
            dest_space,
            dest_subpath,
            dest_shortname,
            class_type,

        )

        # Create dest dir if not exist
        if not os.path.isdir(dest_path):
            os.makedirs(dest_path)

        copy_file(src=src_path / src_filename, dst=dest_path / dest_filename)

        self.payload_path(src_space, src_subpath, class_type)
        # Move payload file with the meta file
        if (
                meta_obj.payload
                and meta_obj.payload.content_type != ContentType.text
                and isinstance(meta_obj.payload.body, str)
        ):
            src_payload_file_path = (
                    self.payload_path(src_space, src_subpath, class_type)
                    / meta_obj.payload.body
            )
            dist_payload_file_path = (
                    self.payload_path(
                        dest_space, dest_subpath, class_type
                    )
                    / meta_obj.payload.body
            )
            copy_file(src=src_payload_file_path, dst=dist_payload_file_path)

    def is_entry_exist(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            resource_type: ResourceType,
            schema_shortname: str | None = None,
    ) -> bool:
        """Check if an entry with the given name already exist or not in the given path

        Args:
            space_name (str): The target space name
            subpath (str): The target subpath
            shortname (str): the target shortname
            class_type (core.Meta): The target class of the entry
            schema_shortname (str | None, optional): schema shortname of the entry. Defaults to None.

        Returns:
            bool: True if it's already exist, False otherwise
        """
        if subpath[0] == "/":
            subpath = f".{subpath}"

        payload_file = settings.spaces_folder / space_name / \
                       subpath / f"{shortname}.json"
        if payload_file.is_file():
            return True

        for r_type in ResourceType:
            # Spaces compared with each others only
            if r_type == ResourceType.space and r_type != resource_type:
                continue
            resource_cls = getattr(
                sys.modules["models.core"], camel_case(r_type.value), None
            )
            if not resource_cls:
                continue
            meta_path, meta_file = self.metapath(
                space_name, subpath, shortname, resource_cls, schema_shortname)
            if (meta_path / meta_file).is_file():
                return True

        return False

    async def delete(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            user_shortname: str,
            schema_shortname: str | None = None,
            retrieve_lock_status: bool | None = False,
    ):

        path, filename = self.metapath(
            space_name,
            subpath,
            meta.shortname,
            meta.__class__,

            schema_shortname,
        )
        if not path.is_dir() or not (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(
                    type="delete", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"),
            )
        if retrieve_lock_status:
            async with RedisServices() as redis_services:
                if await redis_services.is_entry_locked(
                        space_name, subpath, meta.shortname, user_shortname
                ):
                    raise api.Exception(
                        status_code=status.HTTP_403_FORBIDDEN,
                        error=api.Error(
                            type="delete", code=InternalErrorCode.LOCKED_ENTRY, message="This entry is locked"),
                    )
                else:
                    # if the current can release the lock that means he is the right user
                    await redis_services.delete_lock_doc(
                        space_name, subpath, meta.shortname
                    )

        pathname = path / filename
        if pathname.is_file():
            os.remove(pathname)

            # Delete payload file
            if meta.payload and meta.payload.content_type not in ContentType.inline_types():
                payload_file_path = self.payload_path(
                    space_name, subpath, meta.__class__
                ) / str(meta.payload.body)
                if payload_file_path.exists() and payload_file_path.is_file():
                    os.remove(payload_file_path)

        history_path = f"{settings.spaces_folder}/{space_name}" + \
                       f"{subpath}/.dm/{meta.shortname}"

        if (
                path.is_dir()
                and (
                not isinstance(meta, core.Attachment)
                or len(os.listdir(path)) == 0
        )
        ):
            shutil.rmtree(path)
            # in case of folder the path = {folder_name}/.dm
            if isinstance(meta, core.Folder) and path.parent.is_dir():
                shutil.rmtree(path.parent)
            if isinstance(meta, core.Folder) and Path(history_path).is_dir():
                shutil.rmtree(history_path)

    async def lock_handler(
            self, space_name: str, subpath: str, shortname: str, user_shortname: str, action: LockAction
    ) -> dict | None:
        match action:
            case LockAction.lock:
                async with RedisServices() as redis_services:
                    lock_type = await redis_services.save_lock_doc(
                        space_name,
                        subpath,
                        shortname,
                        user_shortname,
                        settings.lock_period,
                    )
                    return lock_type
            case LockAction.fetch:
                async with RedisServices() as redis_services:
                    lock_payload = await redis_services.get_lock_doc(
                        space_name, subpath, shortname
                    )
                    return lock_payload
            case LockAction.unlock:
                async with RedisServices() as redis_services:
                    await redis_services.delete_lock_doc(
                        space_name, subpath, shortname
                    )

    async def fetch_space(self, space_name: str) -> core.Space | None:
        spaces = await get_spaces()
        if space_name not in spaces:
            return None
        return core.Space.model_validate_json(spaces[space_name])

    async def get_entry_attachments(
            self,
            subpath: str,
            attachments_path: Path,
            filter_types: list | None = None,
            include_fields: list | None = None,
            filter_shortnames: list | None = None,
            retrieve_json_payload: bool = False,
    ) -> dict:
        if not attachments_path.is_dir():
            return {}
        try:
            attachments_iterator = os.scandir(attachments_path)
            attachments_dict: dict[ResourceType, list] = {}
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

                    if filter_types and ResourceType(attach_resource_name) not in filter_types:
                        continue

                    resource_class = getattr(
                        sys.modules["models.core"], camel_case(attach_resource_name)
                    )
                    resource_obj = None
                    async with aiofiles.open(attachments_file, "r") as meta_file:
                        try:
                            resource_obj = resource_class.model_validate_json(await meta_file.read())
                        except Exception as e:
                            raise Exception(
                                f"Bad attachment ... {attachments_file=}"
                            ) from e

                    resource_record_obj = resource_obj.to_record(
                        subpath, attach_shortname, include_fields
                    )
                    if is_file_check(retrieve_json_payload, resource_obj, resource_record_obj, attachment_entry):
                        async with aiofiles.open(
                                f"{attachment_entry.path}/{resource_obj.payload.body}", "r"
                        ) as payload_file_content:
                            resource_record_obj.attributes["payload"].body = json.loads(
                                await payload_file_content.read()
                            )

                    if attach_resource_name in attachments_dict:
                        attachments_dict[ResourceType(attach_resource_name)].append(
                            resource_record_obj)
                    else:
                        attachments_dict[ResourceType(attach_resource_name)] = [resource_record_obj]
                attachments_files.close()
            attachments_iterator.close()

            # SORT ALTERATION ATTACHMENTS BY ALTERATION.CREATED_AT
            sort_alteration(attachments_dict, attachments_path)

            return attachments_dict
        except Exception as e:
            print(e)
            return {}
