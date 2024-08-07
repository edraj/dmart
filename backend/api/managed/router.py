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

from api.managed.utils import serve_request_create, serve_request_update_r_replace, serve_request_assign, \
    serve_request_update_acl, serve_request_delete, serve_request_move, \
    get_resource_content_type_from_payload_content_type, csv_entries_prepare_docs, handle_update_state, \
    update_state_handle_resolution, serve_space_delete, serve_space_update, serve_space_create, \
    data_asset_attachments_handler, import_resources_from_csv_handler, data_asset_handler, \
    create_or_update_resource_with_payload_handler
from utils.generate_email import generate_email_from_template, generate_subject
from utils.custom_validations import validate_csv_with_schema, validate_jsonl_with_schema, validate_uniqueness
from utils.internal_error_code import InternalErrorCode
from utils.router_helper import is_space_exist
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
    RequestType,
    ResourceType,
    LockAction,
    DataAssetType,
    TaskType,
)
import utils.regex as regex
import sys
import json
from utils.jwt import JWTBearer, GetJWTToken, remove_active_session
from utils.access_control import access_control
from utils.spaces import initialize_spaces
from typing import Any
import utils.repository as repository
from utils.helpers import (
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
from utils.redis_services import RedisServices
from fastapi.responses import RedirectResponse
from languages.loader import languages
from typing import Callable
from pathlib import Path as FilePath
from data_adapters.adapter import data_adapter as db

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
                type="media", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"
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

    response = StreamingResponse(
        iter([v_path.getvalue()]), media_type="text/csv")
    response.headers[
        "Content-Disposition"
    ] = f"attachment; filename={space_name}_{record.subpath}.csv"

    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
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
            subpath=query.subpath,
            action_type=core.ActionType.query,
            user_shortname=user_shortname,
            attributes={"filter_shortnames": query.filter_shortnames},
        )
    )

    folder = await db.load(
        query.space_name,
        '/',
        query.subpath,
        core.Folder,
        user_shortname,
    )

    folder_payload = await db.load_resource_payload(
        query.space_name,
        "/",
        f"{folder.shortname}.json",
        core.Folder,
    )
    folder_views = folder_payload.get("csv_columns", [])
    if not folder_views:
        folder_views = folder_payload.get("index_attributes", [])

    keys: list = [i["name"] for i in folder_views]
    keys_existence = dict(zip(keys, [False for _ in range(len(keys))]))

    # if settings.active_data_db == 'file':
    #     _, search_res = await db.query(query, user_shortname)
    # else:
    #     _, search_res = await db.query(query, user_shortname)
    #     docs_dicts = [search_re.model_dump() for search_re in search_res]

    _, search_res = await repository.serve_query(
        query, user_shortname,
    )

    docs_dicts = [search_re.model_dump() for search_re in search_res]

    json_data, deprecated_keys, new_keys = csv_entries_prepare_docs(query, docs_dicts, folder_views, keys_existence)

    await plugin_manager.after_action(
        core.Event(
            space_name=query.space_name,
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
    keys = list(filter(lambda item: item not in list_deprecated_keys, keys))
    writer = csv.DictWriter(v_path, fieldnames=(keys + list(new_keys)))
    writer.writeheader()
    writer.writerows(json_data)

    response = StreamingResponse(
        iter([v_path.getvalue()]), media_type="text/csv")
    response.headers[
        "Content-Disposition"
    ] = f"attachment; filename={query.space_name}_{query.subpath}.csv"

    return response


@router.post("/space", response_model=api.Response, response_model_exclude_none=True)
async def serve_space(
        request: api.Request, owner_shortname=Depends(JWTBearer())
) -> api.Response:
    record = request.records[0]
    history_diff = {}
    match request.request_type:
        case api.RequestType.create:
            await serve_space_create(request, record, owner_shortname)

        case api.RequestType.update:
            history_diff = await serve_space_update(request, record, owner_shortname)

        case api.RequestType.delete:
            await serve_space_delete(request, record, owner_shortname)

        case _:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.UNMATCHED_DATA,
                    message="mismatch with the information provided",
                ),
            )

    await initialize_spaces()

    await access_control.load_permissions_and_roles()

    await plugin_manager.after_action(
        core.Event(
            space_name=record.shortname,
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
    await is_space_exist(query.space_name)

    await plugin_manager.before_action(
        core.Event(
            space_name=query.space_name,
            subpath=query.subpath,
            action_type=core.ActionType.query,
            user_shortname=user_shortname,
            attributes={"filter_shortnames": query.filter_shortnames},
        )
    )

    total, records = await repository.serve_query(
        query, user_shortname,
    )

    await plugin_manager.after_action(
        core.Event(
            space_name=query.space_name,
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
    await is_space_exist(request.space_name)

    if not request.records:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.MISSING_DATA,
                message="Request records cannot be empty",
            ),
        )

    records = []
    failed_records = []
    match request.request_type:
        case api.RequestType.create:
            records, failed_records = await serve_request_create(request, owner_shortname, token, is_internal)

        case api.RequestType.update | api.RequestType.r_replace:
            records, failed_records = await serve_request_update_r_replace(request, owner_shortname)

        case api.RequestType.assign:
            records, failed_records = await serve_request_assign(request, owner_shortname)

        case api.RequestType.update_acl:
            records, failed_records = await serve_request_update_acl(request, owner_shortname)

        case api.RequestType.delete:
            records, failed_records = await serve_request_delete(request, owner_shortname)

        case api.RequestType.move:
            records, failed_records = await serve_request_move(request, owner_shortname)

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
        shortname: str = Path(..., pattern=regex.SHORTNAME,
                              examples=["unique_shortname"]),
        action: str = Path(..., examples=["approve"]),
        resolution: str | None = Body(None, embed=True, examples=[
            "Ticket state resolution"]),
        comment: str | None = Body(None, embed=True, examples=["Nice ticket"]),
        retrieve_lock_status: bool | None = False,
) -> api.Response:
    await is_space_exist(space_name)

    _user_roles = await access_control.get_user_roles(logged_in_user)
    user_roles = _user_roles.keys()

    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.progress_ticket,
            resource_type=ResourceType.ticket,
            user_shortname=logged_in_user,
        )
    )

    ticket_obj: core.Ticket = core.Ticket.model_validate(
        await db.load(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            class_type=core.Ticket,
            user_shortname=logged_in_user,
        )
    )
    if ticket_obj.payload is None or ticket_obj.payload.body is None:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"
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
            entry_shortname=shortname
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
        workflows_data = await db.load(
            space_name=space_name,
            subpath="workflows",
            shortname=ticket_obj.workflow_shortname,
            class_type=core.Content,
            user_shortname=logged_in_user,
        )

        if (
                workflows_data.payload is not None
                and workflows_data.payload.body is not None
        ):
            ticket_obj, workflows_payload, response, old_version_flattend = await handle_update_state(
                space_name, logged_in_user, ticket_obj, action, user_roles
            )
            if resolution:
                ticket_obj = await update_state_handle_resolution(ticket_obj, workflows_payload, response, resolution)

            new_version_flattend = flatten_dict(ticket_obj.model_dump())
            new_version_flattend.pop("payload.body", None)
            new_version_flattend.update(
                flatten_dict({"payload.body": ticket_obj}))

            if comment:
                time = datetime.now().strftime("%Y%m%d%H%M%S")
                new_version_flattend["comment"] = comment
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

            history_diff = await db.update(
                space_name,
                f"/{subpath}",
                ticket_obj,
                old_version_flattend,
                new_version_flattend,
                ["state", "resolution_reason", "comment"],

                logged_in_user,
                retrieve_lock_status=retrieve_lock_status,
            )
            await plugin_manager.after_action(
                core.Event(
                    space_name=space_name,
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
        error=api.Error(
            type="ticket",
            code=InternalErrorCode.WORKFLOW_BODY_NOT_FOUND,
            message="Workflow body not found"
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
        shortname: str = Path(..., pattern=regex.SHORTNAME,
                              examples=["unique_shortname"]),
        schema_shortname: str | None = None,
        ext: str = Path(..., pattern=regex.EXT, examples=["png"]),
        logged_in_user=Depends(JWTBearer()),
) -> FileResponse:
    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
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
                type="media", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"
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
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [9]",
            ),
        )

    payload_path = db.payload_path(
        space_name=space_name,
        subpath=subpath,
        class_type=cls,
        schema_shortname=schema_shortname,
    )
    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
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
        space_name: str = Form(..., examples=["data"]),
        sha: str | None = Form(None, examples=["data"]),
        owner_shortname: str = Depends(JWTBearer()),
):
    # NOTE We currently make no distinction between create and update.
    # in such case update should contain all the data every time.
    await is_space_exist(space_name)

    record = core.Record.model_validate_json(request_record.file.read())

    payload_filename = payload_file.filename or ""
    resource_content_type = get_resource_content_type_from_payload_content_type(
        payload_file, payload_filename, record
    )

    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
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
            entry_shortname=record.shortname,
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
    resource_obj, record = await create_or_update_resource_with_payload_handler(
            record, owner_shortname, space_name, payload_file, payload_filename, checksum, sha, resource_content_type
    )

    await db.save(space_name, record.subpath, resource_obj)
    await db.save_payload(
        space_name, record.subpath, resource_obj, payload_file
    )

    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
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
        space_name: str = Path(..., pattern=regex.SPACENAME, examples=["data"]),
        subpath: str = Path(..., pattern=regex.SUBPATH, examples=["/content"]),
        schema_shortname: str = Path(..., pattern=regex.SHORTNAME, examples=[
            "model_schema"]),
        owner_shortname=Depends(JWTBearer()),
):
    contents = await resources_file.read()
    decoded = contents.decode()
    buffer = StringIO(decoded)
    csv_reader = csv.DictReader(buffer)

    schema_path = (
            db.payload_path(space_name, "schema", core.Schema)
            / f"{schema_shortname}.json"
    )
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

    resource_cls = getattr(
        sys.modules["models.core"], camel_case(resource_type)
    )
    meta_class_attributes = resource_cls.model_fields
    failed_shortnames: list = []
    success_count = 0
    for row in csv_reader:
        payload_object, meta_object, shortname = await import_resources_from_csv_handler(
            row,
            meta_class_attributes,
            schema_content,
            data_types_mapper,
        )

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
        shortname: str = Path(..., pattern=regex.SHORTNAME,
                              examples=["unique_shortname"]),
        retrieve_json_payload: bool = False,
        retrieve_attachments: bool = False,
        filter_attachments_types: list = Query(default=[], examples=["media", "comment", "json"]),
        validate_schema: bool = True,
        logged_in_user=Depends(JWTBearer()),
) -> dict[str, Any]:
    if subpath == settings.root_subpath_mw:
        subpath = "/"

    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.view,
            resource_type=resource_type,
            user_shortname=logged_in_user,
        )
    )

    resource_class = getattr(
        sys.modules["models.core"], camel_case(resource_type)
    )
    meta: core.Meta = await db.load(
        space_name=space_name,
        subpath=subpath,
        shortname=shortname,
        class_type=resource_class,
        user_shortname=logged_in_user,
    )
    if meta is None:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"
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
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [11]",
            )
        )

    attachments = {}
    entry_path = (
            settings.spaces_folder
            / f"{space_name}/{subpath}/.dm/{shortname}"
    )
    if retrieve_attachments:
        attachments = await db.get_entry_attachments(
            subpath=subpath,
            attachments_path=entry_path,
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

    payload_body = await db.load_resource_payload(
        space_name=space_name,
        subpath=subpath,
        filename=meta.payload.body,
        class_type=resource_class,
    )

    if meta.payload and meta.payload.schema_shortname and validate_schema:
        await validate_payload_with_schema(
            payload_data=payload_body,
            space_name=space_name,
            schema_shortname=meta.payload.schema_shortname,
        )

    meta.payload.body = payload_body
    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
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
        retrieve_lock_status: bool = False,
        logged_in_user=Depends(JWTBearer()),
):
    return await repository.get_entry_by_var(
        "uuid",
        uuid,
        logged_in_user,
        retrieve_json_payload,
        retrieve_attachments,
        retrieve_lock_status,
    )


