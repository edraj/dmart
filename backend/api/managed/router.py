from copy import copy
import csv
from datetime import datetime
import hashlib
import os
from re import sub as res_sub
from time import time
from fastapi import APIRouter, Body, Depends, Query, UploadFile, Path, Form, status
from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse

from database.create_tables import Spaces
from utils.bootstrap import bootstrap_all, load_permissions_and_roles
from utils.generate_email import generate_email_from_template, generate_subject
from utils.custom_validations import (
    validate_csv_with_schema,
    validate_jsonl_with_schema,
)
from utils.internal_error_code import InternalErrorCode
from utils.ticket_sys_utils import (
    set_ticket_init_state,
    transite,
    post_transite,
    check_open_state,
)
import models.api as api
import models.core as core
from models.enums import (
    ContentType,
    RequestType,
    ResourceType,
    LockAction,
    DataAssetType,
    TaskType, QueryType,
)
import utils.regex as regex
import sys
import json
from utils.jwt import JWTBearer, GetJWTToken, remove_redis_active_session
from utils.access_control import access_control
from utils.operational_repository import operational_repo
from utils.data_database import data_adapter as db
from typing import Any
from utils.helpers import (
    branch_path,
    camel_case,
    csv_file_to_json,
    flatten_dict,
    resolve_schema_references,
)
from utils.custom_validations import validate_payload_with_schema
from utils.settings import settings
from utils.plugin_manager import plugin_manager
from io import BytesIO, StringIO
from api.user.service import (
    send_email,
    send_sms,
)
from fastapi.responses import RedirectResponse
from languages.loader import languages
from typing import Callable
import duckdb

from pathlib import Path as FilePath

router = APIRouter()


@router.post(
    "/csv/{space_name}",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def generate_csv_from_report_saved_query(
    space_name: str, record: core.Record, user_shortname=Depends(JWTBearer())
):
    records = (
        await execute(
            space_name=space_name,
            record=record,
            task_type=TaskType.query,
            logged_in_user=user_shortname,
        )
    ).records
    if not records:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media",
                code=InternalErrorCode.OBJECT_NOT_FOUND,
                message="Request object is not available",
            ),
        )

    json_data = []
    for r in records:
        if r.attributes is None:
            continue
        json_data.append(flatten_dict(r.attributes))

    v_path = StringIO()
    if len(json_data) == 0:
        return api.Response(
            status=api.Status.success,
            records=records,
            attributes={"message": "The records are empty"},
        )

    keys: set = set({})
    for row in json_data:
        keys.update(set(row.keys()))

    writer = csv.DictWriter(v_path, fieldnames=list(keys))
    writer.writeheader()
    writer.writerows(json_data)

    response = StreamingResponse(iter([v_path.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = (
        f"attachment; filename={space_name}_{record.subpath}.csv"
    )

    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
            branch_name=record.branch_name,
            subpath=record.subpath,
            action_type=core.ActionType.query,
            user_shortname=user_shortname,
            attributes={
                "shortname": record.shortname,
                "number_of_records": len(json_data),
            },
        )
    )

    return response


@router.post("/csv", response_model=api.Response, response_model_exclude_none=True)
async def csv_entries(query: api.Query, user_shortname=Depends(JWTBearer())):
    subpath_parts = query.subpath.split("/")
    subpath = "/"
    shortname = query.subpath
    if len(subpath_parts) > 1:
        subpath = "/".join(subpath_parts[:-1])
        shortname = subpath_parts[-1]
    folder_dto = core.EntityDTO(
        space_name=query.space_name,
        subpath=subpath,
        shortname=shortname,
        resource_type=ResourceType.folder,
        user_shortname=user_shortname,
    )

    await plugin_manager.before_action(
        folder_dto.to_event_data(
            core.ActionType.query, {"filter_shortnames": query.filter_shortnames}
        )
    )

    # redis_query_policies = await access_control.get_user_query_policies(
    #     user_shortname, query.space_name, query.subpath
    # )

    # folder: core.Meta = await db.load(folder_dto)
    folder_payload: dict[str, Any] = await db.load_resource_payload(folder_dto)

    folder_views = folder_payload.get("csv_columns", [])
    if not folder_views:
        folder_views = folder_payload.get("index_attributes", [])

    keys: list = [i["name"] for i in folder_views]
    keys_existence = dict(zip(keys, [False for _ in range(len(keys))]))
    search_res: tuple[int, list[dict[str, Any]]] = await operational_repo.search(
        query, user_shortname
    )
    json_data = []
    timestamp_fields = ["created_at", "updated_at"]
    new_keys: set = set()
    deprecated_keys: set = set()
    for redis_doc_dict in search_res[1]:
        if redis_doc_dict.get("payload_doc_id") and query.retrieve_json_payload:
            payload_doc_content = await operational_repo.find_payload_data_by_id(
                redis_doc_dict["payload_doc_id"], redis_doc_dict["resource_type"]
            )
            redis_doc_dict.update(payload_doc_content)

        rows: list[dict] = [{}]
        flattened_doc = flatten_dict(redis_doc_dict)
        for folder_view in folder_views:
            column_key = folder_view.get("key")
            column_title = folder_view.get("name")
            attribute_val = flattened_doc.get(column_key)
            if attribute_val:
                keys_existence[column_title] = True
            """
            Extract array items in a separate row per item
            - list_new_rows = []
            - for row in rows:
            -      for item in new_list[1:]:
            -          new_row = row
            -          add item attributes to the new_row
            -          list_new_rows.append(new_row)
            -      add new_list[0] attributes to row
            -    
            -  rows += list_new_rows
            """
            if isinstance(attribute_val, list) and len(attribute_val) > 0:
                list_new_rows: list[dict] = []
                # Duplicate old rows
                for row in rows:
                    # New row for each item
                    for item in attribute_val[1:]:
                        new_row = copy(row)
                        # New cell for each item's attribute
                        if isinstance(item, dict):
                            for k, v in item.items():
                                new_row[f"{column_title}.{k}"] = v
                                new_keys.add(f"{column_title}.{k}")
                        else:
                            new_row[column_title] = item

                        list_new_rows.append(new_row)
                    # Add first items's attribute to the existing rows
                    if isinstance(attribute_val[0], dict):
                        deprecated_keys.add(column_title)
                        for k, v in attribute_val[0].items():
                            row[f"{column_title}.{k}"] = v
                            new_keys.add(f"{column_title}.{k}")
                    else:
                        row[column_title] = attribute_val[0]
                rows += list_new_rows

            elif attribute_val and not isinstance(attribute_val, list):
                new_col = (
                    attribute_val
                    if column_key not in timestamp_fields
                    else datetime.fromtimestamp(attribute_val).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )
                for row in rows:
                    row[column_title] = new_col
        json_data += rows

    # Sort all entries from all schemas
    if query.sort_by in core.Meta.model_fields and len(query.filter_schema_names) > 1:
        json_data = sorted(
            json_data,
            key=lambda d: d[query.sort_by] if query.sort_by in d else "",
            reverse=(query.sort_type == api.SortType.descending),
        )

    await plugin_manager.after_action(
        folder_dto.to_event_data(core.ActionType.query)
    )

    if len(json_data) == 0:
        return api.Response(
            status=api.Status.success,
            attributes={"message": "The records are empty"},
        )

    keys = [key for key in keys if keys_existence[key]]
    v_path = StringIO()

    list_deprecated_keys = list(deprecated_keys)
    keys = list(filter(lambda item: item not in list_deprecated_keys, keys))
    writer = csv.DictWriter(v_path, fieldnames=(keys + list(new_keys)))
    writer.writeheader()
    writer.writerows(json_data)

    response = StreamingResponse(iter([v_path.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = (
        f"attachment; filename={query.space_name}_{query.subpath}.csv"
    )

    return response


@router.post("/space", response_model=api.Response, response_model_exclude_none=True)
async def serve_space(
    request: api.Request, owner_shortname=Depends(JWTBearer())
) -> api.Response:
    if settings.active_data_db == "file":
        spaces = await operational_repo.find_by_id("spaces")
        if request.space_name not in spaces:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message="Space name provided is empty or invalid [3]",
                ),
            )

    else:
        spaces = await db.query(api.Query(type=QueryType.spaces, space_name="management", subpath="/"))
        if request.space_name not in [space.shortname for space in spaces]:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message="Space name provided is empty or invalid [3]",
                ),
            )

    record = request.records[0]
    history_diff: dict[str, Any] = {}
    match request.request_type:
        case api.RequestType.create:
            if request.space_name in [space.shortname for space in spaces]:
                raise api.Exception(
                    status.HTTP_400_BAD_REQUEST,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.ALREADY_EXIST_SPACE_NAME,
                        message="Space name provided already existed [1]",
                    ),
                )

            dto = core.EntityDTO.from_record(
                record, request.space_name, owner_shortname
            )

            if not await access_control.check_access(
                dto=dto,
                action_type=core.ActionType.create,
                record_attributes=record.attributes,
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.NOT_ALLOWED,
                        message="You don't have permission to this action [1]",
                    ),
                )

            resource_obj = core.Space.from_record(
                record=record, owner_shortname=owner_shortname
            )

            resource_obj.is_active = True
            resource_obj.indexing_enabled = True
            resource_obj.shortname = request.space_name
            resource_obj.active_plugins = [
                "action_log",
                "redis_db_update",
                "resource_folders_creation",
            ]
            await db.save(dto, resource_obj)

        case api.RequestType.update:
            dto = core.EntityDTO.from_record(
                record, request.space_name, owner_shortname
            )
            space = await operational_repo.find(dto)
            if (
                not space
                or request.space_name not in spaces
                or request.space_name != record.shortname
            ):
                raise api.Exception(
                    status.HTTP_400_BAD_REQUEST,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.INVALID_SPACE_NAME,
                        message="Space name provided is empty or invalid [6]",
                    ),
                )

            if not await access_control.check_access(
                dto=dto,
                action_type=core.ActionType.update,
                meta=space,
                record_attributes=record.attributes,
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.NOT_ALLOWED,
                        message="You don't have permission to this action [2]",
                    ),
                )

            if not await operational_repo.validate_and_release_lock(dto):
                raise api.Exception(
                    status_code=status.HTTP_403_FORBIDDEN,
                    error=api.Error(
                        type="update",
                        code=InternalErrorCode.LOCKED_ENTRY,
                        message="This entry is locked",
                    ),
                )

            await plugin_manager.before_action(
                dto.to_event_data(core.ActionType.update)
            )

            await db.update(dto, space)

        case api.RequestType.delete:
            if request.space_name == settings.management_space:
                raise api.Exception(
                    status.HTTP_400_BAD_REQUEST,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.CANNT_DELETE,
                        message="Cannot delete management space",
                    ),
                )
            if request.space_name not in spaces:
                raise api.Exception(
                    status.HTTP_400_BAD_REQUEST,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.INVALID_SPACE_NAME,
                        message="Space name provided is empty or invalid [2]",
                    ),
                )

            dto = core.EntityDTO.from_record(
                record, request.space_name, owner_shortname
            )
            space = await operational_repo.find(dto)
            if not await access_control.check_access(
                dto=dto,
                meta=space,
                action_type=core.ActionType.delete,
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.NOT_ALLOWED,
                        message="You don't have permission to this action [3]",
                    ),
                )

            os.system(f"rm -r {settings.spaces_folder}/{request.space_name}")

            indexes = await operational_repo.list_indexes()
            for index in indexes:
                if index.startswith(f"{request.space_name}:"):
                    await operational_repo.drop_index(index, True)

        case _:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.UNMATCHED_DATA,
                    message="mismatch with the information provided",
                ),
            )

    await bootstrap_all()

    await plugin_manager.after_action(
        core.Event(
            space_name=record.shortname,
            branch_name=record.branch_name,
            subpath=record.subpath,
            shortname=record.shortname,
            action_type=core.ActionType(request.request_type),
            resource_type=ResourceType.space,
            user_shortname=owner_shortname,
            attributes={"history_diff": history_diff},
        )
    )

    return api.Response(status=api.Status.success)


