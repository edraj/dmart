from copy import copy
from datetime import datetime
from typing import Any

from fastapi import status
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
    DataAssetType,
)
import sys
import json
from utils.jwt import remove_active_session
from utils.access_control import access_control
import utils.repository as repository
from utils.helpers import (
    camel_case,
    flatten_dict,
)
from utils.custom_validations import validate_payload_with_schema
from utils.settings import settings
from utils.plugin_manager import plugin_manager
from api.user.service import (
    send_email,
    send_sms,
)
from utils.redis_services import RedisServices
from languages.loader import languages
from data_adapters.adapter import data_adapter as db


def csv_entries_prepare_docs(query, docs_dicts, folder_views, keys_existence):
    json_data = []
    timestamp_fields = ["created_at", "updated_at"]
    new_keys = set()
    deprecated_keys = set()

    for redis_document in docs_dicts:
        rows: list[dict] = [{}]
        flattened_doc = flatten_dict(redis_document)
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
                list_new_rows = []
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
                new_col = attribute_val if column_key not in timestamp_fields else \
                    datetime.fromtimestamp(attribute_val).strftime(
                        '%Y-%m-%d %H:%M:%S')
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

    return json_data, deprecated_keys, new_keys


async def serve_request_create_check_access(request, record, owner_shortname):
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
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [4]",
            ),
        )


async def send_sms_email_invitation(resource_obj, record):
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


def set_resource_object(record, resource_obj, is_internal):
    if not is_internal or "created_at" not in record.attributes:
        resource_obj.created_at = datetime.now()
        resource_obj.updated_at = datetime.now()
    body_shortname = record.shortname

    separate_payload_data = None
    if (
        resource_obj.payload
        and resource_obj.payload.content_type == ContentType.json
        and resource_obj.payload.body is not None
    ):
        separate_payload_data = resource_obj.payload.body
        if settings.active_data_db == 'file':
            resource_obj.payload.body = body_shortname + (
                ".json" if record.resource_type != ResourceType.log else ".jsonl"
            )
    return separate_payload_data, resource_obj


