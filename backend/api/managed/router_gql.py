from datetime import datetime
from uuid import uuid4
import strawberry
from models.enums import ContentType, ResourceType
import models.schema as schema_gql
from utils.access_control import access_control
from utils.generate_email import generate_email_from_template, generate_subject
from utils.helpers import pp
from utils.jwt import sign_jwt
from utils.repository import get_resource_obj_or_none, subpath_query
from models import core
from utils.settings import settings
from fastapi import status
from utils.custom_validations import validate_payload_with_schema, validate_uniqueness
from utils import db
from utils.redis_services import RedisServices
from api.user.service import send_sms, send_email
from fastapi.logger import logger
from utils.plugin_manager import plugin_manager

@strawberry.type
class Query:
    @strawberry.field
    async def subpath_query(self, query: schema_gql.QueryGQL) -> schema_gql.QueryResult:
        records, total = await subpath_query(query, "dmart") # TODO: use the authenticated user
        pp(records=records)

        return schema_gql.QueryResult(
            records=[schema_gql.RecordGQL.from_pydantic(record) for record in records],
            total=total,
            returned=len(records)
        )


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_resource(self, space_name: str, records: list[schema_gql.InputRecordGQL]) -> schema_gql.ResponseGQL:
        owner_shortname = "dmart" # TODO: use the authenticated user
        success_records: list[schema_gql.RecordGQL] = []
        failed_records: list[schema_gql.RecordGQL] = []
        for record in records:
            if record.subpath[0] != "/":
                record.subpath = f"/{record.subpath}"
            try:
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
                    raise schema_gql.CreateRecordFailed(
                        code=status.HTTP_401_UNAUTHORIZED,
                        type="request",
                        message="You don't have permission to this action [g4]"
                    )

                # if record.resource_type == ResourceType.ticket:
                #     record = await set_init_state_from_request(
                #         request, record.branch_name, owner_shortname
                #     )

                resource_obj = await get_resource_obj_or_none(
                    space_name=space_name,
                    branch_name=record.branch_name,
                    subpath=record.subpath,
                    shortname=record.shortname,
                    resource_type=record.resource_type,
                    user_shortname=owner_shortname,
                )
                if (
                    resource_obj
                    and resource_obj.shortname != settings.auto_uuid_rule
                ):
                    raise schema_gql.CreateRecordFailed(
                        type="request",
                        code=status.HTTP_400_BAD_REQUEST,
                        message=f"This shortname {resource_obj.shortname} already exists",
                    )

                await validate_uniqueness(space_name, record)

                resource_obj = core.Meta.from_record(
                    record=record, owner_shortname=owner_shortname
                )
                resource_obj.created_at = datetime.now()
                resource_obj.updated_at = datetime.now()
                body_shortname = record.shortname
                if resource_obj.shortname == settings.auto_uuid_rule:
                    resource_obj.uuid = uuid4()
                    resource_obj.shortname = str(resource_obj.uuid)[:8]
                    body_shortname = resource_obj.shortname

                separate_payload_data = None
                if (
                    resource_obj.payload
                    and resource_obj.payload.content_type == ContentType.json
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
                        space_name=space_name,
                        branch_name=record.branch_name,
                        schema_shortname=resource_obj.payload.schema_shortname,
                    )

                await db.save(
                    space_name,
                    record.subpath,
                    resource_obj,
                    record.branch_name,
                )

                if record.resource_type == ResourceType.user:
                    invitation_token = sign_jwt(
                        {"shortname": record.shortname}, settings.jwt_access_expires
                    )

                    channel = ""
                    async with RedisServices() as redis_services:
                        if not record.attributes.get(
                            "is_msisdn_verified", False
                        ) and record.attributes.get("msisdn"):
                            invitation_token = sign_jwt(
                                {"shortname": record.shortname, "channel": "SMS"},
                                settings.jwt_access_expires,
                            )
                            invitation_link = f"{settings.invitation_link}/auth/invitation?invitation={invitation_token}"
                            token_uuid = str(uuid4())[:8]
                            await redis_services.set(
                                f"short/{token_uuid}",
                                invitation_link,
                                ex=60 * 60 * 48,
                                nx=False,
                            )
                            link = (
                                f"{settings.public_app_url}/managed/s/{token_uuid}"
                            )
                            invitation_message = f"Confirm your account via this link: {link}, This link can be used once and within the next 48 hours."
                            channel += f"SMS:{record.attributes.get('msisdn')},"
                            try:
                                await send_sms(
                                    msisdn=record.attributes.get("msisdn", ""),
                                    message=invitation_message,
                                )
                            except Exception as e:
                                logger.warning(
                                    "Exception",
                                    extra={
                                        "props": {
                                            "record": record,
                                            "target": "msisdn",
                                            "exception": e,
                                        }
                                    },
                                )
                        if not record.attributes.get(
                            "is_email_verified", False
                        ) and record.attributes.get("email"):
                            invitation_token = sign_jwt(
                                {"shortname": record.shortname, "channel": "EMAIL"},
                                settings.jwt_access_expires,
                            )
                            invitation_link = f"{settings.invitation_link}/auth/invitation?invitation={invitation_token}"
                            token_uuid = str(uuid4())[:8]
                            await redis_services.set(
                                f"short/{token_uuid}",
                                invitation_link,
                                ex=60 * 60 * 48,
                                nx=True,
                            )
                            link = (
                                f"{settings.public_app_url}/managed/s/{token_uuid}"
                            )
                            channel += f"EMAIL:{record.attributes.get('email')}"
                            try:
                                await send_email(
                                    from_address=settings.email_sender,
                                    to_address=record.attributes.get("email", ""),
                                    # message=f"Welcome, this is your invitation link: {invitation_link}",
                                    message=generate_email_from_template(
                                        "activation",
                                        {
                                            "link": link,
                                            "name": record.attributes.get(
                                                "displayname", {}
                                            ).get("en", ""),
                                            "shortname": record.shortname,
                                            "msisdn": record.attributes.get(
                                                "msisdn"
                                            ),
                                        },
                                    ),
                                    subject=generate_subject("activation"),
                                )
                            except Exception as e:
                                logger.warning(
                                    "Exception",
                                    extra={
                                        "props": {
                                            "record": record,
                                            "target": "email",
                                            "exception": e,
                                        }
                                    },
                                )
                        await redis_services.set(
                            f"users:login:invitation:{invitation_token}", channel
                        )

                if separate_payload_data != None and isinstance(
                    separate_payload_data, dict
                ):
                    await db.save_payload_from_json(
                        space_name,
                        record.subpath,
                        resource_obj,
                        separate_payload_data,
                        record.branch_name,
                    )

                success_records.append(
                    schema_gql.RecordGQL.from_pydantic(
                        instance=resource_obj.to_record(
                            record.subpath,
                            resource_obj.shortname,
                            [],
                            record.branch_name,
                        )
                    )
                )
                record.attributes["logged_in_user_token"] = "token" # TODO: use auth user
                await plugin_manager.after_action(
                    core.Event(
                        space_name=space_name,
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

            except Exception as e:
                failed_records.append(
                    schema_gql.FailedRecord(
                        record=schema_gql.RecordGQL.from_pydantic(record),
                        error=e,
                        error_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                ) 

        return schema_gql.CreateRecordSuccess(
            success_records=success_records,
            failed_records=failed_records
        )