@router.post("/query", response_model=api.Response, response_model_exclude_none=True)
async def query_entries(
    query: api.Query, user_shortname=Depends(JWTBearer())
) -> api.Response:
    await plugin_manager.before_action(
        core.Event(
            space_name=query.space_name,
            branch_name=query.branch_name,
            subpath=query.subpath,
            action_type=core.ActionType.query,
            user_shortname=user_shortname,
            attributes={"filter_shortnames": query.filter_shortnames},
        )
    )
    if settings.active_data_db == "file":
        total, records = await operational_repo.query_handler(query, user_shortname)
    else:
        records = await db.query(query)
        total = len(records)

    await plugin_manager.after_action(
        core.Event(
            space_name=query.space_name,
            branch_name=query.branch_name,
            subpath=query.subpath,
            action_type=core.ActionType.query,
            user_shortname=user_shortname,
        )
    )
    return api.Response(
        status=api.Status.success,
        records=records,
        attributes={"total": total, "returned": len(records)},
    )


@router.post("/request", response_model=api.Response, response_model_exclude_none=True)
async def serve_request(
    request: api.Request,
    token=Depends(GetJWTToken()),
    owner_shortname=Depends(JWTBearer()),
    is_internal: bool = False,
) -> api.Response:
    if settings.active_data_db == "file":
        spaces = await operational_repo.find_by_id("spaces")
        if request.space_name not in spaces:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message="Space name provided is empty or invalid [3]",
                ),
            )

    else:
        spaces = await db.query(api.Query(type=QueryType.spaces, space_name="management", subpath="/"))
        if request.space_name not in [space.shortname for space in spaces]:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message="Space name provided is empty or invalid [3]",
                ),
            )

    records = []
    failed_records = []

    for record in request.records:
        meta: core.Meta | None = None
        dto: core.EntityDTO = core.EntityDTO.from_record(
            record, request.space_name, owner_shortname
        )

        if request.request_type != RequestType.create:
            meta = await db.load_or_none(dto) # type: ignore

        if not await access_control.check_access(
            dto=dto,
            meta=meta,
            action_type=request.action_type,
            record_attributes=record.attributes,
        ):
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(
                    type="request",
                    code=InternalErrorCode.NOT_ALLOWED,
                    message="You don't have permission to this action [1]",
                ),
            )
        await plugin_manager.before_action(
            dto.to_event_data(request.action_type, record.attributes)
        )
        try:
            match request.request_type:
                case api.RequestType.create:
                    if (
                        db.is_entry_exist(dto)
                        and record.shortname != settings.auto_uuid_rule
                    ):
                        raise api.Exception(
                            status.HTTP_400_BAD_REQUEST,
                            api.Error(
                                type="request",
                                code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
                                message=f"This shortname {record.shortname} already exists",
                            ),
                        )

                    await operational_repo.validate_uniqueness(
                        dto, record.attributes
                    )

                    meta = dto.class_type.from_record(
                        record=record, owner_shortname=owner_shortname
                    )
                    if not isinstance(meta, core.Meta):
                        continue
                    if record.shortname != settings.auto_uuid_rule:
                        dto.shortname = meta.shortname

                    if meta and isinstance(meta, core.Ticket):
                        meta = await set_ticket_init_state(dto, meta)

                    if not is_internal or "created_at" not in record.attributes:
                        meta.created_at = datetime.now()
                        meta.updated_at = datetime.now()

                    separate_payload_data: dict[str, Any] = {}
                    if (
                        meta.payload
                        and meta.payload.content_type == ContentType.json
                        and isinstance(meta.payload.body, dict)
                    ):
                        separate_payload_data = meta.payload.body
                        meta.payload.body = dto.shortname + ".json"

                    if (
                        meta.payload
                        and meta.payload.content_type == ContentType.json
                        and meta.payload.schema_shortname
                        and isinstance(separate_payload_data, dict)
                    ):
                        await validate_payload_with_schema(
                            payload_data=separate_payload_data,
                            space_name=request.space_name,
                            branch_name=record.branch_name,
                            schema_shortname=meta.payload.schema_shortname,
                        )

                    await db.save(dto, meta, separate_payload_data)

                    if isinstance(meta, core.User):
                        # SMS Invitation
                        if not meta.is_msisdn_verified and meta.msisdn:
                            inv_link = (
                                await operational_repo.store_user_invitation_token(
                                    meta, "SMS"
                                )
                            )
                            if inv_link:
                                await send_sms(
                                    msisdn=record.attributes.get("msisdn", ""),
                                    message=languages[meta.language][
                                        "invitation_message"
                                    ].replace(
                                        "{link}",
                                        await operational_repo.url_shortener(inv_link),
                                    ),
                                )
                        # EMAIL Invitation
                        if not meta.is_email_verified and meta.email:
                            inv_link = (
                                await operational_repo.store_user_invitation_token(
                                    meta, "EMAIL"
                                )
                            )
                            if inv_link:
                                await send_email(
                                    from_address=settings.email_sender,
                                    to_address=meta.email,
                                    message=generate_email_from_template(
                                        "activation",
                                        {
                                            "link": await operational_repo.url_shortener(
                                                inv_link
                                            ),
                                            "name": record.attributes.get(
                                                "displayname", {}
                                            ).get("en", ""),
                                            "shortname": meta.shortname,
                                            "msisdn": meta.msisdn,
                                        },
                                    ),
                                    subject=generate_subject("activation"),
                                )

                case api.RequestType.update | api.RequestType.r_replace:
                    if not meta or await operational_repo.is_locked_by_other_user(dto):
                        raise api.Exception(
                            status_code=status.HTTP_404_NOT_FOUND,
                            error=api.Error(
                                type="db",
                                code=InternalErrorCode.OBJECT_NOT_FOUND,
                                message="Request object is not available or locked",
                            ),
                        )

                    # GET PAYLOAD DATA
                    resource_payload_body: dict[str, Any] = {}
                    if (
                        meta.payload
                        and meta.payload.content_type == ContentType.json
                        and isinstance(meta.payload.body, str)
                    ):
                        try:
                            resource_payload_body = await db.load_resource_payload(
                                dto
                            )
                        except api.Exception as e:
                            if request.request_type == api.RequestType.update:
                                raise e

                    # GENERATE NEW RESOURCE OBJECT
                    meta.updated_at = datetime.now()
                    updated_payload: dict | None = meta.update_from_record(
                        record=record,
                        old_body=resource_payload_body,
                        replace=request.request_type == api.RequestType.r_replace,
                    )

                    await operational_repo.validate_uniqueness(
                        dto, record.attributes, RequestType.update
                    )
                    # VALIDATE SEPARATE PAYLOAD BODY
                    if (
                        meta.payload
                        and meta.payload.content_type == ContentType.json
                        and meta.payload.schema_shortname
                        and updated_payload is not None
                    ):
                        await validate_payload_with_schema(
                            payload_data=updated_payload,
                            space_name=request.space_name,
                            branch_name=record.branch_name or settings.default_branch,
                            schema_shortname=meta.payload.schema_shortname,
                        )

                    history_diff = await db.update(dto, meta, updated_payload)
                    
                    await operational_repo.delete_lock_doc(dto)

                    if (
                        isinstance(meta, core.User)
                        and record.attributes.get("is_active") is False
                    ):
                        await remove_redis_active_session(record.shortname)

                    record.attributes["history_diff"] = history_diff

                case api.RequestType.assign:
                    if not meta or await operational_repo.is_locked_by_other_user(dto):
                        raise api.Exception(
                            status_code=status.HTTP_404_NOT_FOUND,
                            error=api.Error(
                                type="db",
                                code=InternalErrorCode.OBJECT_NOT_FOUND,
                                message="Request object is not available or locked",
                            ),
                        )
                    if not record.attributes.get("owner_shortname"):
                        raise api.Exception(
                            status.HTTP_400_BAD_REQUEST,
                            api.Error(
                                type="request",
                                code=InternalErrorCode.MISSING_DATA,
                                message="The owner_shortname is required",
                            ),
                        )
                    _target_user: core.User = await db.load(
                        core.EntityDTO(
                            space_name=settings.management_space,
                            subpath=settings.users_subpath,
                            shortname=record.attributes["owner_shortname"],
                            resource_type=ResourceType.user,
                            branch_name=record.branch_name,
                        )
                    )
                    meta.updated_at = datetime.now()
                    meta.owner_shortname = record.attributes["owner_shortname"]
                    history_diff = await db.update(dto, meta)
                    await operational_repo.delete_lock_doc(dto)
                    record.attributes["history_diff"] = history_diff

                case api.RequestType.update_acl:
                    if not meta or await operational_repo.is_locked_by_other_user(dto):
                        raise api.Exception(
                            status_code=status.HTTP_404_NOT_FOUND,
                            error=api.Error(
                                type="db",
                                code=InternalErrorCode.OBJECT_NOT_FOUND,
                                message="Request object is not available or locked",
                            ),
                        )
                    if record.attributes.get("acl", None) is None:
                        raise api.Exception(
                            status.HTTP_400_BAD_REQUEST,
                            api.Error(
                                type="request",
                                code=InternalErrorCode.MISSING_DATA,
                                message="The acl is required",
                            ),
                        )

                    meta.updated_at = datetime.now()
                    meta.acl = record.attributes["acl"]

                    history_diff = await db.update(dto, meta)
                    
                    await operational_repo.delete_lock_doc(dto)

                    record.attributes["history_diff"] = history_diff

                case api.RequestType.delete:
                    #TODO - Check if the object is locked by another user
                    # if not meta or await operational_repo.is_locked_by_other_user(dto):
                    #     raise api.Exception(
                    #         status_code=status.HTTP_404_NOT_FOUND,
                    #         error=api.Error(
                    #             type="db",
                    #             code=InternalErrorCode.OBJECT_NOT_FOUND,
                    #             message="Request object is not available or locked",
                    #         ),
                    #     )
                    await db.delete(dto)

                    record.attributes["entry"] = meta

                case api.RequestType.move:
                    if (
                        not record.attributes.get("src_subpath")
                        or not record.attributes.get("src_shortname")
                        or not record.attributes.get("dest_subpath")
                        or not record.attributes.get("dest_shortname")
                    ):
                        raise api.Exception(
                            status.HTTP_400_BAD_REQUEST,
                            api.Error(
                                type="move",
                                code=InternalErrorCode.PROVID_SOURCE_PATH,
                                message="Please provide a source and destination path and a src shortname",
                            ),
                        )

                    if not meta or await operational_repo.is_locked_by_other_user(dto):
                        raise api.Exception(
                            status_code=status.HTTP_404_NOT_FOUND,
                            error=api.Error(
                                type="db",
                                code=InternalErrorCode.OBJECT_NOT_FOUND,
                                message="Request object is not available or locked",
                            ),
                        )

                    dest_dto = core.EntityDTO(
                        space_name=request.space_name,
                        subpath=record.attributes.get("dest_subpath", record.subpath),
                        shortname=record.attributes.get(
                            "dest_shortname", record.shortname
                        ),
                        resource_type=record.resource_type,
                        user_shortname=owner_shortname,
                    )

                    if not await access_control.check_access(
                        dto=dest_dto,
                        action_type=core.ActionType.create,
                    ):
                        raise api.Exception(
                            status.HTTP_401_UNAUTHORIZED,
                            api.Error(
                                type="request",
                                code=InternalErrorCode.NOT_ALLOWED,
                                message="You don't have permission to this action [6]",
                            ),
                        )

                    await db.move(
                        dto=dto,
                        meta=meta,
                        dest_subpath=record.attributes["dest_subpath"],
                        dest_shortname=record.attributes["dest_shortname"],
                    )
                    record.attributes["entry"] = meta

            if meta:
                records.append(
                    meta.to_record(
                        record.subpath, meta.shortname, [], record.branch_name
                    )
                )

            await plugin_manager.after_action(
                dto.to_event_data(request.action_type, record.attributes)
            )
        except api.Exception as e:
            failed_records.append(
                {
                    "record": record,
                    "error": e.error.message,
                    "error_code": e.error.code,
                }
            )

    if len(failed_records) == 0:
        return api.Response(status=api.Status.success, records=records)
    else:
        raise api.Exception(
            status_code=400,
            error=api.Error(
                type="request",
                code=InternalErrorCode.SOMETHING_WRONG,
                message="Something went wrong",
                info=[{"successfull": records, "failed": failed_records}],
            ),
        )


