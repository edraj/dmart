import hashlib
from re import sub as res_sub
from uuid import uuid4
from fastapi import APIRouter, Body, Depends, Form, Path, Query, UploadFile, status
from models.enums import AttachmentType, ContentType, ResourceType, TaskType, PublicSubmitResourceType
from data_adapters.adapter import data_adapter as db
import models.api as api
from utils.helpers import camel_case
from utils.internal_error_code import InternalErrorCode
import utils.regex as regex
import models.core as core
from api.managed.utils import get_mime_type, get_resource_content_type_from_payload_content_type, \
    create_or_update_resource_with_payload_handler, iter_bytesio
from typing import Any, Union, Optional
import sys
import re
import os
from utils.access_control import access_control
import utils.repository as repository
from utils.plugin_manager import plugin_manager
from utils.router_helper import is_space_exist
from utils.settings import settings
from starlette.responses import FileResponse, StreamingResponse

from utils.ticket_sys_utils import set_init_state_for_record
from fastapi.responses import ORJSONResponse

router = APIRouter(default_response_class=ORJSONResponse)

# Retrieve publically-available content


@router.post("/query", response_model=api.Response, response_model_exclude_none=True)
async def query_entries(query: api.Query) -> api.Response:
    await plugin_manager.before_action(
        core.Event(
            space_name=query.space_name,
            subpath=query.subpath,
            action_type=core.ActionType.query,
            user_shortname="anonymous",
            attributes={"filter_shortnames": query.filter_shortnames},
        )
    )

    total, records = await repository.serve_query(
        query, "anonymous"
    )

    await plugin_manager.after_action(
        core.Event(
            space_name=query.space_name,
            subpath=query.subpath,
            action_type=core.ActionType.query,
            user_shortname="anonymous",
            attributes={"filter_shortnames": query.filter_shortnames},
        )
    )

    return api.Response(
        status=api.Status.success,
        records=records,
        attributes={"total": total, "returned": len(records)},
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
    filter_attachments_types: list = Query(default=[], examples=["media", "comment", "json"]),
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
            user_shortname="anonymous",
        )
    )

    resource_class = getattr(
        sys.modules["models.core"], camel_case(resource_type))
    meta = await db.load(
        space_name=space_name,
        subpath=subpath,
        shortname=shortname,
        class_type=resource_class,
        user_shortname="anonymous",
    )
    if meta is None:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="media", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not found"
            ),
        )

    if not await access_control.check_access(
            user_shortname="anonymous",
            space_name=space_name,
            subpath=subpath,
            resource_type=resource_type,
            action_type=core.ActionType.view,
            resource_is_active=meta.is_active,
            resource_owner_shortname=meta.owner_shortname,
            resource_owner_group=meta.owner_group_shortname,
            entry_shortname=meta.shortname,
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [14]",
            ),
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
            filter_types=filter_attachments_types
        )

    if (not retrieve_json_payload or
            not meta.payload or
            not meta.payload.body or
            not isinstance(meta.payload.body, str) or
            meta.payload.content_type != ContentType.json
    ):
        # TODO
        # include locked before returning the dictionary
        return {
            **meta.dict(exclude_none=True),
            "attachments": attachments
        }

    payload_body = await db.load_resource_payload(
        space_name=space_name,
        subpath=subpath,
        filename=meta.payload.body,
        class_type=resource_class,
    )

    if meta.payload and meta.payload.schema_shortname and payload_body:
        await db.validate_payload_with_schema(
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
            user_shortname="anonymous",
        )
    )

    return {
        **meta.dict(exclude_none=True),
        "attachments": attachments
    }


