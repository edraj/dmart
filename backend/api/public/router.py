from re import sub as res_sub
from uuid import uuid4
from fastapi import APIRouter, Body, Query, Path, status, Depends
from models.enums import AttachmentType, ContentType, ResourceType, TaskType
from utils.data_database import data_adapter as db
import models.api as api
from utils.helpers import branch_path
from utils.custom_validations import validate_payload_with_schema
from utils.internal_error_code import InternalErrorCode
import utils.regex as regex
import models.core as core
from fastapi.responses import FileResponse
from typing import Any
from utils.access_control import access_control
from utils.plugin_manager import plugin_manager
from utils.settings import settings
from utils.operational_repository import operational_repo

router = APIRouter()

# Retrieve publically-available content


@router.post("/query", response_model=api.Response, response_model_exclude_none=True)
async def query_entries(query: api.Query) -> api.Response:

    await plugin_manager.before_action(
        core.Event(
            space_name=query.space_name,
            branch_name=query.branch_name,
            subpath=query.subpath,
            action_type=core.ActionType.query,
            user_shortname="anonymous",
            attributes={"filter_shortnames": query.filter_shortnames},
        )
    )

    total, records = await operational_repo.query_handler(query, "anonymous")

    await plugin_manager.after_action(
        core.Event(
            space_name=query.space_name,
            branch_name=query.branch_name,
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
    filter_attachments_types: list = Query(
        default=[], examples=["media", "comment", "json"]
    ),
    branch_name: str | None = settings.default_branch,
) -> dict[str, Any]:

    if subpath == settings.root_subpath_mw:
        subpath = "/"

    dto = core.EntityDTO(
        space_name=space_name,
        branch_name=branch_name,
        subpath=subpath,
        shortname=shortname,
        resource_type=resource_type,
        user_shortname="anonymous",
    )
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
                message="You don't have permission to this action [14]",
            ),
        )

    await plugin_manager.before_action(dto.to_event_data(core.ActionType.view))

    attachments = {}
    entry_path = (
        settings.spaces_folder
        / f"{space_name}/{branch_path(branch_name)}/{subpath}/.dm/{shortname}"
    )
    if retrieve_attachments:
        attachments = await db.get_entry_attachments(
            subpath=subpath,
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
        return {**meta.dict(exclude_none=True), "attachments": attachments}

    payload_body = await db.load_resource_payload(dto)

    if meta.payload and meta.payload.schema_shortname:
        await validate_payload_with_schema(
            payload_data=payload_body,
            space_name=space_name,
            branch_name=branch_name or settings.default_branch,
            schema_shortname=meta.payload.schema_shortname,
        )

    meta.payload.body = payload_body
    await plugin_manager.after_action(dto.to_event_data(core.ActionType.view))

    return {**meta.dict(exclude_none=True), "attachments": attachments}


# Public payload retrieval; can be used in "src=" in html pages
@router.get(
    "/payload/{resource_type}/{space_name}/{subpath:path}/{shortname}.{ext}",
    response_model_exclude_none=True,
)
async def retrieve_entry_or_attachment_payload(
    resource_type: ResourceType,
    space_name: str = Path(..., pattern=regex.SPACENAME),
    subpath: str = Path(..., pattern=regex.SUBPATH),
    shortname: str = Path(..., pattern=regex.SHORTNAME),
    ext: str = Path(..., pattern=regex.EXT),
    branch_name: str | None = settings.default_branch,
) -> FileResponse:
    
    dto = core.EntityDTO(
        space_name=space_name,
        branch_name=branch_name,
        subpath=subpath,
        shortname=shortname,
        resource_type=resource_type,
        user_shortname="anonymous",
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
                message="You don't have permission to this action [15]",
            ),
        )
        
    await plugin_manager.before_action(dto.to_event_data(core.ActionType.view))
    
    # TODO check security labels for public access
    # assert meta.is_active
    payload_path = db.payload_path(dto)

    await plugin_manager.after_action(dto.to_event_data(core.ActionType.view))

    media_file = payload_path / str(meta.payload.body)
    return FileResponse(media_file)


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
            branch_name=query.branch_name,
            subpath=query.subpath,
            action_type=core.ActionType.query,
            user_shortname="anonymous",
            attributes={"filter_shortnames": query.filter_shortnames},
        )
    )
    total, records = await operational_repo.query_handler(
        query, "anonymous"
    )

    await plugin_manager.after_action(
        core.Event(
            space_name=query.space_name,
            branch_name=query.branch_name,
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


@router.post("/submit/{space_name}/{schema_shortname}/{subpath:path}")
async def create_entry(
    space_name: str = Path(...),
    schema_shortname: str = Path(...),
    subpath: str = Path(..., regex=regex.SUBPATH),
    body_dict: dict[str, Any] = Body(...),
    branch_name: str | None = settings.default_branch,
):
    allowed_models = {
        "applications": ["log", "feedback", "cancellation_survey"]
    }
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

    uuid = uuid4()
    shortname = str(uuid)[:8]
    dto = core.EntityDTO(
        space_name=space_name,
        subpath=subpath,
        user_shortname="anonymous",
        resource_type=ResourceType.content,
        schema_shortname=schema_shortname,
        shortname=shortname
    )
    if not await access_control.check_access(
        dto=dto,
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

    
    await plugin_manager.before_action(dto.to_event_data(core.ActionType.create))

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

    if content_obj.payload and content_obj.payload.schema_shortname:
        await validate_payload_with_schema(
            payload_data=body_dict,
            space_name=space_name,
            branch_name=branch_name or settings.default_branch,
            schema_shortname=content_obj.payload.schema_shortname,
        )

    await db.save(dto, content_obj, body_dict)
    
    await plugin_manager.after_action(dto.to_event_data(core.ActionType.create))

    return api.Response(status=api.Status.success)


@router.post("/attach/{space_name}")
async def create_attachment(
    space_name: str,
    record: core.Record,
    branch_name: str | None = settings.default_branch,
):
    if record.resource_type not in AttachmentType.__members__:
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [14]",
            ),
        )
        
    dto = core.EntityDTO.from_record(record, space_name, "anonymous")

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
                message="You don't have permission to this action [15]",
            ),
        )

    await plugin_manager.before_action(dto.to_event_data(core.ActionType.create))

    attachment_obj = dto.class_type.from_record(record=record, owner_shortname="anonymous")
    if record.shortname != settings.auto_uuid_rule:
        dto.shortname = attachment_obj.shortname

    await db.save(dto, attachment_obj)

    await plugin_manager.after_action(dto.to_event_data(core.ActionType.create))

    return api.Response(status=api.Status.success)