@router.put(
    "/progress-ticket/{space_name}/{subpath:path}/{shortname}/{action}",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def update_state(
    logged_in_user=Depends(JWTBearer()),
    space_name: str = Path(..., pattern=regex.SPACENAME, examples=["data"]),
    subpath: str = Path(..., pattern=regex.SUBPATH, examples=["/content"]),
    shortname: str = Path(..., pattern=regex.SHORTNAME, examples=["unique_shortname"]),
    action: str = Path(..., examples=["approve"]),
    resolution: str | None = Body(
        None, embed=True, examples=["Ticket state resolution"]
    ),
    comment: str | None = Body(None, embed=True, examples=["Nice ticket"]),
    branch_name: str | None = settings.default_branch,
) -> api.Response:
    if settings.active_data_db == "file":
        spaces = await operational_repo.find_by_id("spaces")
        if space_name not in spaces:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message="Space name provided is empty or invalid [3]",
                ),
            )

    else:
        spaces = await db.query(api.Query(type=QueryType.spaces, space_name="management", subpath="/"))
        if space_name not in [space.shortname for space in spaces]:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message="Space name provided is empty or invalid [3]",
                ),
            )

    user_roles: list[str] = list(
        (await access_control.get_user_roles(logged_in_user)).keys()
    )

    dto: core.EntityDTO = core.EntityDTO(
        space_name=space_name,
        subpath=subpath,
        shortname=shortname,
        resource_type=ResourceType.ticket,
        user_shortname=logged_in_user,
    )

    ticket_obj: core.Ticket = await db.load(dto)

    await plugin_manager.before_action(
        dto.to_event_data(core.ActionType.progress_ticket)
    )

    if(
        ticket_obj.payload is None 
        or ticket_obj.payload.body is None 
        or await operational_repo.is_locked_by_other_user(dto)
    ):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media",
                code=InternalErrorCode.OBJECT_NOT_FOUND,
                message="Request object is not available or locked",
            ),
        )

    if not await access_control.check_access(
        dto=dto,
        meta=ticket_obj,
        action_type=core.ActionType.update,
        record_attributes={"state": "", "resolution_reason": ""},
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [8]",
            ),
        )
    if ticket_obj.payload.content_type == ContentType.json:
        workflow_dto = core.EntityDTO(
            space_name=space_name,
            subpath="workflows",
            shortname=ticket_obj.workflow_shortname,
            resource_type=ResourceType.content,
            user_shortname=logged_in_user,
        )
        workflows_data: core.Content = await db.load(workflow_dto)

        if (
            workflows_data.payload is not None
            and workflows_data.payload.body is not None
        ):
            workflows_payload = await db.load_resource_payload(workflow_dto)
            if not ticket_obj.is_open:
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="transition",
                        code=InternalErrorCode.TICKET_ALREADY_CLOSED,
                        message="Ticket is already in closed",
                    ),
                )
            response = transite(
                workflows_payload["states"], action, user_roles, ticket_obj.state
            )

            if not response["status"]:
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="transition",
                        code=InternalErrorCode.INVALID_TICKET_STATUS,
                        message=response["message"],
                    ),
                )

            ticket_obj.state = response["message"]
            ticket_obj.is_open = check_open_state(
                workflows_payload["states"], response["message"]
            )

            if resolution:
                post_response = post_transite(
                    workflows_payload["states"], response["message"], resolution
                )
                if not post_response["status"]:
                    raise api.Exception(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=api.Error(
                            type="transition",
                            code=InternalErrorCode.INVALID_TICKET_STATUS,
                            message=post_response["message"],
                        ),
                    )
                ticket_obj.resolution_reason = resolution

            if comment:
                time = datetime.now().strftime("%Y%m%d%H%M%S")
                payload = {
                    "content_type": "comment",
                    "body": comment,
                    "state": ticket_obj.state,
                }
                record_file = json.dumps(
                    {
                        "shortname": f"c_{time}",
                        "resource_type": "comment",
                        "subpath": f"{subpath}/{shortname}",
                        "attributes": {"is_active": True, **payload},
                    }
                ).encode()
                payload_file = json.dumps(payload).encode()
                await create_or_update_resource_with_payload(
                    UploadFile(
                        filename=f"{time}.json",
                        file=BytesIO(payload_file),
                    ),
                    UploadFile(
                        filename="record.json",
                        file=BytesIO(record_file),
                    ),
                    space_name,
                    owner_shortname=logged_in_user,
                )

            history_diff = await db.update(dto, ticket_obj)
            await operational_repo.delete_lock_doc(dto)
            await plugin_manager.after_action(
                dto.to_event_data(
                    core.ActionType.progress_ticket,
                    {
                        "history_diff": history_diff,
                        "state": ticket_obj.state,
                    },
                )
            )
            return api.Response(status=api.Status.success)

    raise api.Exception(
        status.HTTP_400_BAD_REQUEST,
        error=api.Error(
            type="ticket",
            code=InternalErrorCode.WORKFLOW_BODY_NOT_FOUND,
            message="Workflow body not found",
        ),
    )


