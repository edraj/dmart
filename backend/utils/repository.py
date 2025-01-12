import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
from fastapi import status
import models.api as api
import models.core as core
import utils.regex as regex
from data_adapters.file.adapter_helpers import get_record_from_redis_doc
from models.enums import ContentType, Language, ResourceType
from data_adapters.adapter import data_adapter as db
from utils.access_control import access_control
from utils.helpers import (
    camel_case,
    flatten_all,
    snake_case,
)
from utils.internal_error_code import InternalErrorCode
from utils.jwt import generate_jwt
from utils.plugin_manager import plugin_manager
from data_adapters.file.redis_services import RedisServices
from utils.settings import settings


def parse_redis_response(rows: list) -> list:
    mylist: list = []
    for one in rows:
        mydict = {}
        key: str | None = None
        for i, value in enumerate(one):
            if i % 2 == 0:
                key = value
            elif key:
                mydict[key] = value
        mylist.append(mydict)
    return mylist


async def serve_query(
        query: api.Query, logged_in_user: str
) -> tuple[int, list[core.Record]]:
    records: list[core.Record] = []
    total: int = 0

    total, records = await db.query(query, logged_in_user)
    init_length = len(records)
    records = [record for record in records if await access_control.check_access(
        user_shortname=logged_in_user,
        space_name=query.space_name,
        subpath=query.subpath,
        resource_type=record.resource_type,
        action_type=core.ActionType.query,
        entry_shortname=record.shortname,
    )]
    new_length = len(records)
    total -= init_length - new_length


    if query.jq_filter:
        try:
            jq = __import__("jq")
            _input = [record.to_dict() for record in records]
            for __input in _input:
                if "uuid" in __input:
                    __input["uuid"] = str(__input["uuid"])

            records = (
                jq.compile(query.jq_filter)
                .input(_input)
                .all()
            )
        except ModuleNotFoundError:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.NOT_ALLOWED,
                    message="jq is not installed!",
                ),
            )

    return total, records


async def get_last_updated_entry(
        space_name: str,
        schema_names: list,
        retrieve_json_payload: bool,
        logged_in_user: str,
):
    report_query = api.Query(
        type=api.QueryType.search,
        space_name=space_name,
        subpath="/",
        search=f"@schema_shortname:{'|'.join(schema_names)}",
        filter_schema_names=["meta"],
        sort_by="updated_at",
        sort_type=api.SortType.descending,
        limit=50,  # to be in safe side if the query filtered out some invalid entries
        retrieve_json_payload=retrieve_json_payload,
    )
    _, records = await serve_query(report_query, logged_in_user)

    return records[0] if records else None





# def is_entry_exist(
#     space_name: str,
#     subpath: str,
#     shortname: str,
#     resource_type: ResourceType,
#     schema_shortname: str | None = None,
# ) -> bool:
#     """Check if an entry with the given name already exist or not in the given path
#
#     Args:
#         space_name (str): The target space name
#         subpath (str): The target subpath
#         shortname (str): the target shortname
#         class_type (core.Meta): The target class of the entry
#         schema_shortname (str | None, optional): schema shortname of the entry. Defaults to None.
#
#     Returns:
#         bool: True if it's already exist, False otherwise
#     """
#     if subpath[0] == "/":
#         subpath = f".{subpath}"
#
#     payload_file = settings.spaces_folder / space_name / \
#         subpath / f"{shortname}.json"
#     if payload_file.is_file():
#         return True
#
#     for r_type in ResourceType:
#         # Spaces compared with each others only
#         if r_type == ResourceType.space and r_type != resource_type:
#             continue
#         resource_cls = getattr(
#             sys.modules["models.core"], camel_case(r_type.value), None
#         )
#         if not resource_cls:
#             continue
#         meta_path, meta_file = db.metapath(
#             space_name, subpath, shortname, resource_cls, schema_shortname)
#         if (meta_path/meta_file).is_file():
#             return True
#
#     return False


async def get_resource_obj_or_none(
        *,
        space_name: str,
        subpath: str,
        shortname: str,
        resource_type: str,
        user_shortname: str,
):
    resource_cls = getattr(
        sys.modules["models.core"], camel_case(resource_type))
    try:
        return await db.load(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            class_type=resource_cls,
            user_shortname=user_shortname,
        )
    except Exception:
        return None


async def get_payload_obj_or_none(
        *,
        space_name: str,
        subpath: str,
        filename: str,
        resource_type: str,
):
    resource_cls = getattr(
        sys.modules["models.core"], camel_case(resource_type))
    try:
        return await db.load_resource_payload(
            space_name=space_name,
            subpath=subpath,
            filename=filename,
            class_type=resource_cls,
        )
    except Exception:
        return None


