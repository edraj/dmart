from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import jq

from models.enums import ContentType, ResourceType, ValidationEnum
from utils.access_control import access_control
from utils.spaces import get_spaces
from utils.settings import settings
import utils.regex as regex
import models.core as core
import models.api as api
import utils.db as db
from utils.redis_services import RedisServices
import aiofiles
from fastapi import status
from fastapi.logger import logger
from utils.helpers import branch_path, camel_case, snake_case
from utils.custom_validations import validate_payload_with_schema
import subprocess
from redis.commands.search.document import Document as RedisDocument #type: ignore


async def serve_query(
    query: api.Query, logged_in_user: str, redis_query_policies: list = []
) -> tuple[int, list[core.Record]]:
    """Given a query return the total and the records

    Parameters
    ----------
    query: api.Query
        query of type [spaces, search, subpath]

    Returns
    -------
    Total, Records

    """
    records: list[core.Record] = []
    total: int = 0
    spaces = await get_spaces()
    redis = await RedisServices()
    match query.type:
        case api.QueryType.spaces:
            for space_json in spaces.values():
                space = core.Space.parse_raw(space_json)

                if await access_control.check_space_access(
                    logged_in_user, space.shortname
                ):
                    total += 1
                    records.append(
                        space.to_record(
                            query.subpath,
                            space.shortname,
                            query.include_fields if query.include_fields else [],
                            query.branch_name,
                        )
                    )

        case api.QueryType.search:
            search_res: list = []
            total = 0
            if not query.filter_schema_names:
                query.filter_schema_names = ["meta"]
            created_at_search = ""
            if query.from_date and query.to_date:
                created_at_search = (
                    "["
                    + f"{query.from_date.timestamp()} {query.to_date.timestamp()}"
                    + "]"
                )
            elif query.from_date:
                created_at_search = (
                    "["
                    + f"{query.from_date.timestamp()} {datetime(2199, 12, 31).timestamp()}"
                    + "]"
                )
            elif query.to_date:
                created_at_search = (
                    "["
                    + f"{datetime(2010, 1, 1).timestamp()} {query.to_date.timestamp()}"
                    + "]"
                )
            for schema_name in query.filter_schema_names:
                redis_res = await redis.search(
                    space_name=query.space_name,
                    branch_name=query.branch_name,
                    schema_name=schema_name,
                    search=str(query.search),
                    filters={
                        "resource_type": query.filter_types or [],
                        "shortname": query.filter_shortnames or [],
                        "tags": query.filter_tags or [],
                        "subpath": [query.subpath] if query.subpath != "/" else [],
                        "query_policies": redis_query_policies,
                        "created_at": created_at_search,
                    },
                    limit=(query.limit + query.offset),
                    offset=0,
                    highlight_fields=list(query.highlight_fields.keys()),
                    sort_by=query.sort_by,
                    sort_type=query.sort_type or api.SortType.ascending,
                )
                if redis_res:
                    search_res.extend(redis_res["data"])
                    total += redis_res["total"]
            for redis_document in search_res:
                redis_doc_dict = json.loads(redis_document.json)
                meta_doc_content = {}
                payload_doc_content = {}
                resource_class = getattr(
                    sys.modules["models.core"],
                    camel_case(redis_doc_dict["resource_type"]),
                )

                system_attributes = [
                    "branch_name",
                    "query_policies",
                    "subpath",
                    "resource_type",
                    "meta_doc_id",
                    "payload_doc_id",
                ]
                for key, value in redis_doc_dict.items():
                    if key in resource_class.__fields__.keys():
                        meta_doc_content[key] = value
                    elif key not in system_attributes:
                        payload_doc_content[key] = value

                if (
                    not payload_doc_content
                    and query.retrieve_json_payload
                    and "payload_doc_id" in redis_doc_dict
                ):
                    payload_redis_doc = await redis.get_doc_by_id(
                        redis_doc_dict["payload_doc_id"]
                    )
                    if payload_redis_doc:
                        for key, value in payload_redis_doc.items():
                            not_payload_attr = system_attributes + list(
                                resource_class.__fields__.keys()
                            )
                            if key not in not_payload_attr:
                                payload_doc_content[key] = value

                meta_doc_content["created_at"] = datetime.fromtimestamp(
                    meta_doc_content["created_at"]
                )
                meta_doc_content["updated_at"] = datetime.fromtimestamp(
                    meta_doc_content["updated_at"]
                )
                resource_obj = resource_class.parse_obj(meta_doc_content)
                resource_base_record = resource_obj.to_record(
                    redis_doc_dict["subpath"],
                    meta_doc_content["shortname"],
                    query.include_fields,
                    redis_doc_dict["branch_name"],
                )
                if resource_base_record:
                    locked_data = await redis.get_lock_doc(
                        query.space_name,
                        query.branch_name,
                        redis_doc_dict["subpath"],
                        resource_obj.shortname,
                    )
                    if locked_data:
                        resource_base_record.attributes["locked"] = locked_data

                entry_path = (
                    settings.spaces_folder
                    / f"{query.space_name}/{branch_path(redis_doc_dict['branch_name'])}/{redis_doc_dict['subpath']}/.dm/{meta_doc_content['shortname']}"
                )

                if query.retrieve_attachments and entry_path.is_dir():
                    resource_base_record.attachments = await get_entry_attachments(
                        subpath=f"{redis_doc_dict['subpath']}/{meta_doc_content['shortname']}",
                        branch_name=redis_doc_dict["branch_name"],
                        attachments_path=entry_path,
                        filter_types=query.filter_types,
                        include_fields=query.include_fields,
                        retrieve_json_payload=query.retrieve_json_payload,
                    )

                if (
                    query.retrieve_json_payload
                    and resource_base_record.attributes["payload"]
                    and resource_base_record.attributes["payload"].content_type
                    == ContentType.json
                ):
                    resource_base_record.attributes[
                        "payload"
                    ].body = payload_doc_content

                if (
                    query.retrieve_json_payload
                    and resource_obj.payload
                    and resource_obj.payload.schema_shortname
                    and payload_doc_content is not None
                    and query.validate_schema
                ):
                    try:
                        await validate_payload_with_schema(
                            payload_data=payload_doc_content,
                            space_name=query.space_name,
                            branch_name=query.branch_name,
                            schema_shortname=resource_obj.payload.schema_shortname,
                        )
                    except:
                        continue

                if query.highlight_fields:
                    for key, value in query.highlight_fields.items():
                        resource_base_record.attributes[value] = getattr(
                            redis_document, key, None
                        )
                        
                # Don't repeat the same entry comming from different indices
                if resource_base_record in records:
                    total -= 1
                    continue

                records.append(resource_base_record)

            # Sort all entries from all schemas
            if (
                query.sort_by in core.Meta.__fields__
                and len(query.filter_schema_names) > 1
            ):
                records = sorted(
                    records,
                    key=lambda d: d.attributes[query.sort_by]
                    if query.sort_by in d.attributes
                    else "",
                    reverse=(query.sort_type == api.SortType.descending),
                )
            records = records[query.offset : (query.limit + query.offset)]

        case api.QueryType.subpath:
            subpath = query.subpath
            if subpath[0] == "/":
                subpath = "." + subpath
            path = (
                settings.spaces_folder
                / query.space_name
                / branch_path(query.branch_name)
                / subpath
            )

            if query.include_fields is None:
                query.include_fields = []

            # Gel all matching entries
            # entries_glob = ".dm/*/meta.*.json"

            meta_path = path / ".dm"
            if meta_path.is_dir() :
                path_iterator = os.scandir(meta_path) 
                for entry in path_iterator:
                    if not entry.is_dir():
                        continue

                    subpath_iterator = os.scandir(entry)
                    for one in subpath_iterator:
                        # for one in path.glob(entries_glob):
                        match = regex.FILE_PATTERN.search(str(one.path))
                        if not match or not one.is_file():
                            continue

                        shortname = match.group(1)
                        resource_name = match.group(2).lower()
                        if (
                            query.filter_types
                            and not ResourceType(resource_name) in query.filter_types
                        ):
                            logger.info(
                                resource_name + " resource is not listed in filter types"
                            )
                            continue

                        if (
                            query.filter_shortnames
                            and shortname not in query.filter_shortnames
                        ):
                            continue

                        resource_class = getattr(
                            sys.modules["models.core"], camel_case(resource_name)
                        )

                        async with aiofiles.open(one, "r") as meta_file:
                            resource_obj = resource_class.parse_raw(await meta_file.read())

                        if query.filter_tags and (
                            not resource_obj.tags
                            or not any(
                                item in resource_obj.tags for item in query.filter_tags
                            )
                        ):
                            continue

                        # apply check access
                        if not await access_control.check_access(
                            user_shortname=logged_in_user,
                            space_name=query.space_name,
                            subpath=query.subpath,
                            resource_type=ResourceType(resource_name),
                            action_type=core.ActionType.view,
                            resource_is_active=resource_obj.is_active,
                            resource_owner_shortname=resource_obj.owner_shortname,
                            resource_owner_group=resource_obj.owner_group_shortname,
                        ):
                            continue
                        total += 1
                        if len(records) >= query.limit or total < query.offset:
                            continue

                        resource_base_record = resource_obj.to_record(
                            query.subpath,
                            shortname,
                            query.include_fields,
                            query.branch_name,
                        )
                        if resource_base_record:
                            locked_data = await redis.get_lock_doc(
                                query.space_name,
                                query.branch_name,
                                query.subpath,
                                resource_obj.shortname,
                            )
                            if locked_data:
                                resource_base_record.attributes["locked"] = locked_data

                        if (
                            query.retrieve_json_payload
                            and resource_obj.payload
                            and resource_obj.payload.content_type
                            and resource_obj.payload.content_type == ContentType.json
                            and (path / resource_obj.payload.body).is_file()
                        ):
                            async with aiofiles.open(
                                path / resource_obj.payload.body, "r"
                            ) as payload_file_content:
                                resource_base_record.attributes[
                                    "payload"
                                ].body = json.loads(await payload_file_content.read())

                        if resource_obj.payload and resource_obj.payload.schema_shortname:
                            try:
                                payload_body = resource_base_record.attributes[
                                    "payload"
                                ].body
                                if not payload_body or type(payload_body) == str:
                                    async with aiofiles.open(
                                        path / resource_obj.payload.body, "r"
                                    ) as payload_file_content:
                                        payload_body = json.loads(
                                            await payload_file_content.read()
                                        )

                                if query.validate_schema:
                                    await validate_payload_with_schema(
                                        payload_data=payload_body,
                                        space_name=query.space_name,
                                        branch_name=query.branch_name,
                                        schema_shortname=resource_obj.payload.schema_shortname,
                                    )
                            except:
                                continue

                        resource_base_record.attachments = await get_entry_attachments(
                            subpath=f"{query.subpath}/{shortname}",
                            branch_name=query.branch_name,
                            attachments_path=(meta_path / shortname),
                            filter_types=query.filter_types,
                            include_fields=query.include_fields,
                            retrieve_json_payload=query.retrieve_json_payload,
                        )
                        records.append(resource_base_record)

                    subpath_iterator.close()
                if path_iterator:
                    path_iterator.close()

            # Get all matching sub folders
            # apply check access

            if meta_path.is_dir() :
                subfolders_iterator = os.scandir(path) 
                for one in subfolders_iterator:
                    if not one.is_dir():
                        continue

                    subfolder_meta = Path(one.path + "/.dm/meta.folder.json")

                    match = regex.FOLDER_PATTERN.search(str(subfolder_meta))

                    if not match or not subfolder_meta.is_file():
                        continue

                    shortname = match.group(1)
                    if not await access_control.check_access(
                        user_shortname=logged_in_user,
                        space_name=query.space_name,
                        subpath=f"{query.subpath}/{shortname}",
                        resource_type=ResourceType.folder,
                        action_type=core.ActionType.query,
                    ):
                        continue
                    if query.filter_shortnames and shortname not in query.filter_shortnames:
                        continue
                    total += 1
                    if len(records) >= query.limit or total < query.offset:
                        continue

                    folder_obj = core.Folder.parse_raw(subfolder_meta.read_text())
                    folder_record = folder_obj.to_record(
                        query.subpath, shortname, query.include_fields, query.branch_name
                    )
                    if (
                        query.retrieve_json_payload
                        and folder_obj.payload
                        and folder_obj.payload.content_type
                        and folder_obj.payload.content_type == ContentType.json
                        and isinstance(folder_obj.payload.body, str)
                        and (path / folder_obj.payload.body).is_file()
                    ):
                        async with aiofiles.open(
                            path / folder_obj.payload.body, "r"
                        ) as payload_file_content:
                            folder_record.attributes["payload"].body = json.loads(
                                await payload_file_content.read()
                            )
                            if os.path.exists(meta_path / shortname):
                                folder_record.attachments = await get_entry_attachments(
                                    subpath=f"{query.subpath if query.subpath != '/' else ''}/{shortname}",
                                    branch_name=query.branch_name,
                                    attachments_path=(meta_path / shortname),
                                    filter_types=query.filter_types,
                                    include_fields=query.include_fields,
                                    retrieve_json_payload=query.retrieve_json_payload,
                                )
                    records.append(folder_record)

                if subfolders_iterator:
                    subfolders_iterator.close()
                
            if query.sort_by:
                sort_reverse: bool = (
                    query.sort_type != None
                    and query.sort_type == api.SortType.descending
                )
                if query.sort_by in core.Record.__fields__:
                    records = sorted(records, key=lambda record: record.__getattribute__(query.sort_by), reverse=sort_reverse)  # type: ignore
                else:
                    records = sorted(records, key=lambda record: record.attributes[query.sort_by], reverse=sort_reverse)  # type: ignore

        case api.QueryType.counters:
            if not await access_control.check_access(
                user_shortname=logged_in_user,
                space_name=query.space_name,
                subpath=query.subpath,
                resource_type=ResourceType.content,
                action_type=core.ActionType.query,
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=401,
                        message="You don't have permission to this action [16]",
                    ),
                )
            for schema_name in query.filter_schema_names:
                redis_res = await redis.get_count(
                    space_name=query.space_name,
                    branch_name=query.branch_name,
                    schema_shortname=schema_name,
                )
                total += int(redis_res)

        case api.QueryType.history:
            if not await access_control.check_access(
                user_shortname=logged_in_user,
                space_name=query.space_name,
                subpath=query.subpath,
                resource_type=ResourceType.history,
                action_type=core.ActionType.query,
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=401,
                        message="You don't have permission to this action [17]",
                    ),
                )

            if not query.filter_shortnames:
                raise api.Exception(
                    status.HTTP_400_BAD_REQUEST,
                    api.Error(
                        type="request",
                        code=400,
                        message="filter_shortnames is missing",
                    ),
                )

            path = f"{settings.spaces_folder}/{query.space_name}/{branch_path(query.branch_name)}{query.subpath}/.dm/{query.filter_shortnames[0]}/history.jsonl"

            if Path(path).is_file():
                cmd = f"tail -n {query.limit + query.offset} {path} | head -n {query.limit} | tac"
                result = list(
                    filter(
                        None,
                        subprocess.run(
                            [cmd], capture_output=True, text=True, shell=True
                        ).stdout.split("\n"),
                    )
                )
                total = int(
                    subprocess.run(
                        [f"wc -l < {path}"],
                        capture_output=True,
                        text=True,
                        shell=True,
                    ).stdout,
                    10,
                )
                for line in result:
                    action_obj = json.loads(line)

                    records.append(
                        core.Record(
                            resource_type=ResourceType.history,
                            shortname=query.filter_shortnames[0],
                            subpath=query.subpath,
                            attributes=action_obj,
                            branch_name=query.branch_name,
                        ),
                    )

        case api.QueryType.events:
            trimmed_subpath = query.subpath
            if trimmed_subpath[0] == "/":
                trimmed_subpath = trimmed_subpath[1:]

            path = f"{settings.spaces_folder}/{query.space_name}/{branch_path(query.branch_name)}/.dm/events.jsonl"
            if Path(path).is_file():
                cmd = (
                    f"(tail -n {query.limit + query.offset} {path} | head -n {query.limit}; echo "
                    ") | tac"
                )
                result = list(
                    filter(
                        None,
                        subprocess.run(
                            [cmd], capture_output=True, text=True, shell=True
                        ).stdout.split("\n"),
                    )
                )
                total = int(
                    subprocess.run(
                        [f"wc -l < {path}"],
                        capture_output=True,
                        text=True,
                        shell=True,
                    ).stdout,
                    10,
                )
                for line in result:
                    action_obj = json.loads(line)

                    if not await access_control.check_access(
                        user_shortname=logged_in_user,
                        space_name=query.space_name,
                        subpath=query.subpath,
                        resource_type=action_obj["resource"]["type"],
                        action_type=core.ActionType(action_obj["request"]),
                    ):
                        continue

                    records.append(
                        core.Record(
                            resource_type=action_obj["resource"]["type"],
                            shortname=action_obj["resource"]["shortname"],
                            subpath=action_obj["resource"]["subpath"],
                            attributes=action_obj,
                        ),
                    )

    if query.jq_filter:
        records = jq.compile(query.jq_filter).input([record.to_dict() for record in records]).all()
    return total, records