async def serve_request_create(request: api.Request, owner_shortname: str, token: str, is_internal: bool = False):
    failed_records = []
    records = []
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
                    subpath=record.subpath,
                    shortname=record.shortname,
                    action_type=core.ActionType.create,
                    schema_shortname=schema_shortname,
                    resource_type=record.resource_type,
                    user_shortname=owner_shortname,
                )
            )

            await serve_request_create_check_access(
                request, record, owner_shortname
            )

            if record.resource_type == ResourceType.ticket:
                record = await set_init_state_from_request(
                    request, owner_shortname
                )

            shortname_exists = db.is_entry_exist(
                space_name=request.space_name,
                subpath=record.subpath,
                shortname=record.shortname,
                resource_type=record.resource_type,
                schema_shortname=record.attributes.get(
                    "schema_shortname", None)
            )

            if record.shortname != settings.auto_uuid_rule and shortname_exists:
                raise api.Exception(
                    status.HTTP_400_BAD_REQUEST,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
                        message=f"This shortname {record.shortname} already exists",
                    ),
                )

            await validate_uniqueness(request.space_name, record)

            resource_obj = core.Meta.from_record(
                record=record, owner_shortname=owner_shortname
            )

            separate_payload_data, resource_obj = set_resource_object(record, resource_obj, is_internal)

            if (
                resource_obj.payload
                and resource_obj.payload.content_type == ContentType.json
                and resource_obj.payload.schema_shortname
                and isinstance(separate_payload_data, dict)
            ):
                await validate_payload_with_schema(
                    payload_data=separate_payload_data,
                    space_name=request.space_name,
                    schema_shortname=resource_obj.payload.schema_shortname,
                )

            await db.save(
                request.space_name,
                record.subpath,
                resource_obj,
            )

            if isinstance(resource_obj, core.User):
                await send_sms_email_invitation(resource_obj, record)

            if separate_payload_data is not None and isinstance(
                    separate_payload_data, dict
            ):
                await db.update_payload(
                    request.space_name, record.subpath, resource_obj, separate_payload_data, owner_shortname
                )

            records.append(
                resource_obj.to_record(
                    record.subpath,
                    resource_obj.shortname,
                    [],
                )
            )
            record.attributes["logged_in_user_token"] = token
            await plugin_manager.after_action(
                core.Event(
                    space_name=request.space_name,
                    subpath=record.subpath,
                    shortname=resource_obj.shortname,
                    action_type=core.ActionType.create,
                    schema_shortname=record.attributes["payload"].get(
                        "schema_shortname", None
                    )
                    if record.attributes.get("payload")
                    else None,
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

    return records, failed_records


async def serve_request_update_r_replace_fetch_payload(
    old_resource_obj, record, request, resource_cls, schema_shortname
):
    old_resource_payload_body : dict[str, Any] = {}
    old_version_flattend = flatten_dict(
        old_resource_obj.model_dump()
    )
    if (
            record.resource_type != ResourceType.log
            and old_resource_obj.payload
            and old_resource_obj.payload.content_type == ContentType.json
            and isinstance(old_resource_obj.payload.body, str)
    ):
        try:
            mybody = await db.load_resource_payload(
                space_name=request.space_name,
                subpath=record.subpath,
                filename=old_resource_obj.payload.body,
                class_type=resource_cls,
                schema_shortname=schema_shortname,
            )
            old_resource_payload_body = mybody if mybody else {}
        except api.Exception as e:
            if request.request_type == api.RequestType.update:
                raise e

        old_version_flattend.pop("payload.body", None)
        old_version_flattend.update(
            flatten_dict(
                {"payload.body": old_resource_payload_body}
            )
        )

    return old_version_flattend, old_resource_payload_body


async def serve_request_update_r_replace(request, owner_shortname: str):
    records: list[core.Record] = []
    failed_records: list[dict] = []

    for record in request.records:
        try:
            if record.subpath[0] != "/":
                record.subpath = f"/{record.subpath}"

            await plugin_manager.before_action(
                core.Event(
                    space_name=request.space_name,
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
                sys.modules["models.core"], camel_case(
                    record.resource_type
                )
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
                    entry_shortname=record.shortname
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.NOT_ALLOWED,
                        message="You don't have permission to this action [5]",
                    ),
                )

            # GET PAYLOAD DATA
            old_version_flattend, old_resource_payload_body = await serve_request_update_r_replace_fetch_payload(
                old_resource_obj, record, request, resource_cls, schema_shortname
            )

            # GENERATE NEW RESOURCE OBJECT
            resource_obj = old_resource_obj
            resource_obj.updated_at = datetime.now()

            new_version_flattend = {}

            if record.resource_type == ResourceType.log:
                new_resource_payload_data = record.attributes.get("payload", {}).get(
                    "body", {}
                )
            else:
                new_resource_payload_data = (
                    resource_obj.update_from_record(
                        record=record,
                        old_body=old_resource_payload_body,
                        replace=request.request_type == api.RequestType.r_replace,
                    )
                )
                new_version_flattend = resource_obj.model_dump()
                if new_resource_payload_data:
                    new_version_flattend["payload"] = {
                        **new_version_flattend["payload"],
                        "body": new_resource_payload_data
                    }
                new_version_flattend = flatten_dict(new_version_flattend)

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
                    schema_shortname=resource_obj.payload.schema_shortname,
                )

            if record.resource_type == ResourceType.log:
                history_diff = await db.update(
                    space_name=request.space_name,
                    subpath=record.subpath,
                    meta=resource_obj,
                    old_version_flattend={},
                    new_version_flattend={},
                    updated_attributes_flattend=[],
                    user_shortname=owner_shortname,
                    schema_shortname=schema_shortname,
                    retrieve_lock_status=record.retrieve_lock_status,
                )
            else:
                updated_attributes_flattend = list(
                    flatten_dict(record.attributes).keys()
                )
                if request.request_type == RequestType.r_replace:
                    updated_attributes_flattend = (
                            list(old_version_flattend.keys()) +
                            list(new_version_flattend.keys())
                    )

                if (settings.active_data_db == 'sql'
                        and resource_obj.payload
                        and resource_obj.payload.content_type == ContentType.json):
                    resource_obj.payload.body = new_resource_payload_data

                history_diff = await db.update(
                    space_name=request.space_name,
                    subpath=record.subpath,
                    meta=resource_obj,
                    old_version_flattend=old_version_flattend,
                    new_version_flattend=new_version_flattend,
                    updated_attributes_flattend=updated_attributes_flattend,
                    user_shortname=owner_shortname,
                    schema_shortname=schema_shortname,
                    retrieve_lock_status=record.retrieve_lock_status,
                )

            if new_resource_payload_data is not None:
                await db.save_payload_from_json(
                    request.space_name,
                    record.subpath,
                    resource_obj,
                    new_resource_payload_data,
                )

            if (
                    isinstance(resource_obj, core.User) and
                    record.attributes.get("is_active") is False
            ):
                await remove_active_session(record.shortname)

            records.append(
                resource_obj.to_record(
                    record.subpath, resource_obj.shortname, []
                )
            )

            await plugin_manager.after_action(
                core.Event(
                    space_name=request.space_name,
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
        except api.Exception as e:
            failed_records.append(
                {
                    "record": record,
                    "error": e.error.message,
                    "error_code": e.error.code,
                }
            )
    return records, failed_records

async def serve_request_patch(request, owner_shortname: str):
    records: list[core.Record] = []
    failed_records: list[dict] = []

    for record in request.records:
        try:
            if record.subpath[0] != "/":
                record.subpath = f"/{record.subpath}"

            await plugin_manager.before_action(
                core.Event(
                    space_name=request.space_name,
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
                sys.modules["models.core"], camel_case(
                    record.resource_type
                )
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
                    entry_shortname=record.shortname
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.NOT_ALLOWED,
                        message="You don't have permission to this action [5]",
                    ),
                )

            # GET PAYLOAD DATA
            old_version_flattend, old_resource_payload_body = await serve_request_update_r_replace_fetch_payload(
                old_resource_obj, record, request, resource_cls, schema_shortname
            )

            # GENERATE NEW RESOURCE OBJECT
            resource_obj = old_resource_obj
            resource_obj.updated_at = datetime.now()

            new_version_flattend = {}

            if record.resource_type == ResourceType.log:
                new_resource_payload_data = record.attributes.get("payload", {}).get(
                    "body", {}
                )
            else:
                new_resource_payload_data = (
                    resource_obj.update_from_record(
                        record=record,
                        old_body=old_resource_payload_body,
                        replace=request.request_type == api.RequestType.r_replace,
                    )
                )
                new_version_flattend = resource_obj.model_dump()
                if new_resource_payload_data:
                    new_version_flattend["payload"] = {
                        **new_version_flattend["payload"],
                        "body": new_resource_payload_data
                    }
                new_version_flattend = flatten_dict(new_version_flattend)

                await validate_uniqueness(
                    request.space_name, record, RequestType.update
                )

            if record.resource_type == ResourceType.log:
                history_diff = await db.update(
                    space_name=request.space_name,
                    subpath=record.subpath,
                    meta=resource_obj,
                    old_version_flattend={},
                    new_version_flattend={},
                    updated_attributes_flattend=[],
                    user_shortname=owner_shortname,
                    schema_shortname=schema_shortname,
                    retrieve_lock_status=record.retrieve_lock_status,
                )
            else:
                updated_attributes_flattend = list(
                    flatten_dict(record.attributes).keys()
                )
                if request.request_type == RequestType.r_replace:
                    updated_attributes_flattend = (
                            list(old_version_flattend.keys()) +
                            list(new_version_flattend.keys())
                    )

                if (settings.active_data_db == 'sql'
                        and resource_obj.payload
                        and resource_obj.payload.content_type == ContentType.json):
                    resource_obj.payload.body = {
                        **resource_obj.payload.body,
                        **new_resource_payload_data
                    }  # type: ignore

                # VALIDATE SEPARATE PAYLOAD BODY
                if (
                    resource_obj.payload
                    and resource_obj.payload.content_type == ContentType.json
                    and resource_obj.payload.schema_shortname
                    and new_resource_payload_data is not None
                ):
                    await validate_payload_with_schema(
                        payload_data=resource_obj.payload.body,
                        space_name=request.space_name,
                        schema_shortname=resource_obj.payload.schema_shortname,
                    )

                history_diff = await db.update(
                    space_name=request.space_name,
                    subpath=record.subpath,
                    meta=resource_obj,
                    old_version_flattend=old_version_flattend,
                    new_version_flattend=new_version_flattend,
                    updated_attributes_flattend=updated_attributes_flattend,
                    user_shortname=owner_shortname,
                    schema_shortname=schema_shortname,
                    retrieve_lock_status=record.retrieve_lock_status,
                )

            if new_resource_payload_data is not None:
                await db.save_payload_from_json(
                    request.space_name,
                    record.subpath,
                    resource_obj,
                    new_resource_payload_data,
                )

            if (
                isinstance(resource_obj, core.User) and
                record.attributes.get("is_active") is False
            ):
                await remove_active_session(record.shortname)

            records.append(
                resource_obj.to_record(
                    record.subpath, resource_obj.shortname, []
                )
            )

            await plugin_manager.after_action(
                core.Event(
                    space_name=request.space_name,
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
        except api.Exception as e:
            failed_records.append(
                {
                    "record": record,
                    "error": e.error.message,
                    "error_code": e.error.code,
                }
            )
    return records, failed_records

async def serve_request_assign(request, owner_shortname: str):
    records: list[core.Record] = []
    failed_records: list[dict] = []

    for record in request.records:
        try:
            if not record.attributes.get("owner_shortname"):
                raise api.Exception(
                    status.HTTP_400_BAD_REQUEST,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.MISSING_DATA,
                        message="The owner_shortname is required",
                    ),
                )
            _target_user = await db.load(
                space_name=settings.management_space,
                subpath=settings.users_subpath,
                shortname=record.attributes["owner_shortname"],
                class_type=core.User,
            )

            if record.subpath[0] != "/":
                record.subpath = f"/{record.subpath}"
            await plugin_manager.before_action(
                core.Event(
                    space_name=request.space_name,
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
                sys.modules["models.core"], camel_case(
                    record.resource_type)
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
                schema_shortname=schema_shortname,
            )

            # CHECK PERMISSION
            if not await access_control.check_access(
                    user_shortname=owner_shortname,
                    space_name=request.space_name,
                    subpath=record.subpath,
                    resource_type=record.resource_type,
                    action_type=core.ActionType.assign,
                    resource_is_active=resource_obj.is_active,
                    resource_owner_shortname=resource_obj.owner_shortname,
                    resource_owner_group=resource_obj.owner_group_shortname,
                    record_attributes=record.attributes,
                    entry_shortname=record.shortname
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.NOT_ALLOWED,
                        message="You don't have permission to this action [05]",
                    ),
                )

            old_version_flattend = flatten_dict(resource_obj.model_dump())

            resource_obj.updated_at = datetime.now()
            resource_obj.owner_shortname = record.attributes["owner_shortname"]

            history_diff = await db.update(
                space_name=request.space_name,
                subpath=record.subpath,
                meta=resource_obj,
                old_version_flattend=old_version_flattend,
                new_version_flattend=flatten_dict(resource_obj.model_dump()),
                updated_attributes_flattend=["owner_shortname"],
                user_shortname=owner_shortname,
                schema_shortname=schema_shortname,
                retrieve_lock_status=record.retrieve_lock_status,
            )

            records.append(
                resource_obj.to_record(
                    record.subpath, resource_obj.shortname, []
                )
            )

            await plugin_manager.after_action(
                core.Event(
                    space_name=request.space_name,
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
        except api.Exception as e:
            failed_records.append(
                {
                    "record": record,
                    "error": e.error.message,
                    "error_code": e.error.code,
                }
            )

    return records, failed_records


async def serve_request_update_acl(request, owner_shortname: str):
    records: list[core.Record] = []
    failed_records: list[dict] = []

    for record in request.records:
        try:
            if record.attributes.get("acl", None) is None:
                raise api.Exception(
                    status.HTTP_400_BAD_REQUEST,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.MISSING_DATA,
                        message="The acl is required",
                    ),
                )

            if record.subpath[0] != "/":
                record.subpath = f"/{record.subpath}"
            await plugin_manager.before_action(
                core.Event(
                    space_name=request.space_name,
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
                sys.modules["models.core"], camel_case(
                    record.resource_type)
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
                schema_shortname=schema_shortname,
            )

            # CHECK PERMISSION
            if not await access_control.check_access(
                    user_shortname=owner_shortname,
                    space_name=request.space_name,
                    subpath=record.subpath,
                    resource_type=record.resource_type,
                    action_type=core.ActionType.update,
                    resource_is_active=resource_obj.is_active,
                    resource_owner_shortname=resource_obj.owner_shortname,
                    resource_owner_group=resource_obj.owner_group_shortname,
                    record_attributes=record.attributes,
            ) or resource_obj.owner_shortname != owner_shortname:
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.NOT_ALLOWED,
                        message="You don't have permission to this action [06]",
                    ),
                )

            old_version_flattend = flatten_dict(resource_obj.model_dump())

            resource_obj.updated_at = datetime.now()
            resource_obj.acl = record.attributes["acl"]

            history_diff = await db.update(
                space_name=request.space_name,
                subpath=record.subpath,
                meta=resource_obj,
                old_version_flattend=old_version_flattend,
                new_version_flattend=flatten_dict(resource_obj.model_dump()),
                updated_attributes_flattend=["acl"],
                user_shortname=owner_shortname,
                schema_shortname=schema_shortname,
                retrieve_lock_status=record.retrieve_lock_status,
            )

            records.append(
                resource_obj.to_record(
                    record.subpath, resource_obj.shortname, []
                )
            )

            await plugin_manager.after_action(
                core.Event(
                    space_name=request.space_name,
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
        except api.Exception as e:
            failed_records.append(
                {
                    "record": record,
                    "error": e.error.message,
                    "error_code": e.error.code,
                }
            )
    return records, failed_records


async def serve_request_delete(request, owner_shortname: str):
    records: list[core.Record] = []
    failed_records: list[dict] = []

    for record in request.records:
        if record.subpath[0] != "/":
            record.subpath = f"/{record.subpath}"
        await plugin_manager.before_action(
            core.Event(
                space_name=request.space_name,
                subpath=record.subpath,
                shortname=record.shortname,
                action_type=core.ActionType.delete,
                resource_type=record.resource_type,
                user_shortname=owner_shortname,
            )
        )

        resource_cls = getattr(
            sys.modules["models.core"], camel_case(
                record.resource_type)
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
                entry_shortname=record.shortname
        ):
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(
                    type="request",
                    code=InternalErrorCode.NOT_ALLOWED,
                    message="You don't have permission to this action [6]",
                ),
            )
        try:
            await db.delete(
                space_name=request.space_name,
                subpath=record.subpath,
                meta=resource_obj,
                user_shortname=owner_shortname,
                schema_shortname=schema_shortname,
                retrieve_lock_status=record.retrieve_lock_status,
            )
        except api.Exception as e:
            failed_records.append(
                {
                    "record": record,
                    "error": e.error.message,
                    "error_code": e.error.code,
                }
            )

        await plugin_manager.after_action(
            core.Event(
                space_name=request.space_name,
                subpath=record.subpath,
                shortname=record.shortname,
                action_type=core.ActionType.delete,
                resource_type=record.resource_type,
                user_shortname=owner_shortname,
                attributes={"entry": resource_obj},
            )
        )

        records.append(record)

    return records, failed_records


async def serve_request_move(request, owner_shortname: str):
    records: list[core.Record] = []
    failed_records: list[dict] = []

    for record in request.records:
        if record.subpath[0] != "/":
            record.subpath = f"/{record.subpath}"

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

        await plugin_manager.before_action(
            core.Event(
                space_name=request.space_name,
                subpath=record.attributes["src_subpath"],
                shortname=record.attributes["src_shortname"],
                action_type=core.ActionType.move,
                resource_type=record.resource_type,
                user_shortname=owner_shortname,
                attributes={
                    "dest_subpath": record.attributes["dest_subpath"]},
            )
        )

        resource_cls = getattr(
            sys.modules["models.core"], camel_case(
                record.resource_type)
        )
        resource_obj = await db.load(
            space_name=request.space_name,
            subpath=record.attributes["src_subpath"],
            shortname=record.attributes["src_shortname"],
            class_type=resource_cls,
            user_shortname=owner_shortname,
        )
        check_src_subpath = await access_control.check_access(
                user_shortname=owner_shortname,
                space_name=request.space_name,
                subpath=record.attributes["src_subpath"],
                resource_type=record.resource_type,
                action_type=core.ActionType.delete,
                resource_is_active=resource_obj.is_active,
                resource_owner_shortname=resource_obj.owner_shortname,
                resource_owner_group=resource_obj.owner_group_shortname,
                entry_shortname=record.shortname
        )
        check_dest_subpath = await access_control.check_access(
            user_shortname=owner_shortname,
            space_name=request.space_name,
            subpath=record.attributes["dest_subpath"],
            resource_type=record.resource_type,
            action_type=core.ActionType.create,
        )
        if not check_src_subpath or not check_dest_subpath:
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(
                    type="request",
                    code=InternalErrorCode.NOT_ALLOWED,
                    message="You don't have permission to this action [7]",
                ),
            )

        try:
            await db.move(
                request.space_name,
                record.attributes["src_subpath"],
                record.attributes["src_shortname"],
                record.attributes["dest_subpath"],
                record.attributes["dest_shortname"],
                resource_obj,
            )
        except api.Exception as e:
            failed_records.append(
                {
                    "record": record,
                    "error": e.error.message,
                    "error_code": e.error.code,
                }
            )

        await plugin_manager.after_action(
            core.Event(
                space_name=request.space_name,
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

        records.append(record)

    return records, failed_records


def get_resource_content_type_from_payload_content_type(payload_file, payload_filename, record):
    if payload_filename.endswith(".json"):
        return ContentType.json
    elif payload_file.content_type == "application/pdf":
        return ContentType.pdf
    elif payload_file.content_type == "text/csv":
        return ContentType.csv
    elif payload_file.content_type == "application/octet-stream":
        if record.attributes.get("content_type") == "jsonl":
            return ContentType.jsonl
        elif record.attributes.get("content_type") == "sqlite":
            return ContentType.sqlite
        elif record.attributes.get("content_type") == "parquet":
            return ContentType.parquet
        else:
            return ContentType.text
    elif payload_file.content_type == "text/markdown":
        return ContentType.markdown
    elif payload_file.content_type and "image/" in payload_file.content_type:
        return ContentType.image
    elif payload_file.content_type and "audio/" in payload_file.content_type:
        return ContentType.audio
    elif payload_file.content_type and "video/" in payload_file.content_type:
        return ContentType.video
    else:
        raise api.Exception(
            status.HTTP_406_NOT_ACCEPTABLE,
            api.Error(
                type="attachment",
                code=InternalErrorCode.NOT_SUPPORTED_TYPE,
                message="The file type is not supported",
            ),
        )


async def handle_update_state(space_name, logged_in_user, ticket_obj, action, user_roles):
    workflows_data = await db.load(
        space_name=space_name,
        subpath="workflows",
        shortname=ticket_obj.workflow_shortname,
        class_type=core.Content,
        user_shortname=logged_in_user,
    )

    workflows_payload: Any = {}
    if workflows_data.payload is not None and workflows_data.payload.body is not None:
        if settings.active_data_db == 'file':
            workflows_payload = await db.load_resource_payload(
                space_name=space_name,
                subpath="workflows",
                filename=str(workflows_data.payload.body),
                class_type=core.Content,
            )
        else:
            workflows_payload = workflows_data.payload.body
    else:
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="transition",
                code=InternalErrorCode.MISSING_DATA,
                message="Invalid workflow",
            ),
        )

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
        workflows_payload.get("states", []), ticket_obj.state, action, user_roles
    )

    if not response.get("status", False):
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="transition",
                code=InternalErrorCode.INVALID_TICKET_STATUS,
                message=response.get("message", "")
            ),
        )

    old_version_flattend = flatten_dict(ticket_obj.model_dump())
    old_version_flattend.pop("payload.body", None)
    old_version_flattend.update(
        flatten_dict({"payload.body": ticket_obj}))

    ticket_obj.state = response["message"]
    ticket_obj.is_open = check_open_state(
        workflows_payload.get("states", []), response["message"]
    )

    return ticket_obj, workflows_payload, response, old_version_flattend


async def update_state_handle_resolution(ticket_obj, workflows_payload, response, resolution):
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
    return ticket_obj


async def serve_space_create(request, record, owner_shortname: str):
    await is_space_exist(request.space_name, should_exist=False)

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
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [1]",
            ),
        )

    resource_obj = core.Meta.from_record(
        record=record, owner_shortname=owner_shortname
    )
    resource_obj.is_active = True
    resource_obj.shortname = request.space_name
    if isinstance(resource_obj, core.Space):
        resource_obj.indexing_enabled = True
        resource_obj.active_plugins = [
            "action_log",
            "redis_db_update",
            "resource_folders_creation",
        ]

    await db.save(
        request.space_name,
        record.subpath,
        resource_obj,
    )