async def get_group_users(group_name: str):
    async with RedisServices() as redis_services:
        users_docs = await redis_services.search(
            space_name=settings.management_space,
            schema_name="meta",
            filters={"subpath": ["users"]},
            limit=10000,
            offset=0,
            search=f"@groups:{{{group_name}}}",
        )

    if users_docs:
        return users_docs["data"]

    return []


async def folder_meta_content_check(
        space_name, subpath, folder_name, spaces_path_parts,
        user_shortname, folder_name_index, invalid_folders
):
    try:
        folder_meta_content = await db.load(
            space_name=space_name,
            subpath=folder_name,
            shortname="",
            class_type=core.Folder,
            user_shortname=user_shortname,
        )
        if (
                folder_meta_content.payload
                and folder_meta_content.payload.content_type == ContentType.json
        ):
            payload_path = "/"
            subpath_parts = subpath.split("/")
            if len(subpath_parts) > (len(spaces_path_parts) + 2):
                payload_path = "/".join(
                    subpath_parts[folder_name_index:-1])
            folder_meta_payload = await db.load_resource_payload(
                space_name,
                payload_path,
                str(folder_meta_content.payload.body),
                core.Folder,
            )
            if folder_meta_content.payload.schema_shortname and folder_meta_payload:
                await db.validate_payload_with_schema(
                    payload_data=folder_meta_payload,
                    space_name=space_name,
                    schema_shortname=folder_meta_content.payload.schema_shortname,
                )
    except Exception:
        invalid_folders.append(folder_name)


async def health_check_entry_vsd(
        space_name, folder_name, entry_shortname, entry_resource_type, user_shortname,
        folder, folders_report, max_invalid_size, entry_meta_obj
):
    await health_check_entry(
        space_name=space_name,
        subpath=folder_name,
        shortname=entry_shortname,
        resource_type=entry_resource_type,
        user_shortname=user_shortname,
    )

    # VALIDATE ENTRY ATTACHMENTS
    attachments_path = f"{folder.path}/{entry_shortname}"
    attachment_folders = os.scandir(attachments_path)
    for attachment_folder in attachment_folders:
        # i.e. attachment_folder = attachments.media
        if attachment_folder.is_file():
            continue

        attachment_folder_files = os.scandir(attachment_folder)
        for attachment_folder_file in attachment_folder_files:
            # i.e. attachment_folder_file = meta.*.json or *.png
            if (
                    not attachment_folder_file.is_file()
                    or not os.access(attachment_folder_file.path, os.W_OK)
                    or not os.access(attachment_folder_file.path, os.R_OK)
            ):
                raise Exception(
                    f"can't access this attachment {attachment_folder_file.path[len(str(settings.spaces_folder)):]}"
                )

            attachment_match = regex.ATTACHMENT_PATTERN.search(attachment_folder_file.path)
            if not attachment_match:
                # if it's the media file not its meta json file
                continue
            attachment_shortname = attachment_match.group(2)
            attachment_resource_type = attachment_match.group(1)
            await health_check_entry(
                space_name=space_name,
                subpath=f"{folder_name}/{entry_shortname}",
                shortname=attachment_shortname,
                resource_type=attachment_resource_type,
                user_shortname=user_shortname,
            )

    if "valid_entries" not in folders_report[folder_name]:
        folders_report[folder_name]["valid_entries"] = 1
    else:
        folders_report[folder_name]["valid_entries"] += 1


