import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
import aiofiles
from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.logger import logger
import models.api as api
import models.core as core
import utils.regex as regex
from models.enums import ContentType, Language, ResourceType
from data_adapters.adapter import data_adapter as db
from utils.access_control import access_control
from utils.custom_validations import validate_payload_with_schema
from utils.helpers import (
    camel_case,
    flatten_all,
    snake_case, str_to_datetime, alter_dict_keys,
)
from utils.internal_error_code import InternalErrorCode
from utils.jwt import generate_jwt
from utils.plugin_manager import plugin_manager
from utils.redis_services import RedisServices
from utils.settings import settings
from utils.spaces import get_spaces


# import redis.commands.search.reducers as reducers


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
    """Given a query return the total and the records

    Parameters
    ----------
    query: api.Query
        query of type [spaces, search, subpath]

    Returns
    -------
    Total, Records

    """
    if settings.active_data_db == "sql":
        return await db.query(query, logged_in_user)

    redis_query_policies = await access_control.get_user_query_policies(
        logged_in_user, query.space_name, query.subpath
    )

    records: list[core.Record] = []
    total: int = 0
    spaces = await get_spaces()
    match query.type:
        case api.QueryType.spaces:
            for space_json in spaces.values():
                space = core.Space.model_validate_json(space_json)

                if await access_control.check_space_access(
                    logged_in_user, space.shortname
                ):
                    total += 1
                    records.append(
                        space.to_record(
                            query.subpath,
                            space.shortname,
                            query.include_fields if query.include_fields else [],
                        )
                    )
            if not query.sort_by:
                query.sort_by = "ordinal"
            if records:
                record_fields = list(records[0].model_fields.keys())
                records = sorted(
                    records,
                    key=lambda d: d.__getattribute__(query.sort_by)
                    if query.sort_by in record_fields
                    else d.attributes[query.sort_by]
                    if query.sort_by in d.attributes and d.attributes[query.sort_by] is not None
                    else 1,
                    reverse=(query.sort_type == api.SortType.descending),
                )

        case api.QueryType.search:
            search_res, total = await redis_query_search(query, logged_in_user, redis_query_policies)
            res_data: list = []
            for redis_document in search_res:
                res_data.append(json.loads(redis_document))
            if len(query.filter_schema_names) > 1:
                if query.sort_by:
                    res_data = sorted(
                        res_data,
                        key=lambda d: d[query.sort_by]
                        if query.sort_by in d
                        else d.get("payload", {})[query.sort_by]
                        if query.sort_by in d.get("payload", {})
                        else "",
                        reverse=(query.sort_type == api.SortType.descending),
                    )
                res_data = res_data[query.offset: (query.limit + query.offset)]

            async with RedisServices() as redis_services:
                for redis_doc_dict in res_data:
                    try:
                        resource_base_record = await get_record_from_redis_doc(
                            space_name=query.space_name,
                            doc=redis_doc_dict,
                            retrieve_json_payload=query.retrieve_json_payload,
                            retrieve_attachments=query.retrieve_attachments,
                            validate_schema=query.validate_schema,
                            filter_types=query.filter_types,
                            retrieve_lock_status=query.retrieve_lock_status,
                        )
                    except Exception:
                        # Incase of schema validation error
                        continue

                    # Don't repeat the same entry comming from different indices
                    # if resource_base_record in records:
                    #     total -= 1
                    #     continue

                    if query.highlight_fields:
                        for key, value in query.highlight_fields.items():
                            resource_base_record.attributes[value] = getattr(
                                redis_doc_dict, key, None
                            )

                    resource_base_record.attributes = alter_dict_keys(
                        jsonable_encoder(resource_base_record.attributes, exclude_none=True),
                        query.include_fields,
                        query.exclude_fields,
                    )

                    records.append(resource_base_record)

        case api.QueryType.subpath:
            subpath = query.subpath
            if subpath[0] == "/":
                subpath = "." + subpath
            path = (
                settings.spaces_folder
                / query.space_name
                / subpath
            )

            if query.include_fields is None:
                query.include_fields = []

            # Gel all matching entries
            # entries_glob = ".dm/*/meta.*.json"

            meta_path = path / ".dm"
            if meta_path.is_dir():
                path_iterator = os.scandir(meta_path)
                async with RedisServices() as redis_services:
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
                                and ResourceType(resource_name) not in query.filter_types
                            ):
                                continue

                            if (
                                query.filter_shortnames
                                and shortname not in query.filter_shortnames
                            ):
                                continue

                            resource_class = getattr(
                                sys.modules["models.core"], camel_case(
                                    resource_name)
                            )

                            async with aiofiles.open(one, "r") as meta_file:
                                resource_obj = resource_class.model_validate_json(
                                    await meta_file.read()
                                )

                            if query.filter_tags and (
                                not resource_obj.tags
                                or not any(
                                    item in resource_obj.tags
                                    for item in query.filter_tags
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
                                entry_shortname=shortname,
                            ):
                                continue
                            total += 1
                            if len(records) >= query.limit or total < query.offset:
                                continue

                            resource_base_record = resource_obj.to_record(
                                query.subpath,
                                shortname,
                                query.include_fields,
                            )
                            if query.retrieve_lock_status and resource_base_record:
                               locked_data = await redis_services.get_lock_doc(
                                   query.space_name,
                                   query.subpath,
                                   resource_obj.shortname,
                               )
                               if locked_data:
                                   resource_base_record.attributes[
                                       "locked"
                                   ] = locked_data

                            if (
                                query.retrieve_json_payload
                                and resource_obj.payload
                                and resource_obj.payload.content_type
                                and resource_obj.payload.content_type
                                == ContentType.json
                                and (path / resource_obj.payload.body).is_file()
                            ):
                                async with aiofiles.open(
                                    path / resource_obj.payload.body, "r"
                                ) as payload_file_content:
                                    resource_base_record.attributes[
                                        "payload"
                                    ].body = json.loads(
                                        await payload_file_content.read()
                                    )

                            if (
                                resource_obj.payload
                                and resource_obj.payload.schema_shortname
                            ):
                                try:
                                    payload_body = resource_base_record.attributes[
                                        "payload"
                                    ].body
                                    if not payload_body or isinstance(payload_body, str):
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
                                            schema_shortname=resource_obj.payload.schema_shortname,
                                        )
                                except Exception:
                                    continue

                            resource_base_record.attachments = (
                                await get_entry_attachments(
                                    subpath=f"{query.subpath}/{shortname}",
                                    attachments_path=(meta_path / shortname),
                                    filter_types=query.filter_types,
                                    include_fields=query.include_fields,
                                    retrieve_json_payload=query.retrieve_json_payload,
                                )
                            )
                            records.append(resource_base_record)

                        subpath_iterator.close()
                    if path_iterator:
                        path_iterator.close()

            # Get all matching sub folders
            # apply check access

            if meta_path.is_dir():
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
                        entry_shortname=shortname
                    ):
                        continue
                    if (
                        query.filter_shortnames
                        and shortname not in query.filter_shortnames
                    ):
                        continue
                    total += 1
                    if len(records) >= query.limit or total < query.offset:
                        continue

                    folder_obj = core.Folder.model_validate_json(
                        subfolder_meta.read_text())
                    folder_record = folder_obj.to_record(
                        query.subpath,
                        shortname,
                        query.include_fields,
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
                    query.sort_type is not None
                    and query.sort_type == api.SortType.descending
                )
                if query.sort_by in core.Record.model_fields:
                    records = sorted(
                        records,
                        key=lambda record: record.__getattribute__(
                            str(query.sort_by)),
                        reverse=sort_reverse,
                    )
                else:
                    records = sorted(
                        records,
                        key=lambda record: record.attributes[str(
                            query.sort_by)],
                        reverse=sort_reverse,
                    )

        case api.QueryType.counters:
            if not await access_control.check_access(
                user_shortname=logged_in_user,
                space_name=query.space_name,
                subpath=query.subpath,
                resource_type=ResourceType.content,
                action_type=core.ActionType.query
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.NOT_ALLOWED,
                        message="You don't have permission to this action [16]",
                    ),
                )
            async with RedisServices() as redis_services:
                for schema_name in query.filter_schema_names:
                    redis_res = await redis_services.get_count(
                        space_name=query.space_name,
                        schema_shortname=schema_name,
                    )
                    total += int(redis_res)

        case api.QueryType.tags:
            async with RedisServices() as redis_services:
                query.sort_by = "tags"
                query.aggregation_data = api.RedisAggregate(
                    group_by=["@tags"],
                    reducers=[
                        api.RedisReducer(
                            reducer_name="count",
                            alias="freq"
                        )
                    ]
                )
                rows = await redis_query_aggregate(
                    query=query,
                    redis_query_policies=redis_query_policies
                )
                records.append(
                    core.Record(
                        resource_type=ResourceType.content,
                        shortname="tags_frequency",
                        subpath=query.subpath,
                        attributes={"result": rows},
                    )
                )
                total = 1

        case api.QueryType.random:
            query.aggregation_data = api.RedisAggregate(
                load=["@__key"],
                group_by=["@resource_type"],
                reducers=[
                    api.RedisReducer(
                        reducer_name="random_sample",
                        alias="id",
                        args=["@__key", query.limit]
                    )
                ]
            )
            async with RedisServices() as redis_services:
                rows = await redis_query_aggregate(
                    query=query,
                    redis_query_policies=redis_query_policies
                )
                ids = []
                for row in rows:
                    ids.extend(row[3])
                docs = await redis_services.get_docs_by_ids(ids)
                total = len(ids)
                for doc in docs:
                    doc = doc[0]
                    if query.retrieve_json_payload and doc.get("payload_doc_id", None):
                        doc["payload"]["body"] = await redis_services.get_payload_doc(
                            doc["payload_doc_id"], doc["resource_type"]
                        )
                    record = core.Record(
                        shortname=doc["shortname"],
                        resource_type=doc["resource_type"],
                        uuid=doc["uuid"],
                        subpath=doc["subpath"],
                        attributes={"payload": doc.get("payload")},
                    )
                    entry_path = (
                        settings.spaces_folder
                        / f"{query.space_name}/{doc['subpath']}/.dm/{doc['shortname']}"
                    )
                    if query.retrieve_attachments and entry_path.is_dir():
                        record.attachments = await get_entry_attachments(
                            subpath=f"{doc['subpath']}/{doc['shortname']}",
                            attachments_path=entry_path,
                            filter_types=query.filter_types,
                            include_fields=query.include_fields,
                            retrieve_json_payload=query.retrieve_json_payload,
                        )
                    records.append(record)

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
                        code=InternalErrorCode.NOT_ALLOWED,
                        message="You don't have permission to this action [17]",
                    ),
                )

            if not query.filter_shortnames:
                raise api.Exception(
                    status.HTTP_400_BAD_REQUEST,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.MISSING_FILTER_SHORTNAMES,
                        message="filter_shortnames is missing",
                    ),
                )

            path = Path(f"{settings.spaces_folder}/{query.space_name}/"
                        f"{query.subpath}/.dm/{query.filter_shortnames[0]}/history.jsonl")
            if path.is_file():
                r1 = subprocess.Popen(
                    ["tail", "-n", f"+{query.offset}", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                rn = subprocess.Popen(
                    ["sed", "-e", "$a\\\n"], stdin=r1.stdout, stdout=subprocess.PIPE,
                )
                r2 = subprocess.Popen(
                    ["head", "-n", f"{query.limit}"], stdin=rn.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                r3 = subprocess.Popen(
                    ["tac"], stdin=r2.stdout, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                r4, _ = r3.communicate()
                if r4 is None:
                    result = []
                else:
                    result = list(
                        filter(
                            None,
                            r4.decode().split("\n"),
                        )
                    )

                r, _ = subprocess.Popen(
                        f"wc -l {path}".split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE
                ).communicate()

                if r is None:
                    total = 0
                else:
                    total = int(
                        r.decode().split()[0],
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
                        ),
                    )

        case api.QueryType.events:
            trimmed_subpath = query.subpath
            if trimmed_subpath[0] == "/":
                trimmed_subpath = trimmed_subpath[1:]

            path = Path(
                f"{settings.spaces_folder}/{query.space_name}/.dm/events.jsonl")
            if path.is_file():
                result = []
                if query.search:
                    p = subprocess.Popen(
                        ["grep", f'"{query.search}"', path], stdout=subprocess.PIPE
                    )
                    p = subprocess.Popen(
                        ["tail", "-n", f"{query.limit + query.offset}"],
                        stdin=p.stdout,
                        stdout=subprocess.PIPE,
                    )
                    p = subprocess.Popen(
                        ["tac"], stdin=p.stdout, stdout=subprocess.PIPE
                    )
                    if query.offset > 0:
                        p = subprocess.Popen(
                            ["sed", f"1,{query.offset}d"],
                            stdin=p.stdout,
                            stdout=subprocess.PIPE,
                        )
                    r, _ = p.communicate()
                    result = list(filter(None, r.decode("utf-8").split("\n")))
                else:
                    r1 = subprocess.Popen(
                        ["tail", "-n", f"{query.limit + query.offset}", path], stdout=subprocess.PIPE,
                    )

                    r1 = subprocess.Popen(
                        ["sed", "-e", "$a\\\n"], stdin=r1.stdout, stdout=subprocess.PIPE,
                    )
                    if query.offset > 0:
                        r1 = subprocess.Popen(
                            ["head", "-n", f"{query.limit}"], stdin=r1.stdout, stdout=subprocess.PIPE,
                        )

                    r6, _ = subprocess.Popen(
                        ["tac"], stdin=r1.stdout, stdout=subprocess.PIPE,
                    ).communicate()

                    if r6 is None:
                        result = []
                    else:
                        result = list(
                            filter(
                                None,
                                r6.decode().split("\n"),
                            )
                        )

                r, _ = subprocess.Popen(
                    f"wc -l {path}".split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE
                ).communicate()

                if r is None:
                    total = 0
                else:
                    total = int(
                        r.decode().split()[0],
                        10,
                    )

                for line in result:
                    action_obj = json.loads(line)

                    if (
                        query.from_date
                        and str_to_datetime(action_obj["timestamp"]) < query.from_date
                    ):
                        continue

                    if (
                        query.to_date
                        and str_to_datetime(action_obj["timestamp"]) > query.to_date
                    ):
                        break

                    if not await access_control.check_access(
                        user_shortname=logged_in_user,
                        space_name=query.space_name,
                        subpath=action_obj.get(
                            "resource", {}).get("subpath", "/"),
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

        case api.QueryType.aggregation:
            rows = await redis_query_aggregate(
                query=query, redis_query_policies=redis_query_policies
            )
            total = len(rows)
            for idx, row in enumerate(rows):
                record = core.Record(
                    resource_type=ResourceType.content,
                    shortname=str(idx+1),
                    subpath=query.subpath,
                    attributes=row["extra_attributes"]
                )
                records.append(record)

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


async def get_entry_attachments(
    subpath: str,
    attachments_path: Path,
    filter_types: list | None = None,
    include_fields: list | None = None,
    filter_shortnames: list | None = None,
    retrieve_json_payload: bool = False,
) -> dict:
    if not attachments_path.is_dir():
        return {}
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
                        f"Bad attachment ... {attachments_file=}") from e

            resource_record_obj = resource_obj.to_record(
                subpath, attach_shortname, include_fields
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
                attachments_dict[ResourceType(attach_resource_name)].append(
                    resource_record_obj)
            else:
                attachments_dict[ResourceType(attach_resource_name)] = [resource_record_obj]
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
                f"Invalid attachment entry:{attachments_path/attachment_name}.\
            Error: {e.args}"
            )

    return attachments_dict


async def redis_query_aggregate(
    query: api.Query,
    redis_query_policies: list = [],
) -> list:
    if not query.aggregation_data:
        return []

    if len(query.filter_schema_names) > 1:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="query", code=InternalErrorCode.INVALID_STANDALONE_DATA, message="only one argument is allowed in filter_schema_names"
            ),
        )

    created_at_search = ""
    if query.from_date and query.to_date:
        created_at_search = (
            "[" + f"{query.from_date.timestamp()} {query.to_date.timestamp()}" + "]"
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

    async with RedisServices() as redis_services:
        value = await redis_services.aggregate(
            space_name=query.space_name,
            schema_name=query.filter_schema_names[0],
            search=str(query.search),
            filters={
                "resource_type": query.filter_types or [],
                "shortname": query.filter_shortnames or [],
                "subpath": [query.subpath],
                "query_policies": redis_query_policies,
                "created_at": created_at_search,
            },
            load=query.aggregation_data.load,
            group_by=query.aggregation_data.group_by,
            reducers=query.aggregation_data.reducers,
            exact_subpath=query.exact_subpath,
            sort_by=query.sort_by,
            max=query.limit,
            sort_type=query.sort_type or api.SortType.ascending,
        )
        if isinstance(value, list):
            return value
        else:
            return []


async def redis_query_search(
    query: api.Query, user_shortname: str, redis_query_policies: list = []
) -> tuple:
    search_res: list = []
    total = 0

    if not query.filter_schema_names:
        query.filter_schema_names = ["meta"]

    created_at_search = ""

    if query.from_date and query.to_date:
        created_at_search = (
            "[" + f"{query.from_date.timestamp()} {query.to_date.timestamp()}" + "]"
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

    limit = query.limit
    offset = query.offset
    if len(query.filter_schema_names) > 1 and query.sort_by:
        limit += offset
        offset = 0

    async with RedisServices() as redis_services:
        for schema_name in query.filter_schema_names:
            redis_res = await redis_services.search(
                space_name=query.space_name,
                schema_name=schema_name,
                search=str(query.search),
                filters={
                    "resource_type": query.filter_types or [],
                    "shortname": query.filter_shortnames or [],
                    "tags": query.filter_tags or [],
                    "subpath": [query.subpath],
                    "query_policies": redis_query_policies,
                    "user_shortname": user_shortname,
                    "created_at": created_at_search,
                },
                exact_subpath=query.exact_subpath,
                limit=limit,
                offset=offset,
                highlight_fields=list(query.highlight_fields.keys()),
                sort_by=query.sort_by,
                sort_type=query.sort_type or api.SortType.ascending,
            )

            if redis_res:
                search_res.extend(redis_res["data"])
                total += redis_res["total"]
    return search_res, total


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

        folder_meta_content = None
        folder_meta_payload = None
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
                if folder_meta_content.payload.schema_shortname:
                    await validate_payload_with_schema(
                        payload_data=folder_meta_payload,
                        space_name=space_name,
                        schema_shortname=folder_meta_content.payload.schema_shortname,
                    )
        except Exception:
            invalid_folders.append(folder_name)

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
                        issue)

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
    entry_meta_obj = await db.load(
        space_name=space_name,
        subpath=subpath,
        shortname=shortname,
        class_type=resource_class,
        user_shortname=user_shortname,
    )
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
        ) or not os.access(payload_file_path, os.W_OK):  # type: ignore
            raise Exception(
                f"can't access this payload {payload_file_path}"
            )
        payload_file_content = await db.load_resource_payload(
            space_name,
            subpath,
            entry_meta_obj.payload.body,
            resource_class,
        )
        if entry_meta_obj.payload.schema_shortname:
            await validate_payload_with_schema(
                payload_data=payload_file_content,
                space_name=space_name,
                schema_shortname=entry_meta_obj.payload.schema_shortname,
            )

    if(
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
    payload_dict: dict = {},
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
            payload_dict = await db.load_resource_payload(
                space_name, subpath, body, core.Content
            )
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
        await db.save(space_name, subpath, meta)
    if payload_updated and meta.payload and meta.payload.schema_shortname:
        await validate_payload_with_schema(
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
            payload_dict.update(json.loads(meta.model_dump_json(exclude_none=True,warnings="error")))
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
            payload.update(json.loads(meta.model_dump_json(exclude_none=True,warnings="error")))
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
    attachments: dict[str, list] = await get_entry_attachments(
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


async def get_record_from_redis_doc(
    space_name: str,
    doc: dict,
    retrieve_json_payload: bool = False,
    retrieve_attachments: bool = False,
    validate_schema: bool = False,
    filter_types: list | None = None,
    retrieve_lock_status: bool = False,
) -> core.Record:
    meta_doc_content = {}
    payload_doc_content = {}
    resource_class = getattr(
        sys.modules["models.core"],
        camel_case(doc["resource_type"]),
    )

    for key, value in doc.items():
        if key in resource_class.model_fields.keys():
            meta_doc_content[key] = value
        elif key not in RedisServices.SYS_ATTRIBUTES:
            payload_doc_content[key] = value

    async with RedisServices() as redis_services:
        # Get payload doc
        if (
            not payload_doc_content
            and retrieve_json_payload
            and "payload_doc_id" in doc
        ):
            payload_doc_content = await redis_services.get_payload_doc(
                doc["payload_doc_id"], doc["resource_type"]
            )

    meta_doc_content["created_at"] = datetime.fromtimestamp(
        meta_doc_content["created_at"]
    )
    meta_doc_content["updated_at"] = datetime.fromtimestamp(
        meta_doc_content["updated_at"]
    )
    resource_obj = resource_class.model_validate(meta_doc_content)
    resource_base_record = resource_obj.to_record(
        doc["subpath"],
        meta_doc_content["shortname"],
        [],
    )

    # Get lock data
    if retrieve_lock_status:
        locked_data = await redis_services.get_lock_doc(
            space_name,
            doc["subpath"],
            doc["shortname"],
        )
        if locked_data:
            resource_base_record.attributes["locked"] = locked_data


    # Get attachments
    entry_path = (
        settings.spaces_folder
        / f"{space_name}/{doc['subpath']}/.dm/{meta_doc_content['shortname']}"
    )
    if retrieve_attachments and entry_path.is_dir():
        resource_base_record.attachments = await get_entry_attachments(
            subpath=f"{doc['subpath']}/{meta_doc_content['shortname']}",
            attachments_path=entry_path,
            filter_types=filter_types,
            retrieve_json_payload=retrieve_json_payload,
        )

    if (
        retrieve_json_payload
        and resource_base_record.attributes["payload"]
        and resource_base_record.attributes["payload"].content_type == ContentType.json
    ):
        resource_base_record.attributes["payload"].body = payload_doc_content

    # Validate payload
    if (
        retrieve_json_payload
        and resource_obj.payload
        and resource_obj.payload.schema_shortname
        and payload_doc_content is not None
        and validate_schema
    ):
        await validate_payload_with_schema(
            payload_data=payload_doc_content,
            space_name=space_name,
            schema_shortname=resource_obj.payload.schema_shortname,
        )

    if isinstance(resource_base_record, core.Record):
        return resource_base_record
    else:
        return core.Record()


async def get_entry_by_var(
    key: str,
    val: str,
    logged_in_user,
    retrieve_json_payload: bool = False,
    retrieve_attachments: bool = False,
    retrieve_lock_status: bool = False,
):
    if settings.active_data_db == "sql":
        return await db.get_entry_by_criteria({key: val})

    spaces = await get_spaces()
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
    async with RedisServices() as redis_services:
        await redis_services.set_key(
            f"short/{token_uuid}",
            url,
            ex=60 * 60 * 48,
            nx=False,
        )

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
    async with RedisServices() as redis_services:
        await redis_services.set_key(
            f"users:login:invitation:{invitation_token}",
            invitation_value
        )

    return core.User.invitation_url_template()\
        .replace("{url}", settings.invitation_link)\
        .replace("{token}", invitation_token)\
        .replace("{lang}", Language.code(user.language))\
        .replace("{user_type}", user.type)


async def delete_space(space_name, record, owner_shortname):
    if settings.active_data_db == "sql":
        resource_obj = core.Meta.from_record(
            record=record, owner_shortname=owner_shortname
        )
        await db.delete(space_name, record.subpath, resource_obj, owner_shortname)

    os.system(f"rm -r {settings.spaces_folder}/{space_name}")
