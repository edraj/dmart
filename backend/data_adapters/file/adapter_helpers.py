import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from fastapi import status
from fastapi.encoders import jsonable_encoder
import aiofiles
from data_adapters.file.redis_services import RedisServices
from models import core, api
from utils import regex

from utils.helpers import camel_case, alter_dict_keys, str_to_datetime, flatten_all
from utils.internal_error_code import InternalErrorCode
from utils.query_policies_helper import get_user_query_policies
from utils.settings import settings


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


async def get_record_from_redis_doc(
        db,
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
        resource_base_record.attachments = await db.get_entry_attachments(
            subpath=f"{doc['subpath']}/{meta_doc_content['shortname']}",
            attachments_path=entry_path,
            filter_types=filter_types,
            retrieve_json_payload=retrieve_json_payload,
        )

    if (
            retrieve_json_payload
            and resource_base_record.attributes["payload"]
            and resource_base_record.attributes["payload"].content_type == core.ContentType.json
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
        await db.validate_payload_with_schema(
            payload_data=payload_doc_content,
            space_name=space_name,
            schema_shortname=resource_obj.payload.schema_shortname,
        )

    if isinstance(resource_base_record, core.Record):
        return resource_base_record
    else:
        return core.Record()

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
                type="query", code=InternalErrorCode.INVALID_STANDALONE_DATA,
                message="only one argument is allowed in filter_schema_names"
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


async def serve_query_space(db, query, logged_in_user):
    records = []
    total = 0

    spaces = await db.get_spaces()
    for space_json in spaces.values():
        space = core.Space.model_validate_json(space_json)
        from utils.access_control import access_control
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

    return total, records


async def serve_query_search(db, query, logged_in_user):
    records = []
    total = 0

    redis_query_policies = await get_user_query_policies(
        db, logged_in_user, query.space_name, query.subpath
    )

    search_res, total = await redis_query_search(query, logged_in_user, redis_query_policies)
    res_data = []
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

    for redis_doc_dict in res_data:
        try:
            resource_base_record = await get_record_from_redis_doc(
                db,
                space_name=query.space_name,
                doc=redis_doc_dict,
                retrieve_json_payload=query.retrieve_json_payload,
                retrieve_attachments=query.retrieve_attachments,
                validate_schema=query.validate_schema,
                filter_types=query.filter_types,
                retrieve_lock_status=query.retrieve_lock_status,
            )
        except Exception as e:
            print("Error in get_record_from_redis_doc", e)
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

    return total, records


async def serve_query_subpath_sorting(query, records):
    sort_reverse = (
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

    return records


async def serve_query_subpath_check_payload(db, resource_base_record, path, resource_obj, query):
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
        await db.validate_payload_with_schema(
            payload_data=payload_body,
            space_name=query.space_name,
            schema_shortname=resource_obj.payload.schema_shortname,
        )


async def set_attachment_for_payload(db, path, folder_obj, folder_record, query, meta_path, shortname):
    if (
            query.retrieve_json_payload
            and folder_obj.payload
            and folder_obj.payload.content_type
            and folder_obj.payload.content_type == core.ContentType.json
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
                folder_record.attachments = await db.get_entry_attachments(
                    subpath=f"{query.subpath if query.subpath != '/' else ''}/{shortname}",
                    attachments_path=(meta_path / shortname),
                    filter_types=query.filter_types,
                    include_fields=query.include_fields,
                    retrieve_json_payload=query.retrieve_json_payload,
                )

    return folder_record


async def serve_query_subpath(db, query, logged_in_user):
    records : list[core.Record] = []
    total = 0

    from utils.access_control import access_control

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

    meta_path = path / ".dm"
    if meta_path.is_dir():
        path_iterator = os.scandir(meta_path)
        async with RedisServices() as redis_services:
            for entry in path_iterator:
                if not entry.is_dir():
                    continue
                subpath_iterator = os.scandir(str(entry.path))
                for one in subpath_iterator:
                    # for one in path.glob(entries_glob):
                    match = regex.FILE_PATTERN.search(str(one.path))
                    if not match or not one.is_file():
                        continue

                    shortname = match.group(1)
                    resource_name = match.group(2).lower()
                    if (
                        query.filter_types
                        and core.ResourceType(resource_name) not in query.filter_types
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
                    async with aiofiles.open(str(one.path), "r") as meta_file:
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
                        resource_type=core.ResourceType(resource_name),
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

                    resource_base_record : core.Record = resource_obj.to_record(
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
                        == core.ContentType.json
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
                            await serve_query_subpath_check_payload(db, resource_base_record, path, resource_obj, query)
                        except Exception:
                            continue

                    resource_base_record.attachments = (
                        await db.get_entry_attachments(
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
                    resource_type=core.ResourceType.folder,
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
                subfolder_meta.read_text()
            )
            folder_record = folder_obj.to_record(
                query.subpath,
                shortname,
                query.include_fields,
            )

            await set_attachment_for_payload(
                db, path, folder_obj, folder_record, query, meta_path, shortname
            )

            records.append(folder_record)

        if subfolders_iterator:
            subfolders_iterator.close()

    if query.sort_by:
        records = await serve_query_subpath_sorting(query, records)

    return total, records


async def serve_query_counters(query, logged_in_user):
    records : list = []
    total = 0
    from utils.access_control import access_control
    if not await access_control.check_access(
            user_shortname=logged_in_user,
            space_name=query.space_name,
            subpath=query.subpath,
            resource_type=core.ResourceType.content,
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

    return total, records


async def serve_query_tags(db, query, user_shortname):
    records = []
    total = 0

    redis_query_policies = await get_user_query_policies(
        db, user_shortname, query.space_name, query.subpath
    )

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
            resource_type=core.ResourceType.content,
            shortname="tags_frequency",
            subpath=query.subpath,
            attributes={"result": rows},
        )
    )
    total = 1

    return total, records


async def serve_query_random(db, query, user_shortname):
    records = []
    total = 0

    redis_query_policies = await get_user_query_policies(
        db, user_shortname, query.space_name, query.subpath
    )
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
                record.attachments = await db.get_entry_attachments(
                    subpath=f"{doc['subpath']}/{doc['shortname']}",
                    attachments_path=entry_path,
                    filter_types=query.filter_types,
                    include_fields=query.include_fields,
                    retrieve_json_payload=query.retrieve_json_payload,
                )
            records.append(record)

    return total, records


async def serve_query_history(query, logged_in_user):
    records = []
    total = 0
    from utils.access_control import access_control
    if not await access_control.check_access(
            user_shortname=logged_in_user,
            space_name=query.space_name,
            subpath=query.subpath,
            resource_type=core.ResourceType.history,
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
                    resource_type=core.ResourceType.history,
                    shortname=query.filter_shortnames[0],
                    subpath=query.subpath,
                    attributes=action_obj,
                ),
            )

    return total, records


async def serve_query_events(query, logged_in_user):
    records = []
    total = 0

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
            from utils.access_control import access_control
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

    return total, records


async def serve_query_aggregation(db, query, user_shortname):
    records = []
    total = 0

    redis_query_policies = await get_user_query_policies(
        db, user_shortname, query.space_name, query.subpath
    )
    rows = await redis_query_aggregate(
        query=query, redis_query_policies=redis_query_policies
    )
    total = len(rows)
    for idx, row in enumerate(rows):
        record = core.Record(
            resource_type=core.ResourceType.content,
            shortname=str(idx + 1),
            subpath=query.subpath,
            attributes=row["extra_attributes"]
        )
        records.append(record)

    return total, records

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

async def generate_payload_string(
        db,
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