async def validate_subpath_data(
        space_name: str,
        subpath: str,
        user_shortname: str,
        invalid_folders: list[str],
        folders_report: dict[str, dict[str, Any]],
        meta_folders_health: list[str],
        max_invalid_size: int,
):
    """
    Params:
    @subpath: str holding the full path, ex: ../spaces/aftersales/reports

    Algorithm:
    - if subpath ends with .dm return
    - for folder in scandir(subpath)
        - if folder ends with .dm
            - get folder_meta = folder/meta.folder.json
            - validate folder_meta
            - loop over folder.entries and validate them along with theire attachments
        - else
            - call myself with subpath = folder
    """
    spaces_path_parts = str(settings.spaces_folder).split("/")
    folder_name_index = len(spaces_path_parts) + 1

    if subpath.endswith(".dm"):
        return

    subpath_folders = os.scandir(subpath)
    for folder in subpath_folders:
        if not folder.is_dir():
            continue

        if folder.name != ".dm":
            await validate_subpath_data(
                space_name,
                folder.path,
                user_shortname,
                invalid_folders,
                folders_report,
                meta_folders_health,
                max_invalid_size,
            )
            continue

        folder_meta = Path(f"{folder.path}/meta.folder.json")
        folder_name = "/".join(subpath.split("/")[folder_name_index:])
        if not folder_meta.is_file():
            meta_folders_health.append(
                str(folder_meta)[len(str(settings.spaces_folder)):]
            )
            continue

        await folder_meta_content_check(
            space_name, subpath, folder_name, spaces_path_parts,
            user_shortname, folder_name_index, invalid_folders
        )

        folders_report.setdefault(folder_name, {})

        # VALIDATE FOLDER ENTRIES
        folder_entries = os.scandir(folder.path)
        for entry in folder_entries:
            if entry.is_file():
                continue

            entry_files = os.scandir(entry)
            entry_match = None
            for file in entry_files:
                if file.is_dir():
                    continue
                entry_match = regex.FILE_PATTERN.search(file.path)

                if entry_match:
                    break

            if not entry_match:
                issue = {
                    "issues": ["meta"],
                    "uuid": "",
                    "shortname": entry.name,
                    "exception": f"Can't access this meta {subpath[len(str(settings.spaces_folder)):]}/{entry.name}",
                }

                if "invalid_entries" not in folders_report[folder_name]:
                    folders_report[folder_name]["invalid_entries"] = [issue]
                else:
                    if (
                            len(folders_report[folder_name]["invalid_entries"])
                            >= max_invalid_size
                    ):
                        break
                    folders_report[folder_name]["invalid_entries"].append(
                        issue)
                continue

            entry_shortname = entry_match.group(1)
            entry_resource_type = entry_match.group(2)

            if folder_name == "schema" and entry_shortname == "meta_schema":
                folders_report[folder_name].setdefault("valid_entries", 0)
                folders_report[folder_name]["valid_entries"] += 1
                continue

            entry_meta_obj = None
            try:
                await health_check_entry_vsd(
                    space_name, folder_name, entry_shortname, entry_resource_type, user_shortname,
                    folder, folders_report, max_invalid_size, entry_meta_obj
                )
            except Exception as e:
                issue_type = "payload"
                uuid = ""
                if not entry_meta_obj:
                    issue_type = "meta"
                else:
                    uuid = str(
                        entry_meta_obj.uuid) if entry_meta_obj.uuid else ""

                issue = {
                    "issues": [issue_type],
                    "uuid": uuid,
                    "shortname": entry_shortname,
                    "resource_type": entry_resource_type,
                    "exception": str(e),
                }

                if "invalid_entries" not in folders_report[folder_name]:
                    folders_report[folder_name]["invalid_entries"] = [issue]
                else:
                    if (
                            len(folders_report[folder_name]["invalid_entries"])
                            >= max_invalid_size
                    ):
                        break
                    folders_report[folder_name]["invalid_entries"].append(
                        issue
                    )

        if not folders_report.get(folder_name, {}):
            del folders_report[folder_name]


async def health_check_entry(
        space_name: str,
        subpath: str,
        resource_type: str,
        shortname: str,
        user_shortname: str,
):
    resource_class = getattr(
        sys.modules["models.core"], camel_case(resource_type)
    )
    entry_meta_obj = resource_class.model_validate(await db.load(
        space_name=space_name,
        subpath=subpath,
        shortname=shortname,
        class_type=resource_class,
        user_shortname=user_shortname,
    ))
    if entry_meta_obj.shortname != shortname:
        raise Exception(
            "the shortname which got from the folder path doesn't match the shortname in the meta file."
        )
    payload_file_path = None
    if (
            entry_meta_obj.payload
            and entry_meta_obj.payload.content_type == ContentType.image
    ):
        payload_file_path = Path(f"{subpath}/{entry_meta_obj.payload.body}")
        if (
                not payload_file_path.is_file()
                or not bool(
            re.match(
                regex.IMG_EXT,
                entry_meta_obj.payload.body.split(".")[-1],
            )
        )
                or not os.access(payload_file_path, os.R_OK)
                or not os.access(payload_file_path, os.W_OK)
        ):
            if payload_file_path:
                raise Exception(
                    f"can't access this payload {payload_file_path}"
                )
            else:
                raise Exception(
                    f"can't access this payload {subpath}"
                    f"/{entry_meta_obj.shortname}"
                )
    elif (
            entry_meta_obj.payload
            and isinstance(entry_meta_obj.payload.body, str)
            and entry_meta_obj.payload.content_type == ContentType.json
    ):
        payload_file_path = db.payload_path(space_name, subpath, resource_class)
        if not entry_meta_obj.payload.body.endswith(
                ".json"
        ) or not os.access(payload_file_path, os.W_OK):
            raise Exception(
                f"can't access this payload {payload_file_path}"
            )
        payload_file_content = await db.load_resource_payload(
            space_name,
            subpath,
            entry_meta_obj.payload.body,
            resource_class,
        )
        if entry_meta_obj.payload.schema_shortname and payload_file_content:
            await db.validate_payload_with_schema(
                payload_data=payload_file_content,
                space_name=space_name,
                schema_shortname=entry_meta_obj.payload.schema_shortname,
            )

    if (
            entry_meta_obj.payload.checksum and
            entry_meta_obj.payload.client_checksum and
            entry_meta_obj.payload.checksum != entry_meta_obj.payload.client_checksum
    ):
        raise Exception(
            f"payload.checksum not equal payload.client_checksum {subpath}/{entry_meta_obj.shortname}"
        )


