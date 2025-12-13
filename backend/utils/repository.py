import os
import re
import sys
import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4
from fastapi import status
import models.api as api
import models.core as core
import utils.regex as regex
from models.enums import ContentType, Language
from data_adapters.adapter import data_adapter as db
from utils.helpers import (
    camel_case,
    jq_dict_parser,
)
from utils.internal_error_code import InternalErrorCode
from utils.jwt import generate_jwt
from utils.settings import settings

async def serve_query(
        query: api.Query, logged_in_user: str
) -> tuple[int, list[core.Record]]:
    records: list[core.Record] = []
    total: int = 0

    total, records = await db.query(query, logged_in_user)

    try:
        for _r in records or []:
            attrs = getattr(_r, "attributes", None)
            if isinstance(attrs, dict):
                attrs.pop("password", None)
    except Exception:
        pass

    if query.jq_filter:
        try:
            def _run_jq_subprocess() -> list:
                _input_local = [record.model_dump() for record in records]
                _input_local = jq_dict_parser(_input_local)
                input_json = json.dumps(_input_local)

                cmd = ["jq", "-c", query.jq_filter]

                try:
                    completed = subprocess.run(
                        cmd, # type: ignore
                        input=input_json.encode("utf-8"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=settings.jq_timeout,
                        check=False,
                    )
                except subprocess.TimeoutExpired:
                    raise api.Exception(
                        status.HTTP_400_BAD_REQUEST,
                        api.Error(
                            type="request",
                            code=InternalErrorCode.JQ_TIMEOUT,
                            message="jq filter took too long to execute",
                        ),
                    )

                if completed.returncode != 0:
                    raise api.Exception(
                        status.HTTP_400_BAD_REQUEST,
                        api.Error(
                            type="request",
                            code=InternalErrorCode.JQ_ERROR,
                            message="jq filter failed to be executed",
                        ),
                    )

                stdout = completed.stdout.decode("utf-8")
                results: list = []
                if stdout.startswith("[") and stdout.endswith("]\n"):
                    results = json.loads(stdout)
                else:
                    for line in stdout.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        results.append(json.loads(line))
                return results

            loop = asyncio.get_running_loop()
            records = await asyncio.wait_for(
                loop.run_in_executor(None, _run_jq_subprocess),
                timeout=settings.jq_timeout,
            )

        except FileNotFoundError:
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