async def serve_space_update(request, record, owner_shortname: str):
    try:
        space = core.Space.from_record(record, owner_shortname)
        await is_space_exist(request.space_name)

        if (
                request.space_name != record.shortname
        ):
            raise Exception
    except Exception:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.INVALID_SPACE_NAME,
                message=f"Space name {request.space_name} provided is empty or invalid [6]",
            ),
        )
    if not await access_control.check_access(
            user_shortname=owner_shortname,
            space_name=settings.all_spaces_mw,
            subpath="/",
            resource_type=ResourceType.space,
            action_type=core.ActionType.update,
            record_attributes=record.attributes,
            entry_shortname=record.shortname
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [2]",
            ),
        )

    await plugin_manager.before_action(
        core.Event(
            space_name=space.shortname,
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
        user_shortname=owner_shortname,
        retrieve_lock_status=record.retrieve_lock_status,
    )
    return history_diff

async def serve_space_delete(request, record, owner_shortname: str):
    if request.space_name == "management":
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.CANNT_DELETE,
                message="Cannot delete management space",
            ),
        )

    await is_space_exist(request.space_name)

    if not await access_control.check_access(
            user_shortname=owner_shortname,
            space_name=settings.all_spaces_mw,
            subpath="/",
            resource_type=ResourceType.space,
            action_type=core.ActionType.delete,
            entry_shortname=record.shortname
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action [3]",
            ),
        )
    await repository.delete_space(request.space_name, record, owner_shortname)
    if settings.active_data_db == 'file':
        async with RedisServices() as redis_services:
            x = await redis_services.list_indices()
            if x:
                indices: list[str] = x
                for index in indices:
                    if index.startswith(f"{request.space_name}:"):
                        await redis_services.drop_index(index, True)