async def internal_sys_update_model(
        space_name: str,
        subpath: str,
        meta: core.Meta,
        updates: dict,
        sync_redis: bool = True,
        payload_dict: dict[str, Any] = {},
) -> bool:
    """
    Update @meta entry and its payload by @updates dict of attributes in the
    *Used by the system only, not APIs*
    """

    meta.updated_at = datetime.now()
    meta_updated = False
    payload_updated = False

    if not payload_dict:
        try:
            body = str(meta.payload.body) if meta and meta.payload else ""
            mydict = await db.load_resource_payload(
                space_name, subpath, body, core.Content
            )
            payload_dict = mydict if mydict else {}
        except Exception:
            pass

    restricted_fields = [
        "uuid",
        "shortname",
        "created_at",
        "updated_at",
        "owner_shortname",
        "payload",
    ]
    old_version_flattend = {**meta.model_dump()}
    for key, value in updates.items():
        if key in restricted_fields:
            continue

        if key in meta.model_fields.keys():
            meta_updated = True
            meta.__setattr__(key, value)
        elif payload_dict:
            payload_dict[key] = value
            payload_updated = True

    if meta_updated:
        await db.update(
            space_name,
            subpath,
            meta,
            old_version_flattend,
            {**meta.model_dump()},
            list(updates.keys()),
            meta.shortname
        )
    if payload_updated and meta.payload and meta.payload.schema_shortname:
        await db.validate_payload_with_schema(
            payload_dict, space_name, meta.payload.schema_shortname
        )
        await db.save_payload_from_json(
            space_name, subpath, meta, payload_dict
        )

    if not sync_redis:
        return True

    async with RedisServices() as redis_services:
        await redis_services.save_meta_doc(space_name, subpath, meta)
        if payload_updated:
            payload_dict.update(json.loads(meta.model_dump_json(exclude_none=True, warnings="error")))
            await redis_services.save_payload_doc(
                space_name,
                subpath,
                meta,
                payload_dict,
                ResourceType(snake_case(type(meta).__name__)),
            )

    return True


async def internal_save_model(
        space_name: str,
        subpath: str,
        meta: core.Meta,
        payload: dict | None = None
):
    await db.save(
        space_name=space_name,
        subpath=subpath,
        meta=meta,
    )

    if settings.active_data_db == "file":
        async with RedisServices() as redis:
            await redis.save_meta_doc(
                space_name,
                subpath,
                meta,
            )

            if payload:
                await db.save_payload_from_json(
                    space_name=space_name,
                    subpath=subpath,
                    meta=meta,
                    payload_data=payload,
                )
                payload.update(json.loads(meta.model_dump_json(exclude_none=True, warnings="error")))
                await redis.save_payload_doc(
                    space_name,
                    subpath,
                    meta,
                    payload,
                    ResourceType(snake_case(type(meta).__name__))
                )