@router.get("/byslug/{slug}", response_model_exclude_none=True)
async def get_entry_by_slug(
        slug: str,
        retrieve_json_payload: bool = False,
        retrieve_attachments: bool = False,
        retrieve_lock_status: bool = False,
        logged_in_user=Depends(JWTBearer()),
):
    return await repository.get_entry_by_var(
        "slug",
        slug,
        logged_in_user,
        retrieve_json_payload,
        retrieve_attachments,
        retrieve_lock_status,
    )


@router.get("/health/{health_type}/{space_name}", response_model_exclude_none=True)
async def get_space_report(
        space_name: str = Path(..., pattern=regex.SPACENAME, examples=["data"]),
        health_type: str = Path(..., examples=["soft", "hard"]),
        logged_in_user=Depends(JWTBearer()),
):
    if logged_in_user != "dmart":
        raise api.Exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error=api.Error(
                type="access",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action"
            ),
        )

    await is_space_exist(space_name)

    if health_type not in ["soft", "hard"]:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media",
                code=InternalErrorCode.INVALID_HEALTH_CHECK,
                message="Invalid health check type"
            ),
        )

    os.system(
        f"./health_check.py -t {health_type} -s {space_name} &")
    return api.Response(
        status=api.Status.success,
    )


@router.put("/lock/{resource_type}/{space_name}/{subpath:path}/{shortname}")
async def lock_entry(
        space_name: str = Path(..., pattern=regex.SPACENAME),
        subpath: str = Path(..., pattern=regex.SUBPATH),
        shortname: str = Path(..., pattern=regex.SHORTNAME),
        resource_type: ResourceType | None = ResourceType.ticket,
        logged_in_user=Depends(JWTBearer()),
):
    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.lock,
            user_shortname=logged_in_user,
        )
    )

    if resource_type == ResourceType.ticket:
        cls = getattr(sys.modules["models.core"], camel_case(resource_type))

        mm = await db.load(
                space_name=space_name,
                subpath=subpath,
                shortname=shortname,
                class_type=cls,
                user_shortname=logged_in_user,
            )

        meta = core.Ticket.model_validate(
            mm.model_dump()
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

    lock_type = await db.lock_handler(
        space_name,
        subpath,
        shortname,
        logged_in_user,
        LockAction.lock
    )

    await db.store_entry_diff(
        space_name,
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
        logged_in_user=Depends(JWTBearer()),
):
    lock_payload = await db.lock_handler(space_name, subpath, shortname, logged_in_user, LockAction.fetch)

    if not lock_payload or lock_payload["owner_shortname"] != logged_in_user:
        raise api.Exception(
            status_code=status.HTTP_403_FORBIDDEN,
            error=api.Error(
                type="lock",
                code=InternalErrorCode.LOCK_UNAVAILABLE,
                message="Lock does not exist or you have no access",
            ),
        )

    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.unlock,
            user_shortname=logged_in_user,
        )
    )

    await db.lock_handler(
        space_name,
        subpath,
        shortname,
        logged_in_user,
        LockAction.unlock
    )

    await db.store_entry_diff(
        space_name,
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
    if settings.active_data_db == "file":
        await access_control.load_permissions_and_roles()

    return api.Response(status=api.Status.success)


@router.post("/excute/{task_type}/{space_name}")
async def execute(
        space_name: str,
        task_type: TaskType,
        record: core.Record,
        logged_in_user=Depends(JWTBearer()),
):
    task_type = task_type
    meta = await db.load(
        space_name=space_name,
        subpath=record.subpath,
        shortname=record.shortname,
        class_type=core.Content,
        user_shortname=logged_in_user,
    )

    if (
            meta.payload is None
            or not isinstance(meta.payload.body, str)
            or not str(meta.payload.body).endswith(".json")
    ):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"
            ),
        )

    query_dict: dict[str, Any] = await db.load_resource_payload(
        space_name=space_name,
        subpath=record.subpath,
        filename=str(meta.payload.body),
        class_type=core.Content,
    )

    if meta.payload.schema_shortname == "report":
        query_dict = query_dict["query"]
    else:
        query_dict["subpath"] = query_dict["query_subpath"]
        query_dict.pop("query_subpath")

    for param, value in record.attributes.items():
        query_dict["search"] = query_dict["search"].replace(
            f"${param}", str(value))

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
    if settings.active_data_db == "file":
        async with RedisServices() as redis_services:
            if url := await redis_services.get_key(f"short/{token}"):
                return RedirectResponse(url=url)
            else:
                return RedirectResponse(url="/frontend")
    else:
        if url := await db.get_url_shortner(token):
            return RedirectResponse(url=url)
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
    alteration_meta = core.Alteration.model_validate(
        await db.load(
            space_name=space_name,
            subpath=f"{on_entry.subpath}/{on_entry.shortname}",
            shortname=alteration_name,
            class_type=core.Alteration,
            user_shortname=logged_in_user,
        )
    )
    entry_meta: core.Meta = await db.load(
        space_name=space_name,
        subpath=f"{on_entry.subpath}",
        shortname=on_entry.shortname,
        class_type=getattr(
            sys.modules["models.core"], camel_case(on_entry.resource_type)
        ),
        user_shortname=logged_in_user,
    )

    record: core.Record = entry_meta.to_record(
        on_entry.subpath, on_entry.shortname, []
    )
    record.attributes["payload"] = record.attributes["payload"].__dict__
    record.attributes["payload"]["body"] = alteration_meta.requested_update

    response = await serve_request(
        request=api.Request(
            space_name=space_name, request_type=RequestType.update, records=[
                record]
        ),
        owner_shortname=logged_in_user,
    )

    await db.delete(
        space_name=space_name,
        subpath=f"{on_entry.subpath}/{on_entry.shortname}",
        meta=alteration_meta,
        user_shortname=logged_in_user,
        retrieve_lock_status=on_entry.retrieve_lock_status,
    )
    return response