async def data_asset_attachments_handler(query, attachments):
    files_paths = []
    for attachment in attachments.get(query.data_asset_type, []):
        file_path = db.payload_path(
            space_name=query.space_name,
            subpath=f"{query.subpath}/{query.shortname}",
            class_type=getattr(sys.modules["models.core"], camel_case(query.data_asset_type)),
        )
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
                schema_shortname=attachment.attributes["payload"].schema_shortname
            )
        if (
                attachment.attributes["payload"].schema_shortname
                and attachment.resource_type == DataAssetType.jsonl
        ):
            await validate_jsonl_with_schema(
                file_path=file_path,
                space_name=query.space_name,
                schema_shortname=attachment.attributes["payload"].schema_shortname
            )
        files_paths.append(file_path)
    return files_paths


async def data_asset_handler(conn, query, files_paths, attachments):
    for idx, file_path in enumerate(files_paths):
        # Load the file into the in-memory DB
        match query.data_asset_type:
            case DataAssetType.csv:
                globals().setdefault(
                    attachments[query.data_asset_type][idx].shortname,
                    conn.read_csv(str(file_path))
                )
            case DataAssetType.jsonl:
                globals().setdefault(
                    attachments[query.data_asset_type][idx].shortname,
                    conn.read_json(
                        str(file_path),
                        format='auto'
                    )
                )
            case DataAssetType.parquet:
                globals().setdefault(
                    attachments[query.data_asset_type][idx].shortname,
                    conn.read_parquet(str(file_path))
                )