async def generate_payload_string(
        space_name: str,
        subpath: str,
        shortname: str,
        payload: dict,
):
    payload_string = ""
    # Remove system related attributes from payload
    for attr in RedisServices.SYS_ATTRIBUTES:
        if attr in payload:
            del payload[attr]

    # Generate direct payload string
    payload_values = set(flatten_all(payload).values())
    payload_string += ",".join([str(i)
                                for i in payload_values if i is not None])

    # Generate attachments payload string
    attachments: dict[str, list] = await db.get_entry_attachments(
        subpath=f"{subpath}/{shortname}",
        attachments_path=(
                settings.spaces_folder
                / f"{space_name}/{subpath}/.dm/{shortname}"
        ),
        retrieve_json_payload=True,
        include_fields=[
            "shortname",
            "displayname",
            "description",
            "payload",
            "tags",
            "owner_shortname",
            "owner_group_shortname",
            "body",
            "state",
        ],
    )
    if not attachments:
        return payload_string.strip(",")

    # Convert Record objects to dict
    dict_attachments = {}
    for k, v in attachments.items():
        dict_attachments[k] = [i.model_dump() for i in v]

    attachments_values = set(flatten_all(dict_attachments).values())
    attachments_payload_string = ",".join(
        [str(i) for i in attachments_values if i is not None]
    )
    payload_string += attachments_payload_string
    return payload_string.strip(",")




async def get_entry_by_var(
        key: str,
        val: str,
        logged_in_user,
        retrieve_json_payload: bool = False,
        retrieve_attachments: bool = False,
        retrieve_lock_status: bool = False,
):
    if settings.active_data_db == "sql":
        _result = await db.get_entry_by_criteria({key: val})
        if _result is None or len(_result) == 0:
            return None
        return _result[0]

    spaces = await db.get_spaces()
    entry_doc = None
    entry_space = None
    async with RedisServices() as redis_services:
        for space_name, space in spaces.items():
            space = json.loads(space)
            if not space['indexing_enabled']:
                continue
            search_res = await redis_services.search(
                space_name=space_name,
                search=f"@{key}:{val}*",
                limit=1,
                offset=0,
                filters={},
            )
            if search_res["total"] > 0:
                entry_doc = json.loads(search_res["data"][0])
                entry_space = space_name
                break

    if not entry_doc or not entry_space:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"
            ),
        )

    if not await access_control.check_access(
            user_shortname=logged_in_user,
            space_name=entry_space,
            subpath=entry_doc["subpath"],
            resource_type=entry_doc["resource_type"],
            action_type=core.ActionType.view,
            resource_is_active=entry_doc["is_active"],
            resource_owner_shortname=entry_doc.get("owner_shortname"),
            resource_owner_group=entry_doc.get("owner_group_shortname"),
            entry_shortname=entry_doc.get("shortname")
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [12]",
            ),
        )

    await plugin_manager.before_action(
        core.Event(
            space_name=entry_space,
            subpath=entry_doc["subpath"],
            shortname=entry_doc["shortname"],
            action_type=core.ActionType.view,
            resource_type=entry_doc["resource_type"],
            user_shortname=logged_in_user,
        )
    )

    resource_base_record = await get_record_from_redis_doc(
        db,
        space_name=entry_space,
        doc=entry_doc,
        retrieve_json_payload=retrieve_json_payload,
        retrieve_attachments=retrieve_attachments,
        validate_schema=True,
        retrieve_lock_status=retrieve_lock_status,
    )

    await plugin_manager.after_action(
        core.Event(
            space_name=entry_space,
            subpath=entry_doc["subpath"],
            shortname=entry_doc["shortname"],
            action_type=core.ActionType.view,
            resource_type=entry_doc["resource_type"],
            user_shortname=logged_in_user,
        )
    )

    return resource_base_record


async def url_shortner(url: str) -> str:
    token_uuid = str(uuid4())[:8]
    await db.set_url_shortner(token_uuid, url)
    return f"{settings.public_app_url}/managed/s/{token_uuid}"


async def store_user_invitation_token(user: core.User, channel: str) -> str | None:
    """Generate and Store an invitation token 

    Returns:
        invitation link or None if the user is not eligible
    """
    invitation_value = None
    if channel == "SMS" and user.msisdn:
        invitation_value = f"{channel}:{user.msisdn}"
    elif channel == "EMAIL" and user.email:
        invitation_value = f"{channel}:{user.email}"

    if not invitation_value:
        return None

    invitation_token = generate_jwt(
        {"shortname": user.shortname, "channel": channel},
        settings.jwt_access_expires,
    )

    await db.set_invitation(invitation_token, invitation_value)

    return core.User.invitation_url_template() \
        .replace("{url}", settings.invitation_link) \
        .replace("{token}", invitation_token) \
        .replace("{lang}", Language.code(user.language)) \
        .replace("{user_type}", user.type)


async def delete_space(space_name, record, owner_shortname):
    if settings.active_data_db == "sql":
        resource_obj = core.Meta.from_record(
            record=record, owner_shortname=owner_shortname
        )
        await db.delete(space_name, record.subpath, resource_obj, owner_shortname)

    os.system(f"rm -r {settings.spaces_folder}/{space_name}")

