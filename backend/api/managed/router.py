from copy import copy
import csv
from datetime import datetime
import hashlib
import os
import uuid
from fastapi.logger import logger
from uuid import uuid4
from re import sub as res_sub
from fastapi import APIRouter, Body, Depends, UploadFile, Path, Form, status
from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse
from utils.generate_email import generate_email_from_template, generate_subject
from utils.custom_validations import validate_uniqueness
from utils.ticket_sys_utils import (
    set_init_state_from_request,
    set_init_state_from_record,
    transite,
    post_transite,
    check_open_state,
)
import models.api as api
import models.core as core
from models.enums import (
    ContentType,
    Language,
    RequestType,
    ResourceType,
    LockAction,
    TaskType,
)
import utils.db as db
import utils.regex as regex
import sys
import json
from utils.jwt import JWTBearer, GetJWTToken, sign_jwt, remove_redis_session_key
from utils.access_control import access_control
from utils.spaces import get_spaces, initialize_spaces
from typing import Any
import utils.repository as repository
from utils.helpers import (
    branch_path,
    camel_case,
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
from utils.redis_services import RedisServices
from fastapi.responses import RedirectResponse
from languages.loader import languages
from typing import Callable


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
                type="media", code=220, message="Requested object not found"
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
    response.headers[
        "Content-Disposition"
    ] = f"attachment; filename={space_name}_{record.subpath}.csv"

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

    redis_query_policies = await access_control.get_user_query_policies(
        user_shortname, query.space_name, query.subpath
    )

    folder = await db.load(
        query.space_name,
        query.subpath,
        "",
        core.Folder,
        user_shortname,
        query.branch_name,
    )

    folder_payload = db.load_resource_payload(
        query.space_name,
        "/",
        f"{folder.shortname}.json",
        core.Folder,
        query.branch_name,
    )
    folder_views = folder_payload.get("csv_columns", [])
    if not folder_views:
        folder_views = folder_payload.get("index_attributes", [])
        
    keys: list = [i["name"] for i in folder_views]
    keys_existence = dict(zip(keys, [False for _ in range(len(keys))]))
    search_res, _ = await repository.redis_query_search(query, redis_query_policies)
    json_data = []
    timestamp_fields = ["created_at", "updated_at"]
    new_keys: set = set()
    deprecated_keys: set = set()
    async with RedisServices() as redis_services:
        for redis_document in search_res:
            redis_doc_dict = redis_document.__dict__
            if "json" in redis_doc_dict:
                redis_doc_dict = json.loads(redis_doc_dict["json"])
            if (
                redis_doc_dict.get("payload_doc_id")
                and query.retrieve_json_payload
            ):
                payload_doc_content = await redis_services.get_payload_doc(
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
                    new_col = attribute_val if column_key not in timestamp_fields else\
                        datetime.fromtimestamp(attribute_val).strftime('%Y-%m-%d %H:%M:%S')
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
        core.Event(
            space_name=query.space_name,
            branch_name=query.branch_name,
            subpath=query.subpath,
            action_type=core.ActionType.query,
            user_shortname=user_shortname,
        )
    )

    if len(json_data) == 0:
        return api.Response(
            status=api.Status.success,
            attributes={"message": "The records are empty"},
        )


    keys = [key for key in keys if keys_existence[key]]
    v_path = StringIO()
    
    list_deprecated_keys = list(deprecated_keys)
    keys = list(filter(lambda item:item not in list_deprecated_keys, keys))
    writer = csv.DictWriter(v_path, fieldnames=(keys + list(new_keys)))
    writer.writeheader()
    writer.writerows(json_data)

    response = StreamingResponse(iter([v_path.getvalue()]), media_type="text/csv")
    response.headers[
        "Content-Disposition"
    ] = f"attachment; filename={query.space_name}_{query.subpath}.csv"

    return response


@router.post("/space", response_model=api.Response, response_model_exclude_none=True)
async def serve_space(
    request: api.Request, owner_shortname=Depends(JWTBearer())
) -> api.Response:
    spaces = await get_spaces()
    record = request.records[0]
    history_diff = {}
    match request.request_type:
        case api.RequestType.create:
            if request.space_name in spaces:
                raise api.Exception(
                    status.HTTP_400_BAD_REQUEST,
                    api.Error(
                        type="request",
                        code=203,
                        message="Space name provided already existed [1]",
                    ),
                )

            if not await access_control.check_access(
                user_shortname=owner_shortname,
                space_name=settings.all_spaces_mw,
                subpath="/",
                resource_type=ResourceType.space,
                action_type=core.ActionType.create,
                record_attributes=record.attributes,
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=401,
                        message="You don't have permission to this action [1]",
                    ),
                )

            resource_obj = core.Meta.from_record(
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
            await db.save(
                request.space_name,
                record.subpath,
                resource_obj,
                settings.default_branch,
            )

        case api.RequestType.update:
            try:
                space = core.Space.from_record(record, owner_shortname)
                if (
                    request.space_name not in spaces
                    or request.space_name != record.shortname
                ):
                    raise Exception
            except Exception:
                raise api.Exception(
                    status.HTTP_400_BAD_REQUEST,
                    api.Error(
                        type="request",
                        code=203,
                        message="Space name provided is empty or invalid [6]",
                    ),
                )
            if not await access_control.check_access(
                user_shortname=owner_shortname,
                space_name=settings.all_spaces_mw,
                subpath="/",
                resource_type=ResourceType.space,
                action_type=core.ActionType.update,
                record_attributes=record.attributes,
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=401,
                        message="You don't have permission to this action [2]",
                    ),
                )

            await plugin_manager.before_action(
                core.Event(
                    space_name=space.shortname,
                    branch_name=record.branch_name,
                    subpath=record.subpath,
                    shortname=space.shortname,
                    action_type=core.ActionType.update,
                    resource_type=record.resource_type,
                    user_shortname=owner_shortname,
                )
            )

            old_space = await db.load(
                space_name=space.shortname,
                subpath=record.subpath,
                shortname=space.shortname,
                class_type=core.Space,
                user_shortname=owner_shortname,
                branch_name=record.branch_name,
            )
            history_diff = await db.update(
                space_name=space.shortname,
                subpath=record.subpath,
                meta=space,
                old_version_flattend=flatten_dict(old_space.model_dump()),
                new_version_flattend=flatten_dict(space.model_dump()),
                updated_attributes_flattend=list(
                    flatten_dict(record.attributes).keys()
                ),
                branch_name=record.branch_name,
                user_shortname=owner_shortname,
            )

        case api.RequestType.delete:
            if request.space_name not in spaces:
                raise api.Exception(
                    status.HTTP_400_BAD_REQUEST,
                    api.Error(
                        type="request",
                        code=202,
                        message="Space name provided is empty or invalid [2]",
                    ),
                )

            if not await access_control.check_access(
                user_shortname=owner_shortname,
                space_name=settings.all_spaces_mw,
                subpath="/",
                resource_type=ResourceType.space,
                action_type=core.ActionType.delete,
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=401,
                        message="You don't have permission to this action [3]",
                    ),
                )

            os.system(f"rm -r {settings.spaces_folder}/{request.space_name}")

            async with RedisServices() as redis_services:
                x = await redis_services.list_indices()
                if x :
                    indices: list[str] = x
                    for index in indices:
                        if index.startswith(f"{request.space_name}:"):
                            await redis_services.drop_index(index, True)

        case _:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=401,
                    message="Not allowed request",
                ),
            )

    await initialize_spaces()

    await access_control.load_permissions_and_roles()

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

    redis_query_policies = await access_control.get_user_query_policies(
        user_shortname, query.space_name, query.subpath
    )

    total, records = await repository.serve_query(
        query, user_shortname, redis_query_policies
    )

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
    spaces = await get_spaces()
    if request.space_name not in spaces:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=202,
                message="Space name provided is empty or invalid [3]",
            ),
        )
    if not request.records:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=202,
                message="Request records cannot be empty",
            ),
        )

    records = []
    failed_records = []
    match request.request_type:
        case api.RequestType.create:
            for record in request.records:
                if record.subpath[0] != "/":
                    record.subpath = f"/{record.subpath}"
                try:
                    schema_shortname: str | None = None
                    if (
                        "payload" in record.attributes
                        and isinstance(record.attributes.get("payload", None), dict)
                        and "schema_shortname" in record.attributes["payload"]
                    ):
                        schema_shortname = record.attributes["payload"][
                            "schema_shortname"
                        ]
                    await plugin_manager.before_action(
                        core.Event(
                            space_name=request.space_name,
                            branch_name=record.branch_name,
                            subpath=record.subpath,
                            shortname=record.shortname,
                            action_type=core.ActionType.create,
                            schema_shortname=schema_shortname,
                            resource_type=record.resource_type,
                            user_shortname=owner_shortname,
                        )
                    )

                    if not await access_control.check_access(
                        user_shortname=owner_shortname,
                        space_name=request.space_name,
                        subpath=record.subpath,
                        resource_type=record.resource_type,
                        action_type=core.ActionType.create,
                        record_attributes=record.attributes,
                    ):
                        raise api.Exception(
                            status.HTTP_401_UNAUTHORIZED,
                            api.Error(
                                type="request",
                                code=401,
                                message="You don't have permission to this action [4]",
                            ),
                        )

                    if record.resource_type == ResourceType.ticket:
                        record = await set_init_state_from_request(
                            request, record.branch_name, owner_shortname
                        )

                    resource_cls = getattr(
                        sys.modules["models.core"], camel_case(record.resource_type)
                    )
                    if issubclass(resource_cls, core.Attachment):
                        search_path, filename = db.metapath(
                            request.space_name,
                            record.subpath,
                            record.shortname,
                            resource_cls,
                            record.branch_name,
                        )
                    else:
                        search_path = (
                            settings.spaces_folder
                            / f"{request.space_name}/{record.subpath}"
                        )
                        filename = record.shortname

                    shortname_exists = repository.dir_has_file(
                        dir_path=search_path, 
                        filename=filename, 
                        resource_type=record.resource_type
                    )
                    if shortname_exists and record.shortname != settings.auto_uuid_rule:
                        raise api.Exception(
                            status.HTTP_400_BAD_REQUEST,
                            api.Error(
                                type="request",
                                code=400,
                                message=f"This shortname {record.shortname} already exists",
                            ),
                        )

                    await validate_uniqueness(request.space_name, record)

                    resource_obj = core.Meta.from_record(
                        record=record, owner_shortname=owner_shortname
                    )
                    if not is_internal or "created_at" not in record.attributes:
                        resource_obj.created_at = datetime.now()
                        resource_obj.updated_at = datetime.now()
                    body_shortname = record.shortname
                    if resource_obj.shortname == settings.auto_uuid_rule:
                        resource_obj.uuid = uuid4()
                        resource_obj.shortname = str(resource_obj.uuid)[:8]
                        record.shortname = str(resource_obj.uuid)[:8]
                        body_shortname = resource_obj.shortname

                    separate_payload_data = None
                    if (
                        resource_obj.payload
                        and resource_obj.payload.content_type == ContentType.json
                        and resource_obj.payload.body is not None
                    ):
                        separate_payload_data = resource_obj.payload.body
                        resource_obj.payload.body = body_shortname + ".json"

                    if (
                        resource_obj.payload
                        and resource_obj.payload.content_type == ContentType.json
                        and resource_obj.payload.schema_shortname
                        and isinstance(separate_payload_data, dict)
                    ):
                        await validate_payload_with_schema(
                            payload_data=separate_payload_data,
                            space_name=request.space_name,
                            branch_name=record.branch_name,
                            schema_shortname=resource_obj.payload.schema_shortname,
                        )

                    await db.save(
                        request.space_name,
                        record.subpath,
                        resource_obj,
                        record.branch_name,
                    )

                    if isinstance(resource_obj, core.User):
                        # SMS Invitation
                        if not resource_obj.is_msisdn_verified and resource_obj.msisdn:
                            inv_link = await repository.store_user_invitation_token(
                                resource_obj, "SMS"
                            )
                            if inv_link:
                                await send_sms(
                                    msisdn=record.attributes.get("msisdn", ""),
                                    message=languages[
                                        resource_obj.language
                                    ]["invitation_message"].replace(
                                        "{link}", 
                                        await repository.url_shortner(inv_link)
                                    ),
                                )
                        # EMAIL Invitation
                        if not resource_obj.is_email_verified and resource_obj.email:
                            inv_link = await repository.store_user_invitation_token(
                                resource_obj, "EMAIL"
                            )
                            if inv_link:
                                await send_email(
                                    from_address=settings.email_sender,
                                    to_address=resource_obj.email,
                                    message=generate_email_from_template(
                                        "activation",
                                        {
                                            "link": await repository.url_shortner(
                                                inv_link
                                            ),
                                            "name": record.attributes.get(
                                                "displayname", {}
                                            ).get("en", ""),
                                            "shortname": resource_obj.shortname,
                                            "msisdn": resource_obj.msisdn,
                                        },
                                    ),
                                    subject=generate_subject("activation"),
                                )
                        

                    if separate_payload_data is not None and isinstance(
                        separate_payload_data, dict
                    ):
                        await db.save_payload_from_json(
                            request.space_name,
                            record.subpath,
                            resource_obj,
                            separate_payload_data,
                            record.branch_name,
                        )

                    records.append(
                        resource_obj.to_record(
                            record.subpath,
                            resource_obj.shortname,
                            [],
                            record.branch_name,
                        )
                    )
                    record.attributes["logged_in_user_token"] = token
                    await plugin_manager.after_action(
                        core.Event(
                            space_name=request.space_name,
                            branch_name=record.branch_name,
                            subpath=record.subpath,
                            shortname=resource_obj.shortname,
                            action_type=core.ActionType.create,
                            schema_shortname=record.attributes.get("payload", {}).get(
                                "schema_shortname", None
                            ),
                            resource_type=record.resource_type,
                            user_shortname=owner_shortname,
                            attributes=record.attributes,
                        )
                    )

                except api.Exception as e:
                    failed_records.append(
                        {
                            "record": record,
                            "error": e.error.message,
                            "error_code": e.error.code,
                        }
                    )
        case api.RequestType.update | api.RequestType.r_replace:
            for record in request.records:
                if record.subpath[0] != "/":
                    record.subpath = f"/{record.subpath}"
                await plugin_manager.before_action(
                    core.Event(
                        space_name=request.space_name,
                        branch_name=record.branch_name,
                        subpath=record.subpath,
                        shortname=record.shortname,
                        schema_shortname=record.attributes.get("payload", {}).get(
                            "schema_shortname", None
                        ),
                        action_type=core.ActionType.update,
                        resource_type=record.resource_type,
                        user_shortname=owner_shortname,
                    )
                )

                resource_cls = getattr(
                    sys.modules["models.core"], camel_case(record.resource_type)
                )
                schema_shortname = record.attributes.get("payload", {}).get(
                    "schema_shortname"
                )
                old_resource_obj = await db.load(
                    space_name=request.space_name,
                    subpath=record.subpath,
                    shortname=record.shortname,
                    class_type=resource_cls,
                    user_shortname=owner_shortname,
                    branch_name=record.branch_name,
                    schema_shortname=schema_shortname,
                )

                # CHECK PERMISSION
                if not await access_control.check_access(
                    user_shortname=owner_shortname,
                    space_name=request.space_name,
                    subpath=record.subpath,
                    resource_type=record.resource_type,
                    action_type=core.ActionType.update,
                    resource_is_active=old_resource_obj.is_active,
                    resource_owner_shortname=old_resource_obj.owner_shortname,
                    resource_owner_group=old_resource_obj.owner_group_shortname,
                    record_attributes=record.attributes,
                ):
                    raise api.Exception(
                        status.HTTP_401_UNAUTHORIZED,
                        api.Error(
                            type="request",
                            code=401,
                            message="You don't have permission to this action [5]",
                        ),
                    )

                # GET PAYLOAD DATA
                old_resource_payload_body = {}
                old_version_flattend = flatten_dict(old_resource_obj.model_dump())
                if (
                    old_resource_obj.payload
                    and old_resource_obj.payload.content_type == ContentType.json
                    and isinstance(old_resource_obj.payload.body, str)
                ):
                    try:
                        old_resource_payload_body = db.load_resource_payload(
                            space_name=request.space_name,
                            subpath=record.subpath,
                            filename=old_resource_obj.payload.body,
                            class_type=resource_cls,
                            branch_name=record.branch_name,
                            schema_shortname=schema_shortname,
                        )
                    except api.Exception as e:
                        if request.request_type == api.RequestType.update:
                            raise e

                    old_version_flattend.pop("payload.body", None)
                    old_version_flattend.update(
                        flatten_dict({"payload.body": old_resource_payload_body})
                    )
                # GENERATE NEW RESOURCE OBJECT
                resource_obj = old_resource_obj
                resource_obj.updated_at = datetime.now()
                new_resource_payload_data: dict | None = (
                    resource_obj.update_from_record(
                        record=record,
                        old_body=old_resource_payload_body,
                        replace=request.request_type == api.RequestType.r_replace,
                    )
                )
                new_version_flattend = flatten_dict(resource_obj.model_dump())
                if new_resource_payload_data:
                    new_version_flattend.update(
                        flatten_dict({"payload.body": new_resource_payload_data})
                    )

                await validate_uniqueness(
                    request.space_name, record, RequestType.update
                )
                # VALIDATE SEPARATE PAYLOAD BODY
                if (
                    resource_obj.payload
                    and resource_obj.payload.content_type == ContentType.json
                    and resource_obj.payload.schema_shortname
                    and new_resource_payload_data is not None
                ):
                    await validate_payload_with_schema(
                        payload_data=new_resource_payload_data,
                        space_name=request.space_name,
                        branch_name=record.branch_name or settings.default_branch,
                        schema_shortname=resource_obj.payload.schema_shortname,
                    )

                updated_attributes_flattend=list(
                    flatten_dict(record.attributes).keys()
                )
                if request.request_type == RequestType.r_replace:
                    updated_attributes_flattend = (
                        list(old_version_flattend.keys()) + 
                        list(new_version_flattend.keys())
                    )
                history_diff = await db.update(
                    space_name=request.space_name,
                    subpath=record.subpath,
                    meta=resource_obj,
                    old_version_flattend=old_version_flattend,
                    new_version_flattend=new_version_flattend,
                    updated_attributes_flattend=updated_attributes_flattend,
                    branch_name=record.branch_name,
                    user_shortname=owner_shortname,
                    schema_shortname=schema_shortname,
                )
                if new_resource_payload_data is not None:
                    await db.save_payload_from_json(
                        request.space_name,
                        record.subpath,
                        resource_obj,
                        new_resource_payload_data,
                        record.branch_name,
                    )
                    
                if(
                    isinstance(resource_obj, core.User) and 
                    record.attributes.get("is_active") is False
                ):
                    await remove_redis_session_key(record.shortname)

                records.append(
                    resource_obj.to_record(
                        record.subpath, resource_obj.shortname, [], record.branch_name
                    )
                )

                await plugin_manager.after_action(
                    core.Event(
                        space_name=request.space_name,
                        branch_name=record.branch_name,
                        subpath=record.subpath,
                        shortname=record.shortname,
                        schema_shortname=record.attributes.get("payload", {}).get(
                            "schema_shortname", None
                        ),
                        action_type=core.ActionType.update,
                        resource_type=record.resource_type,
                        user_shortname=owner_shortname,
                        attributes={"history_diff": history_diff},
                    )
                )

        case api.RequestType.delete:
            for record in request.records:
                if record.subpath[0] != "/":
                    record.subpath = f"/{record.subpath}"
                await plugin_manager.before_action(
                    core.Event(
                        space_name=request.space_name,
                        branch_name=record.branch_name,
                        subpath=record.subpath,
                        shortname=record.shortname,
                        action_type=core.ActionType.delete,
                        resource_type=record.resource_type,
                        user_shortname=owner_shortname,
                    )
                )

                resource_cls = getattr(
                    sys.modules["models.core"], camel_case(record.resource_type)
                )
                schema_shortname = record.attributes.get("payload", {}).get(
                    "schema_shortname"
                )
                resource_obj = await db.load(
                    space_name=request.space_name,
                    subpath=record.subpath,
                    shortname=record.shortname,
                    class_type=resource_cls,
                    user_shortname=owner_shortname,
                    branch_name=record.branch_name,
                    schema_shortname=schema_shortname,
                )
                if not await access_control.check_access(
                    user_shortname=owner_shortname,
                    space_name=request.space_name,
                    subpath=record.subpath,
                    resource_type=record.resource_type,
                    action_type=core.ActionType.delete,
                    resource_is_active=resource_obj.is_active,
                    resource_owner_shortname=resource_obj.owner_shortname,
                    resource_owner_group=resource_obj.owner_group_shortname,
                ):
                    raise api.Exception(
                        status.HTTP_401_UNAUTHORIZED,
                        api.Error(
                            type="request",
                            code=401,
                            message="You don't have permission to this action [6]",
                        ),
                    )

                await db.delete(
                    space_name=request.space_name,
                    subpath=record.subpath,
                    meta=resource_obj,
                    branch_name=record.branch_name,
                    user_shortname=owner_shortname,
                    schema_shortname=schema_shortname,
                )

                await plugin_manager.after_action(
                    core.Event(
                        space_name=request.space_name,
                        branch_name=record.branch_name,
                        subpath=record.subpath,
                        shortname=record.shortname,
                        action_type=core.ActionType.delete,
                        resource_type=record.resource_type,
                        user_shortname=owner_shortname,
                        attributes={"entry": resource_obj},
                    )
                )

        case api.RequestType.move:
            for record in request.records:
                if record.subpath[0] != "/":
                    record.subpath = f"/{record.subpath}"
                if (
                    "dest_subpath" not in record.attributes
                    or not record.attributes["dest_subpath"]
                ) and (
                    "dest_shortname" not in record.attributes
                    or not record.attributes["dest_shortname"]
                ):
                    raise api.Exception(
                        status.HTTP_400_BAD_REQUEST,
                        api.Error(
                            type="move",
                            code=202,
                            message="Please provide a destination path or a new shortname",
                        ),
                    )

                if (
                    "src_subpath" not in record.attributes
                    or not record.attributes["src_subpath"]
                ) or (
                    "src_shortname" not in record.attributes
                    or not record.attributes["src_shortname"]
                ):
                    raise api.Exception(
                        status.HTTP_400_BAD_REQUEST,
                        api.Error(
                            type="move",
                            code=202,
                            message="Please provide a source path and a src shortname",
                        ),
                    )

                await plugin_manager.before_action(
                    core.Event(
                        space_name=request.space_name,
                        branch_name=record.branch_name,
                        subpath=record.attributes["src_subpath"],
                        shortname=record.attributes["src_shortname"],
                        action_type=core.ActionType.move,
                        resource_type=record.resource_type,
                        user_shortname=owner_shortname,
                        attributes={"dest_subpath": record.attributes["dest_subpath"]},
                    )
                )

                resource_cls = getattr(
                    sys.modules["models.core"], camel_case(record.resource_type)
                )
                resource_obj = await db.load(
                    space_name=request.space_name,
                    subpath=record.attributes["src_subpath"],
                    shortname=record.attributes["src_shortname"],
                    class_type=resource_cls,
                    user_shortname=owner_shortname,
                    branch_name=record.branch_name,
                )
                if not await access_control.check_access(
                    user_shortname=owner_shortname,
                    space_name=request.space_name,
                    subpath=record.attributes["src_subpath"],
                    resource_type=record.resource_type,
                    action_type=core.ActionType.delete,
                    resource_is_active=resource_obj.is_active,
                    resource_owner_shortname=resource_obj.owner_shortname,
                    resource_owner_group=resource_obj.owner_group_shortname,
                ) or not await access_control.check_access(
                    user_shortname=owner_shortname,
                    space_name=request.space_name,
                    subpath=record.attributes["dest_subpath"],
                    resource_type=record.resource_type,
                    action_type=core.ActionType.create,
                ):
                    raise api.Exception(
                        status.HTTP_401_UNAUTHORIZED,
                        api.Error(
                            type="request",
                            code=401,
                            message="You don't have permission to this action [7]",
                        ),
                    )
                await db.move(
                    request.space_name,
                    record.attributes["src_subpath"],
                    record.attributes["src_shortname"],
                    record.attributes["dest_subpath"],
                    record.attributes["dest_shortname"],
                    resource_obj,
                    record.branch_name,
                )

                await plugin_manager.after_action(
                    core.Event(
                        space_name=request.space_name,
                        branch_name=record.branch_name,
                        subpath=record.attributes["dest_subpath"],
                        shortname=record.attributes["dest_shortname"],
                        action_type=core.ActionType.move,
                        resource_type=record.resource_type,
                        user_shortname=owner_shortname,
                        attributes={
                            "src_subpath": record.attributes["src_subpath"],
                            "src_shortname": record.attributes["src_shortname"],
                        },
                    )
                )

    if len(failed_records) == 0:
        return api.Response(status=api.Status.success, records=records)
    else:
        raise api.Exception(
            status_code=400,
            error=api.Error(
                type="request",
                code=400,
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
    space_name: str = Path(..., pattern=regex.SPACENAME),
    subpath: str = Path(..., pattern=regex.SUBPATH),
    shortname: str = Path(..., pattern=regex.SHORTNAME),
    action: str = Path(...),
    resolution: str | None = Body(None, embed=True),
    comment: str | None = Body(None, embed=True),
    branch_name: str | None = settings.default_branch,
) -> api.Response:
    spaces = await get_spaces()
    if space_name not in spaces:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=202,
                message="Space name provided is empty or invalid [4]",
            ),
        )
    _user_roles = await access_control.get_user_roles(logged_in_user)
    user_roles = _user_roles.keys()

    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            branch_name=branch_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.progress_ticket,
            resource_type=ResourceType.ticket,
            user_shortname=logged_in_user,
        )
    )

    ticket_obj = await db.load(
        space_name=space_name,
        subpath=subpath,
        shortname=shortname,
        class_type=core.Ticket,
        user_shortname=logged_in_user,
        branch_name=branch_name,
    )
    if ticket_obj.payload is None or ticket_obj.payload.body is None:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media", code=220, message="Requested object not found"
            ),
        )

    if not await access_control.check_access(
        user_shortname=logged_in_user,
        space_name=space_name,
        subpath=subpath,
        resource_type=ResourceType.ticket,
        action_type=core.ActionType.update,
        resource_is_active=ticket_obj.is_active,
        resource_owner_shortname=ticket_obj.owner_shortname,
        resource_owner_group=ticket_obj.owner_group_shortname,
        record_attributes={"state": "", "resolution_reason": ""},
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=401,
                message="You don't have permission to this action [8]",
            ),
        )
    if ticket_obj.payload.content_type == ContentType.json:
        workflows_data = await db.load(
            space_name=space_name,
            subpath="workflows",
            shortname=ticket_obj.workflow_shortname,
            class_type=core.Content,
            user_shortname=logged_in_user,
            branch_name=branch_name,
        )

        if (
            workflows_data.payload is not None
            and workflows_data.payload.body is not None
        ):
            workflows_payload = db.load_resource_payload(
                space_name=space_name,
                subpath="workflows",
                filename=str(workflows_data.payload.body),
                class_type=core.Content,
                branch_name=branch_name,
            )
            if not ticket_obj.is_open:
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="transition",
                        code=299,
                        message="Ticket is already in closed",
                    ),
                )
            response = transite(
                workflows_payload["states"], ticket_obj.state, action, user_roles
            )

            if not response["status"]:
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="transition",
                        code=300,
                        message=response["message"],
                    ),
                )

            old_version_flattend = flatten_dict(ticket_obj.model_dump())
            old_version_flattend.pop("payload.body", None)
            old_version_flattend.update(flatten_dict({"payload.body": ticket_obj}))

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
                            code=301,
                            message=post_response["message"],
                        ),
                    )
                ticket_obj.resolution_reason = resolution

            new_version_flattend = flatten_dict(ticket_obj.model_dump())
            new_version_flattend.pop("payload.body", None)
            new_version_flattend.update(flatten_dict({"payload.body": ticket_obj}))

            if comment:
                time = datetime.now().strftime("%Y%m%d%H%M%S")
                new_version_flattend["comment"] = comment
                payload = {
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

            history_diff = await db.update(
                space_name,
                f"/{subpath}",
                ticket_obj,
                old_version_flattend,
                new_version_flattend,
                ["state", "resolution_reason", "comment"],
                branch_name,
                logged_in_user,
            )
            await plugin_manager.after_action(
                core.Event(
                    space_name=space_name,
                    branch_name=branch_name,
                    subpath=subpath,
                    shortname=shortname,
                    action_type=core.ActionType.progress_ticket,
                    resource_type=ResourceType.ticket,
                    user_shortname=logged_in_user,
                    attributes={
                        "history_diff": history_diff,
                        "state": ticket_obj.state,
                    },
                )
            )
            return api.Response(status=api.Status.success)

    raise api.Exception(
        status.HTTP_400_BAD_REQUEST,
        error=api.Error(type="ticket", code=221, message="Workflow body not found"),
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
    space_name: str = Path(..., pattern=regex.SPACENAME),
    subpath: str = Path(..., pattern=regex.SUBPATH),
    shortname: str = Path(..., pattern=regex.SHORTNAME),
    schema_shortname: str | None = None,
    ext: str = Path(..., pattern=regex.EXT),
    logged_in_user=Depends(JWTBearer()),
    branch_name: str | None = settings.default_branch,
) -> FileResponse:
    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            branch_name=branch_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.view,
            resource_type=resource_type,
            user_shortname=logged_in_user,
        )
    )

    cls = getattr(sys.modules["models.core"], camel_case(resource_type))
    meta: core.Meta = await db.load(
        space_name=space_name,
        subpath=subpath,
        shortname=shortname,
        class_type=cls,
        user_shortname=logged_in_user,
        branch_name=branch_name,
        schema_shortname=schema_shortname,
    )
    if (
        meta.payload is None
        or meta.payload.body is None
        or meta.payload.body != f"{shortname}.{ext}"
    ):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media", code=220, message="Requested object not found"
            ),
        )

    if not await access_control.check_access(
        user_shortname=logged_in_user,
        space_name=space_name,
        subpath=subpath,
        resource_type=resource_type,
        action_type=core.ActionType.view,
        resource_is_active=meta.is_active,
        resource_owner_shortname=meta.owner_shortname,
        resource_owner_group=meta.owner_group_shortname,
        entry_shortname=meta.shortname
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=401,
                message="You don't have permission to this action [9]",
            ),
        )

    payload_path = db.payload_path(
        space_name=space_name,
        subpath=subpath,
        class_type=cls,
        branch_name=branch_name,
        schema_shortname=schema_shortname,
    )
    print(f"{payload_path=}")
    print(f"{meta.payload.body=}")
    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
            branch_name=branch_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.view,
            resource_type=resource_type,
            user_shortname=logged_in_user,
        )
    )

    return FileResponse(payload_path / str(meta.payload.body))