@router.get(
    "/payload/{resource_type}/{space_name}/{subpath:path}/{shortname}.{ext}",
    response_model_exclude_none=True,
)
@router.get(
    "/payload/{resource_type}/{space_name}/{subpath:path}/{shortname}.{schema_shortname}.{ext}",
    response_model_exclude_none=True,
)
async def retrieve_entry_or_attachment_payload(
    resource_type: ResourceType,
    space_name: str = Path(..., pattern=regex.SPACENAME, examples=["data"]),
    subpath: str = Path(..., pattern=regex.SUBPATH, examples=["/content"]),
    shortname: str = Path(..., pattern=regex.SHORTNAME, examples=["unique_shortname"]),
    schema_shortname: str | None = None,
    ext: str = Path(..., pattern=regex.EXT, examples=["png"]),
    logged_in_user=Depends(JWTBearer()),
    branch_name: str | None = settings.default_branch,
) -> FileResponse:

    dto: core.EntityDTO = core.EntityDTO(
        space_name=space_name,
        subpath=subpath,
        shortname=shortname,
        resource_type=resource_type,
        schema_shortname=schema_shortname,
        user_shortname=logged_in_user,
    )

    meta: core.Meta = await db.load(dto)
    print(f"{meta=}")
    await plugin_manager.before_action(dto.to_event_data(core.ActionType.view))
    print("###", meta.payload.body, f"{shortname}.{ext}")
    if (
        meta.payload is None
        or meta.payload.body is None
        or meta.payload.body != f"{shortname}.{ext}"
    ):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media",
                code=InternalErrorCode.OBJECT_NOT_FOUND,
                message="Request object is not available",
            ),
        )

    if not await access_control.check_access(
        dto=dto,
        meta=meta,
        action_type=core.ActionType.view,
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [9]",
            ),
        )

    payload_path = db.payload_path(dto=dto)
    await plugin_manager.after_action(dto.to_event_data(core.ActionType.view))
    print("@@@", payload_path / str(meta.payload.body))
    return FileResponse(payload_path / str(meta.payload.body))