# Public payload retrieval; can be used in "src=" in html pages
@router.get(
    "/payload/{resource_type}/{space_name}/{subpath:path}/{shortname}.{ext}",
    response_model=None
)
async def retrieve_entry_or_attachment_payload(
    resource_type: ResourceType,
    space_name: str = Path(..., pattern=regex.SPACENAME),
    subpath: str = Path(..., pattern=regex.SUBPATH),
    shortname: str = Path(..., pattern=regex.SHORTNAME),
    ext: str = Path(..., pattern=regex.EXT),
) -> FileResponse | api.Response | StreamingResponse:
    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.view,
            resource_type=resource_type,
            user_shortname="anonymous",
        )
    )
    cls = getattr(sys.modules["models.core"], camel_case(resource_type))
    meta = await db.load(
        space_name=space_name,
        subpath=subpath,
        shortname=shortname,
        class_type=cls,
        user_shortname="anonymous",
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
            user_shortname="anonymous",
            space_name=space_name,
            subpath=subpath,
            resource_type=resource_type,
            action_type=core.ActionType.view,
            resource_is_active=meta.is_active,
            resource_owner_shortname=meta.owner_shortname,
            resource_owner_group=meta.owner_group_shortname,
            entry_shortname=meta.shortname,
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [15]",
            ),
        )

    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.view,
            resource_type=resource_type,
            user_shortname="anonymous",
        )
    )

    if settings.active_data_db == "file":
        payload_path = db.payload_path(
            space_name=space_name,
            subpath=subpath,
            class_type=cls,
        )
        return FileResponse(payload_path / str(meta.payload.body))

    if meta.payload.content_type == ContentType.json and isinstance(meta.payload.body, dict):
        return api.Response(
            status=api.Status.success,
            attributes=meta.payload.body
        )

    data = await db.get_media_attachment(space_name, subpath, shortname)
    if data:
        return StreamingResponse(iter_bytesio(data), media_type=get_mime_type(meta.payload.content_type))

    return api.Response(status=api.Status.failed)


"""
@router.post("/submit", response_model_exclude_none=True)
async def submit() -> api.Response:
    return api.Response(status=api.Status.success)
"""


@router.get(
    "/query/{type}/{space_name}/{subpath:path}",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def query_via_urlparams(
        query: api.Query = Depends(api.Query),
) -> api.Response:
    await plugin_manager.before_action(
        core.Event(
            space_name=query.space_name,
            subpath=query.subpath,
            action_type=core.ActionType.query,
            user_shortname="anonymous",
            attributes={"filter_shortnames": query.filter_shortnames},
        )
    )

    total, records = await repository.serve_query(
        query, "anonymous"
    )

    await plugin_manager.after_action(
        core.Event(
            space_name=query.space_name,
            subpath=query.subpath,
            action_type=core.ActionType.query,
            user_shortname="anonymous",
            attributes={"filter_shortnames": query.filter_shortnames},
        )
    )

    return api.Response(
        status=api.Status.success,
        records=records,
        attributes={"total": total, "returned": len(records)},
    )


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
):
    # NOTE We currently make no distinction between create and update.
    # in such case update should contain all the data every time.
    await is_space_exist(space_name)

    record = core.Record.model_validate_json(request_record.file.read())

    payload_filename = payload_file.filename or ""
    if payload_filename and not re.search(regex.EXT, os.path.splitext(payload_filename)[1][1:]):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.INVALID_DATA,
                message=f"Invalid payload file extention, it should end with {regex.EXT}",
            ),
        )
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
            user_shortname="anonymous",
        )
    )

    if not await access_control.check_access(
        user_shortname="anonymous",
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
                message="You don't have permission to this action [50]",
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
        record, "anonymous", space_name, payload_file, payload_filename, checksum, sha, resource_content_type
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
            user_shortname="anonymous",
        )
    )

    return api.Response(
        status=api.Status.success,
        records=[record],
    )