@router.post(
    "/resource_with_payload",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def create_or_update_resource_with_payload(
    payload_file: UploadFile,
    request_record: UploadFile,
    space_name: str = Form(...),
    owner_shortname=Depends(JWTBearer()),
):
    # NOTE We currently make no distinction between create and update.
    # in such case update should contain all the data every time.
    spaces = await get_spaces()
    if space_name not in spaces:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=202,
                message="Space name provided is empty or invalid [5]",
            ),
        )
    payload_filename = payload_file.filename or ""
    if payload_filename.endswith(".json"):
        resource_content_type = ContentType.json
    elif payload_file.content_type == "application/pdf":
        resource_content_type = ContentType.pdf
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
                code=217,
                message="The file type is not supported",
            ),
        )

    record = core.Record.model_validate_json(request_record.file.read())
    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            branch_name=record.branch_name,
            subpath=record.subpath,
            shortname=record.shortname,
            action_type=core.ActionType.create,
            schema_shortname=record.attributes.get("payload", {}).get(
                "schema_shortname", None
            ),
            resource_type=record.resource_type,
            user_shortname=owner_shortname,
        )
    )

    if not await access_control.check_access(
        user_shortname=owner_shortname,
        space_name=space_name,
        subpath=record.subpath,
        resource_type=record.resource_type,
        action_type=core.ActionType.create,
        record_attributes=record.attributes,
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=401,
                message="You don't have permission to this action [10]",
            ),
        )

    sha1 = hashlib.sha1()
    sha1.update(payload_file.file.read())
    checksum = sha1.hexdigest()
    await payload_file.seek(0)
    if record.resource_type == ResourceType.ticket:
        record = await set_init_state_from_record(
            record, record.branch_name, owner_shortname, space_name
        )
    resource_obj = core.Meta.from_record(record=record, owner_shortname=owner_shortname)
    if record.resource_type == ResourceType.ticket:
        record = await set_init_state_from_record(
            record, record.branch_name, owner_shortname, space_name
        )
    resource_obj.payload = core.Payload(
        content_type=resource_content_type,
        checksum=checksum,
        schema_shortname="meta_schema"
        if record.resource_type == ResourceType.schema
        else (
            None
            if "schema_shortname" not in record.attributes
            else record.attributes["schema_shortname"]
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
                code=217,
                message="Only resources of type 'attachment' or 'content' are allowed",
            ),
        )

    if resource_obj.shortname == settings.auto_uuid_rule:
        resource_obj.uuid = uuid4()
        resource_obj.shortname = str(resource_obj.uuid)[:8]
        resource_obj.payload.body = (
            f"{str(resource_obj.uuid)[:8]}." + payload_filename.split(".")[1]
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

    await db.save(space_name, record.subpath, resource_obj, record.branch_name)
    await db.save_payload(
        space_name, record.subpath, resource_obj, payload_file, record.branch_name
    )

    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
            branch_name=record.branch_name,
            subpath=record.subpath,
            shortname=record.shortname,
            action_type=core.ActionType.create,
            schema_shortname=record.attributes.get("payload", {}).get(
                "schema_shortname", None
            ),
            resource_type=record.resource_type,
            user_shortname=owner_shortname,
        )
    )

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
    space_name: str = Path(..., pattern=regex.SPACENAME),
    subpath: str = Path(..., pattern=regex.SUBPATH),
    schema_shortname: str = Path(..., pattern=regex.SHORTNAME),
    owner_shortname=Depends(JWTBearer()),
    branch_name: str | None = settings.default_branch,
):
    contents = await resources_file.read()
    decoded = contents.decode()
    buffer = StringIO(decoded)
    csv_reader = csv.DictReader(buffer)

    schema_path = (
        db.payload_path(space_name, "schema", core.Schema, branch_name)
        / f"{schema_shortname}.json"
    )
    with open(schema_path) as schema_file:
        schema_content = json.load(schema_file)
    schema_content = resolve_schema_references(schema_content)

    data_types_mapper : dict[str, Callable] = {
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
    space_name: str = Path(..., pattern=regex.SPACENAME),
    subpath: str = Path(..., pattern=regex.SUBPATH),
    shortname: str = Path(..., pattern=regex.SHORTNAME),
    retrieve_json_payload: bool = False,
    retrieve_attachments: bool = False,
    validate_schema: bool = True,
    logged_in_user=Depends(JWTBearer()),
    branch_name: str | None = settings.default_branch,
) -> dict[str, Any]:
    if subpath == settings.root_subpath_mw:
        subpath = "/"

    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            branch_name=branch_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.view,
            resource_type=resource_type,
            user_shortname=logged_in_user,
        )
    )

    resource_class = getattr(sys.modules["models.core"], camel_case(resource_type))
    meta: core.Meta = await db.load(
        space_name=space_name,
        subpath=subpath,
        shortname=shortname,
        class_type=resource_class,
        user_shortname=logged_in_user,
        branch_name=branch_name,
    )
    if meta is None:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media", code=221, message="Requested object not found"
            ),
        )

    if not await access_control.check_access(
        user_shortname=logged_in_user,
        space_name=space_name,
        subpath=subpath,
        resource_type=resource_type,
        action_type=core.ActionType.view,
        resource_is_active=meta.is_active,
        resource_owner_shortname=meta.owner_shortname,
        resource_owner_group=meta.owner_group_shortname,
        entry_shortname=meta.shortname
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=401,
                message="You don't have permission to this action [11]",
            ),
        )

    attachments = {}
    entry_path = (
        settings.spaces_folder
        / f"{space_name}/{branch_path(branch_name)}/{subpath}/.dm/{shortname}"
    )
    if retrieve_attachments:
        attachments = await repository.get_entry_attachments(
            subpath=subpath,
            attachments_path=entry_path,
            branch_name=branch_name,
            retrieve_json_payload=retrieve_json_payload,
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

    payload_body = db.load_resource_payload(
        space_name=space_name,
        subpath=subpath,
        filename=meta.payload.body,
        class_type=resource_class,
        branch_name=branch_name,
    )

    if meta.payload and meta.payload.schema_shortname and validate_schema:
        await validate_payload_with_schema(
            payload_data=payload_body,
            space_name=space_name,
            branch_name=branch_name or settings.default_branch,
            schema_shortname=meta.payload.schema_shortname,
        )

    meta.payload.body = payload_body
    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
            branch_name=branch_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.view,
            resource_type=resource_type,
            user_shortname=logged_in_user,
        )
    )
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
    return await repository.get_entry_by_var(
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
    return await repository.get_entry_by_var(
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

#     spaces = await get_spaces()
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
#                     code=401,
#                     message="You don't have permission to this action [12]",
#                 ),
#             )

#     async with RedisServices() as redis_services:
#         await redis_services.create_indices(
#             for_space, for_schemas
#         )
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
    space_name: str,
    health_type: str,
    logged_in_user=Depends(JWTBearer()),
    branch_name: str | None = settings.default_branch,
):
    if logged_in_user != "dmart":
        raise api.Exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error=api.Error(type="access", code=401, message="Not allowed"),
        )

    spaces = await get_spaces()
    if space_name not in spaces and space_name != "all":
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(type="media", code=221, message="Invalid space name"),
        )
    if health_type not in ["soft", "hard"]:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media", code=221, message="Invalid health check type"
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
                type="db", code=12, message="requested object is not found"
            ),
        )
        
    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            branch_name=branch_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.lock,
            user_shortname=logged_in_user,
        )
    )

    if resource_type == ResourceType.ticket:
        cls = getattr(sys.modules["models.core"], camel_case(resource_type))
        meta: core.Ticket = await db.load(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            class_type=cls,
            user_shortname=logged_in_user,
        )
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

    # if lock file is doesn't exist
    # elif lock file exit but lock_period expired
    # elif lock file exist and lock_period isn't expired but the owner want to extend the lock
    async with RedisServices() as redis_services:
        lock_type = await redis_services.save_lock_doc(
            space_name,
            branch_name,
            subpath,
            shortname,
            logged_in_user,
            settings.lock_period,
        )

    await db.store_entry_diff(
        space_name,
        branch_name,
        "/" + subpath,
        shortname,
        logged_in_user,
        {},
        {"lock_type": lock_type},
        ["lock_type"],
        core.Content,
    )
    
    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
            branch_name=branch_name,
            subpath=subpath,
            shortname=shortname,
            resource_type=ResourceType.ticket,
            action_type=core.ActionType.lock,
            user_shortname=logged_in_user,
        )
    )
    
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
    async with RedisServices() as redis_services:
        lock_payload = await redis_services.get_lock_doc(
            space_name, branch_name, subpath, shortname
        )

    if not lock_payload or lock_payload["owner_shortname"] != logged_in_user:
        raise api.Exception(
            status_code=status.HTTP_403_FORBIDDEN,
            error=api.Error(
                type="lock",
                code=30,
                message="Lock does not exist or you have no access",
            ),
        )
        
    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            branch_name=branch_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.unlock,
            user_shortname=logged_in_user,
        )
    )

    async with RedisServices() as redis_services:
        await redis_services.delete_lock_doc(
            space_name, branch_name, subpath, shortname
        )

    await db.store_entry_diff(
        space_name,
        branch_name,
        "/" + subpath,
        shortname,
        logged_in_user,
        {},
        {"lock_type": LockAction.cancel},
        ["lock_type"],
        core.Content,
    )
    
    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
            branch_name=branch_name,
            subpath=subpath,
            shortname=shortname,
            resource_type=ResourceType.ticket,
            action_type=core.ActionType.unlock,
            user_shortname=logged_in_user,
        )
    )
    
    return api.Response(
        status=api.Status.success,
        attributes={"message": "Entry unlocked successfully"},
    )