@router.post(
    "/resource_with_payload",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def create_or_update_resource_with_payload(
    payload_file: UploadFile,
    request_record: UploadFile,
    space_name: str = Form(..., examples=["data"]),
    sha: str | None = Form(None, examples=["data"]),
    owner_shortname: str = Depends(JWTBearer()),
):
    # NOTE We currently make no distinction between create and update.
    # in such case update should contain all the data every time.
    if settings.active_data_db == "file":
        spaces = await operational_repo.find_by_id("spaces")
        if space_name not in spaces:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message="Space name provided is empty or invalid [3]",
                ),
            )

    else:
        spaces = await db.query(api.Query(type=QueryType.spaces, space_name="management", subpath="/"))
        if space_name not in [space.shortname for space in spaces]:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message="Space name provided is empty or invalid [3]",
                ),
            )
    record = core.Record.model_validate_json(request_record.file.read())

    dto = core.EntityDTO.from_record(record, space_name, owner_shortname)

    payload_filename = payload_file.filename or ""
    if payload_filename.endswith(".json"):
        resource_content_type = ContentType.json
    elif payload_file.content_type == "application/pdf":
        resource_content_type = ContentType.pdf
    elif payload_file.content_type == "text/csv":
        resource_content_type = ContentType.csv
    elif payload_file.content_type == "application/octet-stream":
        if record.attributes.get("content_type") == "jsonl":
            resource_content_type = ContentType.jsonl
        elif record.attributes.get("content_type") == "sqlite":
            resource_content_type = ContentType.sqlite
        elif record.attributes.get("content_type") == "parquet":
            resource_content_type = ContentType.parquet
        else:
            resource_content_type = ContentType.text
    elif payload_file.content_type == "text/markdown":
        resource_content_type = ContentType.markdown
    elif payload_file.content_type and "image/" in payload_file.content_type:
        resource_content_type = ContentType.image
    elif payload_file.content_type and "audio/" in payload_file.content_type:
        resource_content_type = ContentType.audio
    elif payload_file.content_type and "video/" in payload_file.content_type:
        resource_content_type = ContentType.video
    else:
        raise api.Exception(
            status.HTTP_406_NOT_ACCEPTABLE,
            api.Error(
                type="attachment",
                code=InternalErrorCode.NOT_SUPPORTED_TYPE,
                message="The file type is not supported",
            ),
        )

    await plugin_manager.before_action(dto.to_event_data(core.ActionType.create))

    if not await access_control.check_access(
        dto=dto,
        action_type=core.ActionType.create,
        record_attributes=record.attributes,
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [10]",
            ),
        )

    sha1 = hashlib.sha1()
    sha1.update(payload_file.file.read())
    checksum = sha1.hexdigest()
    if isinstance(sha, str) and sha != checksum:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.INVALID_DATA,
                message="The provided file doesn't match the sha",
            ),
        )
    await payload_file.seek(0)
    if dto.resource_type == ResourceType.ticket:
        record.attributes["state"] = "TEMP"
    resource_obj: core.Meta = dto.class_type.from_record(
        record=record, owner_shortname=owner_shortname
    )
    
    if record.shortname != settings.auto_uuid_rule:
        dto.shortname = resource_obj.shortname

    if isinstance(resource_obj, core.Ticket):
        resource_obj = await set_ticket_init_state(dto, resource_obj)
    resource_obj.payload = core.Payload(
        content_type=resource_content_type,
        checksum=checksum,
        client_checksum=sha if isinstance(sha, str) else None,
        schema_shortname=(
            "meta_schema"
            if record.resource_type == ResourceType.schema
            else record.attributes.get("payload", {}).get("schema_shortname", None)
        ),
        body=f"{record.shortname}." + payload_filename.split(".")[1],
    )
    if (
        not isinstance(resource_obj, core.Attachment)
        and not isinstance(resource_obj, core.Content)
        and not isinstance(resource_obj, core.Ticket)
        and not isinstance(resource_obj, core.Schema)
    ):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="attachment",
                code=InternalErrorCode.SOME_SUPPORTED_TYPE,
                message="Only resources of type 'attachment', 'content', 'ticket', or 'schema' are allowed",
            ),
        )

    resource_obj.payload.body = (
        f"{resource_obj.shortname}." + payload_filename.split(".")[1]
    )

    if (
        resource_content_type == ContentType.json
        and resource_obj.payload.schema_shortname
    ):
        await validate_payload_with_schema(
            payload_data=payload_file,
            space_name=space_name,
            branch_name=record.branch_name or settings.default_branch,
            schema_shortname=resource_obj.payload.schema_shortname,
        )

    await db.save(dto, resource_obj)
    await db.save_payload(dto, resource_obj, payload_file)

    await plugin_manager.after_action(dto.to_event_data(core.ActionType.create))

    return api.Response(
        status=api.Status.success,
        records=[record],
    )