@router.post("/submit/{space_name}/{schema_shortname}/{subpath:path}")
@router.post("/submit/{space_name}/{resource_type}/{schema_shortname}/{subpath:path}")
@router.post("/submit/{space_name}/{resource_type}/{workflow_shortname}/{schema_shortname}/{subpath:path}")
async def create_entry(
    space_name: str = Path(...),
    schema_shortname: str = Path(...),
    subpath: str = Path(..., pattern=regex.SUBPATH),
    resource_type: PublicSubmitResourceType | None = None,
    workflow_shortname: str | None = None,
    body_dict: dict[str, Any] = Body(...),
):
    allowed_models = settings.allowed_submit_models
    entry_resource_type: ResourceType = ResourceType(resource_type.name) if resource_type else ResourceType.content
    if (
            space_name not in allowed_models
            or schema_shortname not in allowed_models[space_name]
    ):
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED_LOCATION,
                message="Selected location is not allowed",
            ),
        )

    if not await access_control.check_access(
        user_shortname="anonymous",
        space_name=space_name,
        subpath=subpath,
        resource_type=entry_resource_type,
        action_type=core.ActionType.create,
        record_attributes=body_dict,
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [13]",
            ),
        )

    uuid = uuid4()
    shortname = str(uuid)[:8]
    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.create,
            schema_shortname=schema_shortname,
            resource_type=entry_resource_type,
            user_shortname="anonymous",
        )
    )

    content_obj: Optional[Union[core.Content, core.Ticket]] = None
    if entry_resource_type == ResourceType.ticket:
        if workflow_shortname is None:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_DATA,
                    message="Workflow shortname is required for ticket creation",
                ),
            )

        record = core.Record(
            subpath=subpath,
            shortname=shortname,
            resource_type=entry_resource_type,
            attributes={
                "workflow_shortname": workflow_shortname,
                **body_dict
            }
        )
        record = await set_init_state_for_record(record, space_name, "anonymous")
        if not record or not record.attributes.get("state"):
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_DATA,
                    message="Failed to set initial state",
                ),
            )
        content_obj = core.Ticket(
            uuid=uuid,
            shortname=shortname,
            is_active=True,
            owner_shortname="anonymous",
            payload=core.Payload(
                content_type=ContentType.json,
                schema_shortname=schema_shortname,
                body=f"{shortname}.json",
            ),
            state=record.attributes["state"],
            workflow_shortname=workflow_shortname,
            is_open=record.attributes["is_open"]
        )
    elif entry_resource_type == ResourceType.content:
        content_obj = core.Content(
            uuid=uuid,
            shortname=shortname,
            is_active=True,
            owner_shortname="anonymous",
            payload=core.Payload(
                content_type=ContentType.json,
                schema_shortname=schema_shortname,
                body=f"{shortname}.json",
            ),
        )

    if content_obj is None:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.INVALID_DATA,
                message="Invalid resource type for entry creation",
            ),
        )

    if content_obj.payload and content_obj.payload.schema_shortname:
        await db.validate_payload_with_schema(
            payload_data=body_dict,
            space_name=space_name,
            schema_shortname=content_obj.payload.schema_shortname,
        )

    response_data = await db.save(space_name, subpath, content_obj)
    if response_data is None:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.SOMETHING_WRONG,
                message="Something went wrong while saving the entry",
            ),
        )
    await db.save_payload_from_json(
        space_name, subpath, content_obj, body_dict
    )

    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
            subpath=subpath,
            shortname=shortname,
            action_type=core.ActionType.create,
            schema_shortname=schema_shortname,
            resource_type=entry_resource_type,
            user_shortname="anonymous",
            attributes={}
        )
    )
    response_data = response_data.model_dump(exclude_none=True, by_alias=True)
    del response_data["query_policies"]
    return api.Response(
        status=api.Status.success,
        records=[response_data],
    )


@router.post("/attach/{space_name}")
async def create_attachment(
    space_name: str,
    record: core.Record
):
    if record.resource_type not in AttachmentType.__members__:
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [54]",
            ),
        )

    if not await access_control.check_access(
        user_shortname="anonymous",
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
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [55]",
            ),
        )

    await plugin_manager.before_action(
        core.Event(
            space_name=space_name,
            subpath=record.subpath,
            action_type=core.ActionType.create,
            resource_type=record.resource_type,
            user_shortname="anonymous",
        )
    )

    record.shortname = 'auto'
    attachment_obj = core.Meta.from_record(
        record=record, owner_shortname="anonymous"
    )

    await db.save(space_name, record.subpath, attachment_obj)

    await plugin_manager.after_action(
        core.Event(
            space_name=space_name,
            subpath=record.subpath,
            shortname=attachment_obj.shortname,
            action_type=core.ActionType.create,
            resource_type=record.resource_type,
            user_shortname="anonymous",
            attributes={}
        )
    )

    return api.Response(status=api.Status.success)


@router.post("/excute/{task_type}/{space_name}")
async def excute(space_name: str, task_type: TaskType, record: core.Record):
    task_type = task_type
    meta = await db.load(
        space_name=space_name,
        subpath=record.subpath,
        shortname=record.shortname,
        class_type=core.Content,
        user_shortname="anonymous"
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

    mydict = await db.load_resource_payload(
        space_name=space_name,
        subpath=record.subpath,
        filename=str(meta.payload.body),
        class_type=core.Content,
    )
    query_dict = mydict if mydict else {}

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

    filter_shortnames = record.attributes.get("filter_shortnames", [])
    query_dict["filter_shortnames"] = filter_shortnames if isinstance(
        filter_shortnames, list) else []

    return await query_entries(api.Query(**query_dict))


@router.get("/byuuid/{uuid}", response_model_exclude_none=True)
async def get_entry_by_uuid(
    uuid: str,
    retrieve_json_payload: bool = False,
    retrieve_attachments: bool = False,
    retrieve_lock_status: bool = False
):
    return await db.get_entry_by_var(
        "uuid",
        uuid,
        "anonymous",
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
):
    return await db.get_entry_by_var(
        "slug",
        slug,
        "anonymous",
        retrieve_json_payload,
        retrieve_attachments,
        retrieve_lock_status,
    )