@router.post("/data-asset")
async def data_asset(
        query: api.DataAssetQuery,
        _=Depends(JWTBearer()),
):
    try:
        duckdb = __import__("duckdb")  # type: ignore
    except ModuleNotFoundError:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="duckdb is not installed!",
            ),
        )

    attachments: dict[str, list[core.Record]] = await db.get_entry_attachments(
        subpath=f"{query.subpath}/{query.shortname}",
        attachments_path=(
                settings.spaces_folder
                / f"{query.space_name}/{query.subpath}/.dm/{query.shortname}"
        ),
        filter_types=[query.data_asset_type],
        filter_shortnames=query.filter_data_assets
    )
    files_paths: list[FilePath] = await data_asset_attachments_handler(query, attachments)
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
        conn: duckdb.DuckDBPyConnection = duckdb.connect(str(files_paths[0]))  # type: ignore
    else:
        conn = duckdb.connect(":default:")
        await data_asset_handler(conn, query, files_paths, attachments)

    data: duckdb.DuckDBPyRelation = conn.sql(query=query.query_string)  # type: ignore

    temp_file = f"temp_file_from_duckdb_{int(round(time() * 1000))}.csv"
    data.write_csv(file_name=temp_file)
    data_objects: list[dict[str, Any]] = await csv_file_to_json(FilePath(temp_file))
    os.remove(temp_file)

    return data_objects


@router.get("/data-asset")
async def data_asset_single(
        resource_type: ResourceType,
        space_name: str = Path(..., pattern=regex.SPACENAME, examples=["data"]),
        subpath: str = Path(..., pattern=regex.SUBPATH, examples=["/content"]),
        shortname: str = Path(..., pattern=regex.SHORTNAME,
                              examples=["unique_shortname"]),
        schema_shortname: str | None = None,
        ext: str = Path(..., pattern=regex.EXT, examples=["png"]),
        logged_in_user=Depends(JWTBearer()),
) -> StreamingResponse:
    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
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
                type="media", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"
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
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [9]",
            ),
        )

    payload_path = db.payload_path(
        space_name=space_name,
        subpath=subpath,
        class_type=cls,
        schema_shortname=schema_shortname,
    )
    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.view,
            resource_type=resource_type,
            user_shortname=logged_in_user,
        )
    )

    with open(payload_path / str(meta.payload.body), "r") as csv_file:
        media = "text/csv" if resource_type == ResourceType.csv else "text/plain"
        response = StreamingResponse(iter(csv_file.read()), media_type=media)
        response.headers["Content-Disposition"] = "attachment; filename=data.csv"

    return response