@router.post(
    "/resources_from_csv/{resource_type}/{space_name}/{subpath:path}/{schema_shortname}",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def import_resources_from_csv(
    resources_file: UploadFile,
    resource_type: ResourceType,
    space_name: str = Path(..., pattern=regex.SPACENAME, examples=["data"]),
    subpath: str = Path(..., pattern=regex.SUBPATH, examples=["/content"]),
    schema_shortname: str = Path(
        ..., pattern=regex.SHORTNAME, examples=["model_schema"]
    ),
    owner_shortname=Depends(JWTBearer()),
    branch_name: str | None = settings.default_branch,
):
    contents = await resources_file.read()
    decoded = contents.decode()
    buffer = StringIO(decoded)
    csv_reader = csv.DictReader(buffer)

    schema_dto = core.EntityDTO(
        space_name=space_name,
        subpath="schema",
        resource_type=ResourceType.schema,
        shortname=schema_shortname,
        user_shortname=owner_shortname,
    )
    schema_path: FilePath = db.payload_path(schema_dto) / f"{schema_shortname}.json"
    with open(schema_path) as schema_file:
        schema_content = json.load(schema_file)
    schema_content = resolve_schema_references(schema_content)

    data_types_mapper: dict[str, Callable] = {
        "integer": int,
        "number": float,
        "string": str,
        "boolean": str,
        "object": json.loads,
        "array": json.loads,
    }

    resource_cls = getattr(sys.modules["models.core"], camel_case(resource_type))
    meta_class_attributes = resource_cls.model_fields
    failed_shortnames: list = []
    success_count = 0
    for row in csv_reader:
        shortname: str = ""
        meta_object: dict = {}
        payload_object: dict = {}
        for key, value in row.items():
            if not key or not value:
                continue

            if key == "shortname":
                shortname = value
                continue

            keys_list = [i.strip() for i in key.split(".")]
            if keys_list[0] in meta_class_attributes:
                match len(keys_list):
                    case 1:
                        meta_object[keys_list[0].strip()] = value
                    case 2:
                        if keys_list[0].strip() not in meta_object:
                            meta_object[keys_list[0].strip()] = {}
                        meta_object[keys_list[0].strip()][keys_list[1].strip()] = value
                continue

            current_schema_property = schema_content
            for item in keys_list:
                if "oneOf" in current_schema_property:
                    for oneOf_item in current_schema_property["oneOf"]:
                        if (
                            "properties" in oneOf_item
                            and item.strip() in oneOf_item["properties"]
                        ):
                            current_schema_property = oneOf_item["properties"][
                                item.strip()
                            ]
                            break
                else:
                    current_schema_property = current_schema_property["properties"][
                        item.strip()
                    ]

            if current_schema_property["type"] in ["number", "integer"]:
                value = value.replace(",", "")

            value = data_types_mapper[current_schema_property["type"]](value)
            if current_schema_property["type"] == "array":
                value = [
                    str(item) if type(item) in [int, float] else item for item in value
                ]

            match len(keys_list):
                case 1:
                    payload_object[keys_list[0].strip()] = value
                case 2:
                    if keys_list[0].strip() not in payload_object:
                        payload_object[keys_list[0].strip()] = {}
                    payload_object[keys_list[0].strip()][keys_list[1].strip()] = value
                case 3:
                    if keys_list[0].strip() not in payload_object:
                        payload_object[keys_list[0].strip()] = {}
                    if keys_list[1].strip() not in payload_object[keys_list[0].strip()]:
                        payload_object[keys_list[0].strip()][keys_list[1].strip()] = {}
                    payload_object[keys_list[0].strip()][keys_list[1].strip()][
                        keys_list[2].strip()
                    ] = value
                case _:
                    continue

        if shortname:
            if "is_active" not in meta_object:
                meta_object["is_active"] = True
            attributes = meta_object

            attributes["payload"] = {
                "content_type": "json",
                "schema_shortname": schema_shortname,
                "body": payload_object,
            }
            record = core.Record(
                resource_type=resource_type,
                shortname=shortname,
                subpath=subpath,
                branch_name=branch_name,
                attributes=attributes,
            )
            try:
                await serve_request(
                    request=api.Request(
                        space_name=space_name,
                        request_type=RequestType.create,
                        records=[record],
                    ),
                    owner_shortname=owner_shortname,
                    is_internal=True,
                )
                success_count += 1
            except Exception:
                failed_shortnames.append(shortname)

    return api.Response(
        status=api.Status.success,
        attributes={
            "success_count": success_count,
            "failed_shortnames": failed_shortnames,
        },
    )


@router.get(
    "/entry/{resource_type}/{space_name}/{subpath:path}/{shortname}",
    response_model_exclude_none=True,
)
async def retrieve_entry_meta(
    resource_type: ResourceType,
    space_name: str = Path(..., pattern=regex.SPACENAME, examples=["data"]),
    subpath: str = Path(..., pattern=regex.SUBPATH, examples=["/content"]),
    shortname: str = Path(..., pattern=regex.SHORTNAME, examples=["unique_shortname"]),
    retrieve_json_payload: bool = False,
    retrieve_attachments: bool = False,
    filter_attachments_types: list = Query(
        default=[], examples=["media", "comment", "json"]
    ),
    validate_schema: bool = True,
    logged_in_user=Depends(JWTBearer()),
    branch_name: str | None = settings.default_branch,
) -> dict[str, Any]:
    dto = core.EntityDTO(
        space_name=space_name,
        subpath=subpath,
        resource_type=resource_type,
        shortname=shortname,
        user_shortname=logged_in_user,
    )
    if dto.subpath == settings.root_subpath_mw:
        dto.subpath = "/"

    await plugin_manager.before_action(dto.to_event_data(core.ActionType.view))

    meta: core.Meta = await db.load(dto)

    if not await access_control.check_access(
        dto=dto,
        meta=meta,
        action_type=core.ActionType.view,
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [11]",
            ),
        )

    attachments = {}
    entry_path = (
        settings.spaces_folder
        / f"{space_name}/{branch_path(branch_name)}/{subpath}/.dm/{shortname}"
    )
    if retrieve_attachments:
        attachments = await db.get_entry_attachments(
            subpath=subpath if settings.active_data_db == "file" else f"{subpath}/{shortname}",
            attachments_path=entry_path,
            branch_name=branch_name,
            retrieve_json_payload=retrieve_json_payload,
            filter_types=filter_attachments_types,
        )

    if (
        not retrieve_json_payload
        or not meta.payload
        or not meta.payload.body
        or not isinstance(meta.payload.body, str)
        or meta.payload.content_type != ContentType.json
    ):
        # TODO
        # include locked before returning the dictionary
        return {**meta.model_dump(exclude_none=True), "attachments": attachments}

    payload_body = await db.load_resource_payload(dto)

    if meta.payload and meta.payload.schema_shortname and validate_schema:
        await validate_payload_with_schema(
            payload_data=payload_body,
            space_name=space_name,
            branch_name=branch_name or settings.default_branch,
            schema_shortname=meta.payload.schema_shortname,
        )

    meta.payload.body = payload_body
    await plugin_manager.after_action(dto.to_event_data(core.ActionType.view))
    # TODO
    # include locked before returning the dictionary
    return {**meta.model_dump(exclude_none=True), "attachments": attachments}


@router.get("/byuuid/{uuid}", response_model_exclude_none=True)
async def get_entry_by_uuid(
    uuid: str,
    retrieve_json_payload: bool = False,
    retrieve_attachments: bool = False,
    logged_in_user=Depends(JWTBearer()),
):
    return await operational_repo.get_entry_by_var(
        "uuid",
        uuid,
        logged_in_user,
        retrieve_json_payload,
        retrieve_attachments,
    )


@router.get("/byslug/{slug}", response_model_exclude_none=True)
async def get_entry_by_slug(
    slug: str,
    retrieve_json_payload: bool = False,
    retrieve_attachments: bool = False,
    logged_in_user=Depends(JWTBearer()),
):
    return await operational_repo.get_entry_by_var(
        "slug",
        slug,
        logged_in_user,
        retrieve_json_payload,
        retrieve_attachments,
    )


# @router.post("/reload-redis-data", response_model_exclude_none=True)
# async def recreate_redis_indices(
#     for_space: str | None = None,
#     for_schemas: list | None = None,
#     for_subpaths: list | None = None,
#     logged_in_user=Depends(JWTBearer()),
# ):

