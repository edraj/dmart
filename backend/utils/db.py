import shutil
import sys
from models.enums import LockAction
from utils.helpers import branch_path, camel_case, snake_case
from datetime import datetime
import sys
from models.enums import ContentType, ResourceType
from utils.middleware import get_request_data
from utils.redis_services import RedisServices
from utils.settings import settings
import models.core as core
from typing import TypeVar, Type
import models.api as api
import os
import json
from pathlib import Path
from utils.logger import logger
from fastapi import status
from datetime import datetime
import aiofiles
from utils.regex import FILE_PATTERN, FOLDER_PATTERN


MetaChild = TypeVar("MetaChild", bound=core.Meta)


def locators_query(query: api.Query) -> tuple[int, list[core.Locator]]:
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
                        and not ResourceType(resource_name) in query.filter_types
                    ):
                        continue

                    if query.filter_shortnames and shortname not in query.filter_shortnames:
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


def metapath(
    space_name: str,
    subpath: str,
    shortname: str,
    class_type: Type[MetaChild],
    branch_name: str | None = settings.default_branch,
    schema_shortname: str | None = None,
) -> tuple[Path, str]:
    """Construct the full path of the meta file"""
    path = settings.spaces_folder / space_name / branch_path(branch_name)

    filename = ""
    if subpath[0] == "/":
        subpath = f".{subpath}"
    if issubclass(class_type, core.Folder):
        path = path / subpath / shortname / ".dm"
        filename = f"meta.{class_type.__name__.lower()}.json"
    elif issubclass(class_type, core.Space):
        path = settings.spaces_folder / space_name / ".dm" / shortname
        filename = "meta.space.json"
    elif issubclass(class_type, core.Attachment):
        [parent_subpath, parent_name] = subpath.rsplit("/", 1)
        schema_shortname = "." + schema_shortname if schema_shortname else ""
        attachment_folder = (
            f"{parent_name}/attachments{schema_shortname}.{class_type.__name__.lower()}"
        )
        path = path / parent_subpath / ".dm" / attachment_folder
        filename = f"meta.{shortname}.json"
    elif issubclass(class_type, core.History):
        [parent_subpath, parent_name] = subpath.rsplit("/", 1)
        path = path / parent_subpath / ".dm" / f"{parent_name}/history"
        filename = f"{shortname}.json"
    elif issubclass(class_type, core.Branch):
        path = settings.spaces_folder / space_name / shortname / ".dm"
        filename = f"meta.branch.json"
    else:
        path = path / subpath / ".dm" / shortname
        filename = f"meta.{snake_case(class_type.__name__)}.json"
    return path, filename


def payload_path(
    space_name: str,
    subpath: str,
    class_type: Type[MetaChild],
    branch_name: str | None = settings.default_branch,
    schema_shortname: str | None = None,
) -> Path:
    """Construct the full path of the meta file"""
    path = settings.spaces_folder / space_name / branch_path(branch_name)

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


async def load(
    space_name: str,
    subpath: str,
    shortname: str,
    class_type: Type[MetaChild],
    user_shortname: str,
    branch_name: str | None = settings.default_branch,
    schema_shortname: str | None = None,
) -> MetaChild:
    """Load a Meta Json according to the reuqested Class type"""
    path, filename = metapath(
        space_name, subpath, shortname, class_type, branch_name, schema_shortname
    )
    if not (path / filename).is_file():
        # Remove the folder
        if path.is_dir() and len(os.listdir(path)) == 0:
            shutil.rmtree(path)

        raise api.Exception(
            status_code=status.HTTP_404_NOT_FOUND,
            error=api.Error(type="db", code=12, message=f"Requested object not found @{space_name}/{subpath}/{shortname} {class_type=} {schema_shortname=}"),
        )

    path /= filename
    async with aiofiles.open(path, "r") as file:
        content = await file.read()
        return class_type.parse_raw(content)


def load_resource_payload(
    space_name: str,
    subpath: str,
    filename: str,
    class_type: Type[MetaChild],
    branch_name: str | None = settings.default_branch,
    schema_shortname: str | None = None,
) -> dict:
    """Load a Meta class payload file"""

    path = payload_path(space_name, subpath, class_type, branch_name, schema_shortname)
    path /= filename
    if not path.is_file():
        raise api.Exception(
            status_code=status.HTTP_404_NOT_FOUND,
            error=api.Error(type="db", code=12, message="requested object not found"),
        )
    return json.loads(path.read_bytes())