@router.post("/excute/{task_type}/{space_name}")
async def excute(space_name: str, task_type: TaskType, record: core.Record):
    
    dto = core.EntityDTO.from_record(record, space_name, "anonymous")
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

    for param, value in record.attributes.items():
        query_dict["search"] = query_dict["search"].replace(f"${param}", str(value))

    query_dict["search"] = res_sub(
        r"@\w*\:({|\()?\$\w*(}|\))?", "", query_dict["search"]
    )

    if "offset" in record.attributes:
        query_dict["offset"] = record.attributes["offset"]

    if "limit" in record.attributes:
        query_dict["limit"] = record.attributes["limit"]

    query_dict["subpath"] = query_dict["query_subpath"]
    query_dict.pop("query_subpath")
    filter_shortnames = record.attributes.get("filter_shortnames", [])
    query_dict["filter_shortnames"] = (
        filter_shortnames if isinstance(filter_shortnames, list) else []
    )

    return await query_entries(api.Query(**query_dict))


@router.get("/byuuid/{uuid}", response_model_exclude_none=True)
async def get_entry_by_uuid(
    uuid: str, retrieve_json_payload: bool = False, retrieve_attachments: bool = False
):
    return await operational_repo.get_entry_by_var(
        "uuid",
        uuid,
        "anonymous",
        retrieve_json_payload,
        retrieve_attachments,
    )


@router.get("/byslug/{slug}", response_model_exclude_none=True)
async def get_entry_by_slug(
    slug: str, retrieve_json_payload: bool = False, retrieve_attachments: bool = False
):
    return await operational_repo.get_entry_by_var(
        "slug",
        slug,
        "anonymous",
        retrieve_json_payload,
        retrieve_attachments,
    )