# spaces = await operational_repo.find_by_id("spaces")
#     for space_name, space_json in spaces.items():
#         space_obj = core.Space.model_validate_json(space_json)
#         if space_obj.indexing_enabled and not await access_control.check_access(
#             user_shortname=logged_in_user,
#             space_name=space_name,
#             subpath="/",
#             resource_type=ResourceType.content,
#             action_type=core.ActionType.create,
#         ):
#             raise api.Exception(
#                 status.HTTP_401_UNAUTHORIZED,
#                 api.Error(
#                     type="request",
#                     code=InternalErrorCode.NOT_ALLOWED,
#                     message="You don't have permission to this action [12]",
#                 ),
#             )

# await operational_repo.create_application_indexes(
#     for_space,
#     for_schemas,
# )
#     loaded_data = await load_all_spaces_data_to_redis(for_space, for_subpaths)
#     await initialize_spaces()
#     await access_control.load_permissions_and_roles()

#     report = [
#         {"space_name": space_name, "index_data": index_data}
#         for space_name, index_data in loaded_data.items()
#     ]

#     return api.Response(status=api.Status.success, attributes={"report": report})


@router.get("/health/{health_type}/{space_name}", response_model_exclude_none=True)
async def get_space_report(
    space_name: str = Path(..., pattern=regex.SPACENAME, examples=["data"]),
    health_type: str = Path(..., examples=["soft", "hard"]),
    logged_in_user=Depends(JWTBearer()),
    branch_name: str | None = settings.default_branch,
):
    if logged_in_user != "dmart":
        raise api.Exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error=api.Error(
                type="access",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action",
            ),
        )

    if settings.active_data_db == "file":
        spaces = await operational_repo.find_by_id("spaces")
        if space_name not in spaces:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message="Space name provided is empty or invalid [3]",
                ),
            )
    else:
        spaces = await db.query(api.Query(type=QueryType.spaces, space_name="management", subpath="/"))
        if space_name not in [space.shortname for space in spaces]:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message="Space name provided is empty or invalid [3]",
                ),
            )

    if health_type not in ["soft", "hard"]:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media",
                code=InternalErrorCode.INVALID_HEALTH_CHECK,
                message="Invalid health check type",
            ),
        )

    os.system(f"./health_check.py -t {health_type} -b {branch_name} -s {space_name} &")
    return api.Response(
        status=api.Status.success,
    )


@router.put("/lock/{resource_type}/{space_name}/{subpath:path}/{shortname}")
async def lock_entry(
    space_name: str = Path(..., pattern=regex.SPACENAME),
    subpath: str = Path(..., pattern=regex.SUBPATH),
    shortname: str = Path(..., pattern=regex.SHORTNAME),
    branch_name: str | None = settings.default_branch,
    resource_type: ResourceType | None = ResourceType.ticket,
    logged_in_user=Depends(JWTBearer()),
):
    folder_meta_path = (
        settings.spaces_folder
        / space_name
        / branch_path(branch_name)
        / subpath
        / ".dm"
        / shortname
    )
    if not folder_meta_path.is_dir():
        raise api.Exception(
            status_code=status.HTTP_404_NOT_FOUND,
            error=api.Error(
                type="db",
                code=InternalErrorCode.DIR_NOT_FOUND,
                message="requested object is not found",
            ),
        )

    dto = core.EntityDTO(
        space_name=space_name,
        subpath=subpath,
        resource_type=resource_type,
        shortname=shortname,
        user_shortname=logged_in_user,
    )
    meta: core.Meta = await db.load(dto)

    await plugin_manager.before_action(dto.to_event_data(core.ActionType.lock))

    if resource_type == ResourceType.ticket and isinstance(meta, core.Ticket):
        meta.collaborators = meta.collaborators if meta.collaborators else {}
        if meta.collaborators.get("processed_by") != logged_in_user:
            meta.collaborators["processed_by"] = logged_in_user
            request = api.Request(
                space_name=space_name,
                request_type=api.RequestType.update,
                records=[
                    core.Record(
                        resource_type=resource_type,
                        subpath=subpath,
                        shortname=shortname,
                        attributes={
                            "is_active": True,
                            "collaborators": meta.collaborators,
                        },
                    )
                ],
            )
            await serve_request(request=request, owner_shortname=logged_in_user)

    # if lock file doesn't exist
    # elif lock file exit but lock_period expired
    # elif lock file exist and lock_period isn't expired but the owner want to extend the lock
    lock_type: LockAction | None = await operational_repo.save_lock_doc(
        dto,
        logged_in_user,
    )

    if lock_type is None:
        raise api.Exception(
            status_code=status.HTTP_403_FORBIDDEN,
            error=api.Error(
                type="lock",
                code=InternalErrorCode.LOCK_UNAVAILABLE,
                message="Lock does not exist or you have no access",
            ),
        )

    await plugin_manager.after_action(dto.to_event_data(core.ActionType.lock))

    return api.Response(
        status=api.Status.success,
        attributes={
            "message": f"Successfully locked the entry for {settings.lock_period} seconds",
            "lock_period": settings.lock_period,
        },
    )


@router.delete("/lock/{space_name}/{subpath:path}/{shortname}")
async def cancel_lock(
    space_name: str = Path(..., pattern=regex.SPACENAME),
    subpath: str = Path(..., pattern=regex.SUBPATH),
    shortname: str = Path(..., pattern=regex.SHORTNAME),
    branch_name: str | None = settings.default_branch,
    logged_in_user=Depends(JWTBearer()),
):
    dto = core.EntityDTO(
        space_name=space_name,
        branch_name=branch_name,
        subpath=subpath,
        shortname=shortname,
        user_shortname=logged_in_user,
    )
    lock_payload = await operational_repo.get_lock_doc(dto)

    if not lock_payload or lock_payload["owner_shortname"] != logged_in_user:
        raise api.Exception(
            status_code=status.HTTP_403_FORBIDDEN,
            error=api.Error(
                type="lock",
                code=InternalErrorCode.LOCK_UNAVAILABLE,
                message="Lock does not exist or you have no access",
            ),
        )

    await plugin_manager.before_action(dto.to_event_data(core.ActionType.unlock))

    await operational_repo.delete_lock_doc(dto)

    await plugin_manager.after_action(dto.to_event_data(core.ActionType.unlock))

    return api.Response(
        status=api.Status.success,
        attributes={"message": "Entry unlocked successfully"},
    )


@router.get("/reload-security-data")
async def reload_security_data(_=Depends(JWTBearer())):
    await load_permissions_and_roles()

    return api.Response(status=api.Status.success)


@router.post("/excute/{task_type}/{space_name}")
async def execute(
    space_name: str,
    task_type: TaskType,
    record: core.Record,
    branch_name: str | None = settings.default_branch,
    logged_in_user=Depends(JWTBearer()),
):

    dto = core.EntityDTO.from_record(record, space_name, logged_in_user)
    meta: core.Meta = await db.load(dto)

    if (
        meta.payload is None
        or not isinstance(meta.payload.body, str)
        or not str(meta.payload.body).endswith(".json")
    ):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media",
                code=InternalErrorCode.OBJECT_NOT_FOUND,
                message="Request object is not available",
            ),
        )

    query_dict = await db.load_resource_payload(dto)

    if meta.payload.schema_shortname == "report":
        query_dict = query_dict["query"]
    else:
        query_dict["subpath"] = query_dict["query_subpath"]
        query_dict.pop("query_subpath")

    for param, value in record.attributes.items():
        query_dict["search"] = query_dict["search"].replace(f"${param}", str(value))

    query_dict["search"] = res_sub(
        r"@\w*\:({|\()?\$\w*(}|\))?", "", query_dict["search"]
    )

    if "offset" in record.attributes:
        query_dict["offset"] = record.attributes["offset"]

    if "limit" in record.attributes:
        query_dict["limit"] = record.attributes["limit"]

    if "from_date" in record.attributes:
        query_dict["from_date"] = record.attributes["from_date"]

    if "to_date" in record.attributes:
        query_dict["to_date"] = record.attributes["to_date"]

    return await query_entries(
        query=api.Query(**query_dict), user_shortname=logged_in_user
    )