async def get_last_updated_entry(
    space_name: str,
    branch_name: str,
    schema_names: list,
    retrieve_json_payload: bool,
    logged_in_user: str,
):
    report_query = api.Query(
        type=api.QueryType.search,
        space_name=space_name,
        branch_name=branch_name,
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


async def get_entry_attachments(
    subpath: str,
    attachments_path: Path,
    branch_name: str,
    filter_types: list | None = None,
    include_fields: list | None = None,
    filter_shortnames: list | None = None,
    retrieve_json_payload: bool = False,
) -> dict:
    attachments_iterator = os.scandir(attachments_path)
    attachments_dict: dict[str, list] = {}
    for attachment_entry in attachments_iterator:
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

            if filter_types and not ResourceType(attach_resource_name) in filter_types:
                logger.info(
                    attach_resource_name + " resource is not listed in filter types"
                )
                continue

            resource_class = getattr(
                sys.modules["models.core"], camel_case(attach_resource_name)
            )
            async with aiofiles.open(attachments_file, "r") as meta_file:
                resource_obj = resource_class.parse_raw(await meta_file.read())

            resource_record_obj = resource_obj.to_record(
                subpath, attach_shortname, include_fields, branch_name
            )
            if (
                retrieve_json_payload
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

    # SORT ALTERATION ATTACHMENTS BY ALTERATION.TIMESTAMP
    for attachment_name, attachments in attachments_dict.items():
        if attachment_name == ResourceType.alteration:
            attachments_dict[attachment_name] = sorted(
                attachments, key=lambda d: d.attributes["timestamp"]
            )

    return attachments_dict


async def get_resource_obj_or_none(
    *,
    space_name: str,
    branch_name: str | None,
    subpath: str,
    shortname: str,
    resource_type: str,
    user_shortname: str,
):
    resource_cls = getattr(sys.modules["models.core"], camel_case(resource_type))
    try:
        return await db.load(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            class_type=resource_cls,
            user_shortname=user_shortname,
            branch_name=branch_name,
        )
    except Exception:
        return None


async def update_payload_validation_status(
    space_name: str,
    subpath: str,
    branch_name: str | None,
    meta_obj: core.Meta,
    meta_payload: dict,
    validation_status: ValidationEnum,
):
    # Type narrowing for PyRight
    if not isinstance(meta_obj.payload, core.Payload) or not isinstance(
        meta_obj.payload.body, str
    ):
        logger.error(
            f"Meta.payload is None at repository.update_payload_validation_status"
        )
        return

    meta_path, meta_file = db.metapath(
        space_name, subpath, meta_obj.shortname, type(meta_obj)
    )
    if (
        not (meta_path / meta_file).is_file()
        or meta_obj.payload.validation_status == validation_status
    ):
        return

    meta_obj.payload.last_validated = datetime.now()
    meta_obj.payload.validation_status = validation_status

    await db.save(space_name, subpath, meta_obj, branch_name)

    redis = await RedisServices()
    _, meta_json = await redis.save_meta_doc(
        space_name, branch_name, subpath, meta_obj
    )

    meta_payload.update(meta_json)
    await redis.save_payload_doc(
        space_name,
        branch_name,
        subpath,
        meta_obj,
        meta_payload,
        meta_json["resource_type"],
    )


async def get_group_users(group_name: str) -> list[RedisDocument]:
    redis = await RedisServices()
    users_docs = await redis.search(
        space_name=settings.management_space,
        branch_name=settings.management_space_branch,
        schema_name="meta",
        filters={"subpath": ["users"]},
        limit=10000,
        offset=0,
        search=f"@groups:{{{group_name}}}",
    )

    if users_docs:
        return users_docs["data"]

    return []


async def validate_subpath_data(
    space_name: str,
    subpath: str,
    branch_name: str | None,
    user_shortname: str,
    invalid_folders: list,
    folders_report: dict[str, dict],
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
                branch_name,
                user_shortname,
                invalid_folders,
                folders_report,
            )
            continue

        folder_meta = Path(f"{folder.path}/meta.folder.json")
        folder_name = "/".join(subpath.split("/")[folder_name_index:])
        if not folder_meta.is_file():
            continue

        validation_status = ValidationEnum.valid
        folder_meta_content = None
        folder_meta_payload = None
        try:
            folder_meta_content = await db.load(
                space_name=space_name,
                subpath=folder_name,
                shortname="",
                class_type=core.Folder,
                user_shortname=user_shortname,
                branch_name=branch_name,
            )
            if (
                folder_meta_content.payload
                and folder_meta_content.payload.content_type == ContentType.json
            ):
                payload_path = "/"
                subpath_parts = subpath.split("/")
                if len(subpath_parts) > (len(spaces_path_parts) + 2):
                    payload_path = "/".join(subpath_parts[folder_name_index:-1])
                folder_meta_payload = db.load_resource_payload(
                    space_name,
                    payload_path,
                    str(folder_meta_content.payload.body),
                    core.Folder,
                    branch_name,
                )
                await validate_payload_with_schema(
                    payload_data=folder_meta_payload,
                    space_name=space_name,
                    branch_name=branch_name or settings.default_branch,
                    schema_shortname=folder_meta_content.payload.schema_shortname, #type: ignore
                )
        except:
            invalid_folders.append(folder_name)
            validation_status = ValidationEnum.invalid
        finally:
            # Update payload validation status
            if (
                folder_meta_content
                and folder_meta_content.payload
                and folder_meta_content.payload.content_type == ContentType.json
                and folder_meta_payload
            ):
                await update_payload_validation_status(
                    space_name,
                    folder_name,
                    branch_name,
                    folder_meta_content,
                    folder_meta_payload,
                    validation_status,
                )

        if folder_name not in folders_report:
            folders_report[folder_name] = {}

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
                if "invalid_entries" not in folders_report[folder_name]:
                    folders_report[folder_name]["invalid_entries"] = [entry.name]
                else:
                    folders_report[folder_name]["invalid_entries"].append(entry.name)
                continue

            entry_shortname = entry_match.group(1)
            entry_resource_type = entry_match.group(2)

            if folder_name == "schema" and entry_shortname == "meta_schema":
                if not folders_report[folder_name]:
                    folders_report[folder_name]["valid_entries"] = 0
                folders_report[folder_name]["valid_entries"] += 1
                continue

            validation_status = ValidationEnum.valid
            entry_meta_obj = None
            payload_file_content = None
            try:
                resource_class = getattr(
                    sys.modules["models.core"], camel_case(entry_resource_type)
                )
                entry_meta_obj = await db.load(
                    space_name=space_name,
                    subpath=folder_name,
                    shortname=entry_shortname,
                    class_type=resource_class,
                    user_shortname=user_shortname,
                    branch_name=branch_name,
                )
                if entry_meta_obj.shortname != entry_shortname:
                    raise Exception()

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
                        raise Exception()
                elif (
                    entry_meta_obj.payload
                    and entry_meta_obj.payload.content_type == ContentType.json
                ):
                    payload_file_path = f"{subpath}/{entry_meta_obj.payload.body}"
                    if not entry_meta_obj.payload.body.endswith(
                        ".json"
                    ) or not os.access(payload_file_path, os.W_OK):
                        raise Exception()
                    payload_file_content = db.load_resource_payload(
                        space_name,
                        folder_name,
                        entry_meta_obj.payload.body,
                        resource_class,
                        branch_name,
                    )
                    if entry_meta_obj.payload.schema_shortname:
                        await validate_payload_with_schema(
                            payload_data=payload_file_content,
                            space_name=space_name,
                            branch_name=branch_name or settings.default_branch,
                            schema_shortname=entry_meta_obj.payload.schema_shortname,
                        )

                # VALIDATE ENTRY ATTACHMENTS
                attachments_path = f"{folder.path}/{entry_shortname}"
                attachment_folders = os.scandir(attachments_path)
                for attachment_folder in attachment_folders:
                    if attachment_folder.is_file():
                        continue

                    attachment_folder_files = os.scandir(attachment_folder)
                    for attachment_folder_file in attachment_folder_files:
                        if (
                            not attachment_folder_file.is_file()
                            or not os.access(attachment_folder_file.path, os.W_OK)
                            or not os.access(attachment_folder_file.path, os.R_OK)
                        ):
                            raise Exception()

                if "valid_entries" not in folders_report[folder_name]:
                    folders_report[folder_name]["valid_entries"] = 1
                else:
                    folders_report[folder_name]["valid_entries"] += 1
            except:
                if "invalid_entries" not in folders_report[folder_name]:
                    folders_report[folder_name]["invalid_entries"] = [entry_shortname]
                else:
                    folders_report[folder_name]["invalid_entries"].append(
                        entry_shortname
                    )
                validation_status = ValidationEnum.invalid
            finally:
                # Update payload validation status
                if (
                    entry_meta_obj
                    and entry_meta_obj.payload
                    and entry_meta_obj.payload.content_type == ContentType.json
                    and payload_file_content
                ):
                    await update_payload_validation_status(
                        space_name,
                        folder_name,
                        branch_name,
                        entry_meta_obj,
                        payload_file_content,
                        validation_status,
                    )

        if not folders_report.get(folder_name, {}):
            del folders_report[folder_name]


async def _sys_update_model(
    space_name: str,
    subpath: str,
    meta: core.Meta,
    branch_name: str | None,
    updates: dict
) -> bool:
    """
    Update @meta entry and its payload by @updates dict of attributes in the
    *Used by the system only, not APIs*
    """

    meta.updated_at = datetime.now()
    meta_updated = False
    payload_updated = False
    payload_dict = None

    try:
        body = str(meta.payload.body) if meta and meta.payload else ""
        payload_dict = db.load_resource_payload(
            space_name, subpath, body, core.Content, branch_name
        )
    except :
        pass

    restricted_fields = [
        "uuid",
        "shortname",
        "created_at",
        "updated_at",
        "owner_shortname",
        "payload",
    ]
    for key, value in updates.items():
        if key in restricted_fields:
            continue

        if key in meta.__fields__.keys():
            meta_updated = True
            meta.__setattr__(key, value)
        elif payload_dict:
            payload_dict[key] = value
            payload_updated = True
        
    redis = await RedisServices()
    if meta_updated:
        await db.save(space_name, subpath, meta, branch_name)

        await redis.save_meta_doc(space_name, branch_name, subpath, meta)

    if payload_updated:
        if meta and meta.payload and meta.payload.schema_shortname and payload_dict:
            await validate_payload_with_schema(payload_dict, space_name, meta.payload.schema_shortname, branch_name)
        
        if payload_dict:
            await db.save_payload_from_json(space_name, subpath, meta, payload_dict, branch_name)

        # print(f"\n\n =>> meta.json(): {type(json.loads(meta.json()))} --- {json.loads(meta.json())} -- {meta.dict()} \n")
        if payload_dict:
            payload_dict.update(json.loads(meta.json()))
        if payload_dict:
            await redis.save_payload_doc(space_name, branch_name, subpath, meta, payload_dict, ResourceType(snake_case(type(meta).__name__)))

    return True 