async def save(space_name: str, subpath: str, meta: core.Meta, branch_name: str | None):
    """Save Meta Json to respectiv file"""
    path, filename = metapath(
        space_name,
        subpath,
        meta.shortname,
        meta.__class__,
        branch_name,
        meta.payload.schema_shortname if meta.payload else None,
    )

    if isinstance(meta, core.Space):
        path = path.parent

    if not path.is_dir():
        os.makedirs(path)

    async with aiofiles.open(path / filename, "w") as file:
        await file.write(meta.json(exclude_none=True))


async def create(
    space_name: str, subpath: str, meta: core.Meta, branch_name: str | None
):
    path, filename = metapath(
        space_name, subpath, meta.shortname, meta.__class__, branch_name
    )

    if (path / filename).is_file():
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(type="create", code=30, message="already exists"),
        )

    if not path.is_dir():
        os.makedirs(path)

    async with aiofiles.open(path / filename, "w") as file:
        await file.write(meta.json(exclude_none=True))


async def save_payload(
    space_name: str, subpath: str, meta: core.Meta, attachment, branch_name: str | None
):
    path, filename = metapath(
        space_name, subpath, meta.shortname, meta.__class__, branch_name
    )
    payload_file_path = payload_path(space_name, subpath, meta.__class__, branch_name)
    payload_filename = meta.shortname + Path(attachment.filename).suffix

    if not (path / filename).is_file():
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(type="create", code=30, message="metadata is missing"),
        )

    async with aiofiles.open(payload_file_path / payload_filename, "wb") as file:
        content = await attachment.read()
        await file.write(content)


async def save_payload_from_json(
    space_name: str,
    subpath: str,
    meta: core.Meta,
    payload_data: dict,
    branch_name: str | None = settings.default_branch,
):
    path, filename = metapath(
        space_name,
        subpath,
        meta.shortname,
        meta.__class__,
        branch_name,
        meta.payload.schema_shortname,  # type: ignore
    )
    payload_file_path = payload_path(
        space_name, subpath, meta.__class__, branch_name, meta.payload.schema_shortname  # type: ignore
    )

    payload_filename = f"{meta.shortname}.json"

    if not (path / filename).is_file():
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(type="create", code=30, message="metadata is missing"),
        )

    async with aiofiles.open(payload_file_path / payload_filename, "w") as file:
        await file.write(json.dumps(payload_data))


async def update(
    space_name: str,
    subpath: str,
    meta: core.Meta,
    old_version_flattend: dict,
    new_version_flattend: dict,
    updated_attributes_flattend: list,
    branch_name: str | None,
    user_shortname: str,
    schema_shortname: str | None = None,
) -> dict:
    """Update the entry, store the difference and return it"""
    path, filename = metapath(
        space_name,
        subpath,
        meta.shortname,
        meta.__class__,
        branch_name,
        schema_shortname,
    )
    if not (path / filename).is_file():
        raise api.Exception(
            status_code=status.HTTP_404_NOT_FOUND,
            error=api.Error(type="update", code=30, message="does not exist"),
        )
    redis = await RedisServices()
    if await redis.is_entry_locked(
        space_name, branch_name, subpath, meta.shortname, user_shortname
    ):
        raise api.Exception(
            status_code=status.HTTP_403_FORBIDDEN,
            error=api.Error(type="update", code=30, message="This entry is locked"),
        )
    elif await redis.get_lock_doc(space_name, branch_name, subpath, meta.shortname):
        # if the current can release the lock that means he is the right user
        await redis.delete_lock_doc(space_name, branch_name, subpath, meta.shortname)
        await store_entry_diff(
            space_name,
            branch_name,
            "/" + subpath,
            meta.shortname,
            user_shortname,
            {},
            {"lock_type": LockAction.unlock},
            ["lock_type"],
            core.Content,
        )

    meta.updated_at = datetime.now()
    async with aiofiles.open(path / filename, "w") as file:
        await file.write(meta.json(exclude_none=True))

    history_diff = await store_entry_diff(
        space_name,
        branch_name,
        subpath,
        meta.shortname,
        user_shortname,
        old_version_flattend,
        new_version_flattend,
        updated_attributes_flattend,
        meta.__class__,
    )

    return history_diff