@router.get(
    "/s/{token}",
    response_model_exclude_none=True,
)
async def shoting_url(
    token: str,
):
    if url := await operational_repo.find_key(f"short/{token}"):
        return RedirectResponse(url)
    else:
        return RedirectResponse(url="/frontend")


@router.post(
    "/apply-alteration/{space_name}/{alteration_name}", response_model_exclude_none=True
)
async def apply_alteration(
    space_name: str,
    alteration_name: str,
    on_entry: core.Record,
    logged_in_user=Depends(JWTBearer()),
):
    alteration_dto = core.EntityDTO(
        space_name=space_name,
        subpath=f"{on_entry.subpath}/{on_entry.shortname}",
        shortname=alteration_name,
        resource_type=ResourceType.alteration,
        user_shortname=logged_in_user,
        branch_name=on_entry.branch_name,
    )
    alteration_meta: core.Alteration = await db.load(alteration_dto)

    parent_dto = core.EntityDTO(
        space_name=space_name,
        subpath=on_entry.subpath,
        shortname=on_entry.shortname,
        resource_type=on_entry.resource_type,
        user_shortname=logged_in_user,
        branch_name=on_entry.branch_name,
    )
    entry_meta: core.Meta = await db.load(parent_dto)

    record: core.Record = entry_meta.to_record(
        on_entry.subpath, on_entry.shortname, [], on_entry.branch_name
    )
    record.attributes["payload"] = record.attributes["payload"].__dict__
    record.attributes["payload"]["body"] = alteration_meta.requested_update

    response = await serve_request(
        request=api.Request(
            space_name=space_name, request_type=RequestType.update, records=[record]
        ),
        owner_shortname=logged_in_user,
    )

    await db.delete(alteration_dto)
    return response


@router.post("/data-asset")
async def data_asset(
    query: api.DataAssetQuery,
    _=Depends(JWTBearer()),
):
    attachments: dict[str, list[core.Record]] = await db.get_entry_attachments(
        subpath=f"{query.subpath}/{query.shortname}",
        branch_name=query.branch_name,
        attachments_path=(
            settings.spaces_folder
            / f"{query.space_name}/{branch_path(query.branch_name)}/{query.subpath}/.dm/{query.shortname}"
        ),
        filter_types=[query.data_asset_type],
        filter_shortnames=query.filter_data_assets,
    )
    files_paths: list[FilePath] = []

    dto = core.EntityDTO(
        space_name=query.space_name,
        subpath=f"{query.subpath}/{query.shortname}",
        resource_type=query.data_asset_type,
        branch_name=query.branch_name,
        shortname="",
    )
    for attachment in attachments.get(query.data_asset_type, []):
        file_path: FilePath = db.payload_path(dto)
        if (
            not isinstance(attachment.attributes.get("payload"), core.Payload)
            or not isinstance(attachment.attributes["payload"].body, str)
            or not (file_path / attachment.attributes["payload"].body).is_file()
        ):
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(
                    type="db",
                    code=InternalErrorCode.INVALID_DATA,
                    message=f"Invalid data asset file found at {attachment.subpath}/{attachment.shortname}",
                ),
            )

        file_path /= attachment.attributes["payload"].body
        if (
            attachment.attributes["payload"].schema_shortname
            and attachment.resource_type == DataAssetType.csv
        ):
            await validate_csv_with_schema(
                file_path=file_path,
                space_name=query.space_name,
                schema_shortname=attachment.attributes["payload"].schema_shortname,
            )
        if (
            attachment.attributes["payload"].schema_shortname
            and attachment.resource_type == DataAssetType.jsonl
        ):
            await validate_jsonl_with_schema(
                file_path=file_path,
                space_name=query.space_name,
                schema_shortname=attachment.attributes["payload"].schema_shortname,
            )
        files_paths.append(file_path)

    if not files_paths:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.OBJECT_NOT_FOUND,
                message="No data asset attachments found for this entry",
            ),
        )

    if query.data_asset_type in [DataAssetType.sqlite, DataAssetType.duckdb]:
        conn: duckdb.DuckDBPyConnection = duckdb.connect(str(files_paths[0]))
    else:
        conn = duckdb.connect(":default:")
        for idx, file_path in enumerate(files_paths):
            # Load the file into the in-memory DB
            match query.data_asset_type:
                case DataAssetType.csv:
                    globals().setdefault(
                        attachments[query.data_asset_type][idx].shortname,
                        conn.read_csv(str(file_path)),
                    )  # type: ignore  # noqa
                case DataAssetType.jsonl:
                    globals().setdefault(
                        attachments[query.data_asset_type][idx].shortname,
                        conn.read_json(str(file_path), format="auto"),
                    )  # type: ignore  # noqa
                case DataAssetType.parquet:
                    globals().setdefault(
                        attachments[query.data_asset_type][idx].shortname,
                        conn.read_parquet(str(file_path)),
                    )  # type: ignore  # noqa

    data: duckdb.DuckDBPyRelation = conn.sql(query=query.query_string)  # type: ignore

    temp_file = f"temp_file_from_duckdb_{int(round(time() * 1000))}.csv"
    data.write_csv(file_name=temp_file)  # type: ignore
    data_objects: list[dict[str, Any]] = await csv_file_to_json(FilePath(temp_file))
    os.remove(temp_file)

    return data_objects


@router.get("/data-asset")
async def data_asset_single(
    resource_type: ResourceType,
    space_name: str = Path(..., pattern=regex.SPACENAME, examples=["data"]),
    subpath: str = Path(..., pattern=regex.SUBPATH, examples=["/content"]),
    shortname: str = Path(..., pattern=regex.SHORTNAME, examples=["unique_shortname"]),
    schema_shortname: str | None = None,
    ext: str = Path(..., pattern=regex.EXT, examples=["png"]),
    logged_in_user=Depends(JWTBearer()),
    branch_name: str | None = settings.default_branch,
) -> StreamingResponse:
    dto = core.EntityDTO(
        space_name=space_name,
        branch_name=branch_name,
        subpath=subpath,
        shortname=shortname,
        resource_type=resource_type,
        schema_shortname=schema_shortname,
        user_shortname=branch_name,
    )

    meta: core.Meta = await db.load(dto)
    if (
        meta.payload is None
        or meta.payload.body is None
        or meta.payload.body != f"{shortname}.{ext}"
    ):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media",
                code=InternalErrorCode.OBJECT_NOT_FOUND,
                message="Request object is not available",
            ),
        )

    if not await access_control.check_access(
        dto=dto,
        meta=meta,
        action_type=core.ActionType.view,
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [9]",
            ),
        )

    await plugin_manager.before_action(dto.to_event_data(core.ActionType.view))

    payload_path = db.payload_path(dto)

    with open(payload_path / str(meta.payload.body), "r") as csv_file:
        media = "text/csv" if resource_type == ResourceType.csv else "text/plain"
        response = StreamingResponse(iter(csv_file.read()), media_type=media)
        response.headers["Content-Disposition"] = "attachment; filename=data.csv"

    await plugin_manager.after_action(dto.to_event_data(core.ActionType.view))

    return response