@router.get("/reload-security-data")
async def reload_security_data(_=Depends(JWTBearer())):
    await access_control.load_permissions_and_roles()

    return api.Response(status=api.Status.success)


@router.post("/excute/{task_type}/{space_name}")
async def execute(
    space_name: str,
    task_type: TaskType,
    record: core.Record,
    branch_name: str | None = settings.default_branch,
    logged_in_user=Depends(JWTBearer()),
):
    task_type = task_type
    meta = await db.load(
        space_name=space_name,
        subpath=record.subpath,
        shortname=record.shortname,
        class_type=core.Content,
        user_shortname=logged_in_user,
        branch_name=branch_name,
    )

    if (
        meta.payload is None
        or not isinstance(meta.payload.body, str)
        or not str(meta.payload.body).endswith(".json")
    ):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media", code=220, message="Request object is not available"
            ),
        )

    query_dict = db.load_resource_payload(
        space_name=space_name,
        subpath=record.subpath,
        filename=str(meta.payload.body),
        class_type=core.Content,
        branch_name=branch_name,
    )

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
    async with RedisServices() as redis_services:
        if url := await redis_services.get(f"short/{token}"):
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
    alteration_meta = await db.load(
        space_name=space_name,
        subpath=f"{on_entry.subpath}/{on_entry.shortname}",
        shortname=alteration_name,
        class_type=core.Alteration,
        user_shortname=logged_in_user,
        branch_name=on_entry.branch_name,
    )
    entry_meta: core.Meta = await db.load(
        space_name=space_name,
        subpath=f"{on_entry.subpath}",
        shortname=on_entry.shortname,
        class_type=getattr(
            sys.modules["models.core"], camel_case(on_entry.resource_type)
        ),
        user_shortname=logged_in_user,
        branch_name=on_entry.branch_name,
    )

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

    await db.delete(
        space_name=space_name,
        subpath=f"{on_entry.subpath}/{on_entry.shortname}",
        meta=alteration_meta,
        branch_name=on_entry.branch_name,
        user_shortname=logged_in_user,
    )
    return response