async def store_entry_diff(
    space_name: str,
    branch_name: str | None,
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
        if key in updated_attributes_flattend:
            old = old_version_flattend[key] if key in old_version_flattend else "null"
            new = new_version_flattend[key] if key in new_version_flattend else "null"

            if old != new:
                history_diff[key] = {
                    "old": old,
                    "new": new,
                }
    if not history_diff:
        return {}

    history_diff["x_request_data"] = get_request_data()

    history_obj = core.History(
        shortname="history",
        owner_shortname=owner_shortname,
        timestamp=datetime.now(),
        diff=history_diff,
    )
    history_path = settings.spaces_folder / space_name / branch_path(branch_name)

    if subpath == "/" and resource_type == core.Space:
        history_path = f"{history_path}/.dm"
    else:
        if issubclass(resource_type, core.Attachment):
            history_path = f"{history_path}/.dm/{subpath}"
        else:
            if subpath == "/":
                history_path = f"{history_path}/.dm/{shortname}"
            else:
                history_path = f"{history_path}/{subpath}/.dm/{shortname}"

    if not os.path.exists(history_path):
        os.makedirs(history_path)

    async with aiofiles.open(
        f"{history_path}/history.jsonl",
        "a",
    ) as events_file:
        await events_file.write(f"{history_obj.json()}\n")

    return history_diff


async def move(
    space_name: str,
    src_subpath: str,
    src_shortname: str,
    dest_subpath: str | None,
    dest_shortname: str | None,
    meta: core.Meta,
    branch_name: str | None = settings.default_branch,
):
    """Move the file that match the criteria given, remove source folder if empty

    Parameters
    ----------
    space_name: str,
    src_subpath: str,
    src_shortname: str,
    dest_subpath: str | None,
    dest_shortname: str | None,
    meta: core.Meta
    """

    src_path, src_filename = metapath(
        space_name, src_subpath, src_shortname, meta.__class__, branch_name
    )
    dest_path, dest_filename = metapath(
        space_name,
        dest_subpath or src_subpath,
        dest_shortname or src_shortname,
        meta.__class__,
        branch_name,
    )

    # Create dest dir if not exist
    if not os.path.isdir(dest_path):
        os.makedirs(dest_path)

    meta_updated = False
    if dest_shortname:
        meta.shortname = dest_shortname
        meta_updated = True

    os.rename(src=src_path / src_filename, dst=dest_path / dest_filename)

    # Move payload file with the meta file
    if (
        meta.payload
        and meta.payload.content_type != ContentType.text
        and isinstance(meta.payload.body, str)
    ):
        src_payload_file_path = (
            payload_path(space_name, src_subpath, meta.__class__, branch_name)
            / meta.payload.body
        )
        meta.payload.body = meta.shortname + "." + meta.payload.body.split(".")[-1]
        dist_payload_file_path = (
            payload_path(
                space_name, dest_subpath or src_subpath, meta.__class__, branch_name
            )
            / meta.payload.body
        )
        if src_payload_file_path.is_file():
            os.rename(src=src_payload_file_path, dst=dist_payload_file_path)

    if meta_updated:
        async with aiofiles.open(dest_path / dest_filename, "w") as opened_file:
            await opened_file.write(meta.json(exclude_none=True))

    # Delete Src path if empty
    if src_path.is_dir() and len(os.listdir(src_path)) == 0:
        os.removedirs(src_path)


async def delete(
    space_name: str,
    subpath: str,
    meta: core.Meta,
    branch_name: str | None,
    user_shortname: str,
    schema_shortname: str | None = None,
):
    """Delete the file that match the criteria given, remove folder if empty

    Parameters
    ----------
    space_name: str
    subpath: str
    shortname: str
    meta: Meta

    Exception
    ----------
    api.Exception:
        HTTP_404_NOT_FOUND
    """

    path, filename = metapath(
        space_name,
        subpath,
        meta.shortname,
        meta.__class__,
        branch_name,
        schema_shortname,
    )
    if not path.is_dir() or not (path / filename).is_file():
        raise api.Exception(
            status_code=status.HTTP_404_NOT_FOUND,
            error=api.Error(type="delete", code=30, message="does not exist"),
        )
    redis = await RedisServices()
    if await redis.is_entry_locked(
        space_name, branch_name, subpath, meta.shortname, user_shortname
    ):
        raise api.Exception(
            status_code=status.HTTP_403_FORBIDDEN,
            error=api.Error(type="delete", code=30, message="This entry is locked"),
        )
    else:
        # if the current can release the lock that means he is the right user
        await redis.delete_lock_doc(space_name, branch_name, subpath, meta.shortname)

    pathname = path / filename
    if pathname.is_file():
        os.remove(pathname)

        # Delete payload file
        if meta.payload and meta.payload.content_type != ContentType.text:
            payload_file_path = payload_path(
                space_name, subpath, meta.__class__, branch_name
            ) / str(meta.payload.body)
            if payload_file_path.is_file():
                os.remove(payload_file_path)

    # Remove entry folder
    if(
        not isinstance(meta, core.Attachment)
        or len(os.listdir(path)) == 0
    ):
        shutil.rmtree(path)