async def import_resources_from_csv_handler(
    row, meta_class_attributes, schema_content, data_types_mapper,
):
    shortname = ""
    meta_object = {}
    payload_object = {}
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
                    meta_object[keys_list[0].strip(
                    )][keys_list[1].strip()] = value
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
                if (
                    "properties" in current_schema_property
                    and item.strip() in current_schema_property["properties"]
                ):
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
                payload_object[keys_list[0].strip(
                )][keys_list[1].strip()] = value
            case 3:
                if keys_list[0].strip() not in payload_object:
                    payload_object[keys_list[0].strip()] = {}
                if keys_list[1].strip() not in payload_object[keys_list[0].strip()]:
                    payload_object[keys_list[0].strip(
                    )][keys_list[1].strip()] = {}
                payload_object[keys_list[0].strip()][keys_list[1].strip()][
                    keys_list[2].strip()
                ] = value
            case _:
                continue

    return payload_object, meta_object, shortname


async def create_or_update_resource_with_payload_handler(
        record, owner_shortname, space_name, payload_file, payload_filename, checksum, sha, resource_content_type
):
    if record.resource_type == ResourceType.ticket:
        record = await set_init_state_from_record(
            record, owner_shortname, space_name
        )
    resource_obj = core.Meta.from_record(
        record=record, owner_shortname=owner_shortname)
    if record.resource_type == ResourceType.ticket:
        record = await set_init_state_from_record(
            record, owner_shortname, space_name
        )
    resource_obj.payload = core.Payload(
        content_type=resource_content_type,
        checksum=checksum,
        client_checksum=sha if isinstance(sha, str) else None,
        schema_shortname="meta_schema"
        if record.resource_type == ResourceType.schema
        else record.attributes.get("payload", {}).get("schema_shortname", None),
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
                message="Only resources of type 'attachment' or 'content' are allowed",
            ),
        )
    if settings.active_data_db == "file":
        resource_obj.payload.body = f"{resource_obj.shortname}." + \
                                    payload_filename.split(".")[1]
    elif not isinstance(resource_obj, core.Attachment):
        resource_obj.payload.body = json.load(payload_file.file)
        payload_file.file.seek(0)

    if (
        resource_content_type == ContentType.json
        and resource_obj.payload.schema_shortname
    ):
        await validate_payload_with_schema(
            payload_data=payload_file,
            space_name=space_name,
            schema_shortname=resource_obj.payload.schema_shortname,
        )

    return resource_obj, record


def get_mime_type(content_type: ContentType) -> str:
    mime_types = {
        ContentType.text: "text/plain",
        ContentType.markdown: "text/markdown",
        ContentType.html: "text/html",
        ContentType.json: "application/json",
        ContentType.image: "image/jpeg",
        ContentType.python: "text/x-python",
        ContentType.pdf: "application/pdf",
        ContentType.audio: "audio/mpeg",
        ContentType.video: "video/mp4",
        ContentType.csv: "text/csv",
        ContentType.parquet: "application/octet-stream",
        ContentType.jsonl: "application/jsonlines",
        ContentType.duckdb: "application/octet-stream",
        ContentType.sqlite: "application/vnd.sqlite3"
    }
    return mime_types.get(content_type, "application/octet-stream")
