""" Session Apis """

import json
import re
from uuid import uuid4
import aiofiles
from utils.async_request import AsyncRequest
from utils.generate_email import generate_subject
from utils.generate_email import generate_email_from_template
from fastapi import APIRouter, Body, Query, status, Depends, Response, Header
import models.api as api
import models.core as core
from models.enums import ActionType, QueryType, RequestType, ResourceType, ContentType
import utils.db as db
from utils.access_control import access_control
from utils.custom_validations import validate_payload_with_schema
from utils.internal_error_code import InternalErrorCode
from utils.jwt import JWTBearer, remove_redis_active_session, sign_jwt
from typing import Any
from utils.operational_repo import operational_repo
from utils.settings import settings
from utils.plugin_manager import plugin_manager
import utils.password_hashing as password_hashing
from utils.social_sso import get_facebook_sso, get_google_sso
from .service import (
    gen_alphanumeric,
    send_email,
    send_sms,
    send_otp,
    email_send_otp,
)
from .models.requests import (
    ConfirmOTPRequest,
    PasswordResetRequest,
    SendOTPRequest,
    UserLoginRequest,
)
import utils.regex as rgx
from languages.loader import languages
from fastapi_sso.sso.google import GoogleSSO
from fastapi_sso.sso.facebook import FacebookSSO
from fastapi_sso.sso.base import SSOBase

router = APIRouter()

MANAGEMENT_SPACE: str = settings.management_space
MANAGEMENT_BRANCH: str = settings.management_space_branch
USERS_SUBPATH: str = "users"


@router.get(
    "/check-existing", response_model=api.Response, response_model_exclude_none=True
)
async def check_existing_user_fields(
    _=Depends(JWTBearer()),
    shortname: str | None = Query(
        default=None, pattern=rgx.SHORTNAME, examples=["john_doo"]
    ),
    msisdn: str | None = Query(
        default=None, pattern=rgx.EXTENDED_MSISDN, examples=["7777778110"]
    ),
    email: str | None = Query(
        default=None, pattern=rgx.EMAIL, examples=["john_doo@mail.com"]
    ),
):
    unique_fields = {"shortname": shortname, "msisdn": msisdn, "email_unescaped": email}

    search_str = f"@subpath:{USERS_SUBPATH}"
    redis_escape_chars = str.maketrans(
        {".": r"\.", "@": r"\@", ":": r"\:", "/": r"\/", "-": r"\-", " ": r"\ "}
    )
    for key, value in unique_fields.items():
        if not value:
            continue
        value = value.translate(redis_escape_chars).replace("\\\\", "\\")
        if key == "email_unescaped":
            value = f"{{{value}}}"
        redis_search_res: tuple[int, list[dict[str, Any]]] = (
            await operational_repo.search(
                api.Query(
                    type=QueryType.search,
                    space_name=MANAGEMENT_SPACE,
                    branch_name=MANAGEMENT_BRANCH,
                    subpath=USERS_SUBPATH,
                    search=search_str + f" @{key}:{value}",
                    limit=1,
                    offset=0
                )
            )
        )

        if redis_search_res and redis_search_res[0] > 0:
            return api.Response(
                status=api.Status.success,
                attributes={"unique": False, "field": key},
            )

    return api.Response(status=api.Status.success, attributes={"unique": True})


@router.post("/create", response_model=api.Response, response_model_exclude_none=True)
async def create_user(record: core.Record) -> api.Response:
    """Register a new user by invitation"""
    if not settings.is_registrable:
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(type="create", code=50, message="Register API is disabled"),
        )

    if "invitation" not in record.attributes:
        # TBD validate invitation (simply it is a jwt signed token )
        # jwt-signed shortname, email and expiration time
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="create", code=50, message="bad or missign invitation token"
            ),
        )

    # TBD : Raise error if user already eists.

    if "password" not in record.attributes:
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(type="create", code=50, message="empty password"),
        )

    if not re.match(rgx.PASSWORD, record.attributes["password"]):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="jwtauth",
                code=14,
                message="password dose not match required rules",
            ),
        )

    entity = core.EntityDTO.from_record(record, MANAGEMENT_SPACE, record.shortname)

    await plugin_manager.before_action(entity.to_event_data(core.ActionType.create))

    user = core.User.from_record(record=record, owner_shortname=record.shortname)

    await operational_repo.validate_uniqueness(entity, record.attributes)

    separate_payload_data: dict[str, Any] = {}
    if "payload" in record.attributes and "body" in record.attributes["payload"]:
        schema_shortname = getattr(user.payload, "schema_shortname", None)
        user.payload = core.Payload(
            content_type=ContentType.json,
            schema_shortname=schema_shortname,
            body=(
                record.attributes["payload"]["body"]
                if record.attributes["payload"].get("body", False)
                else ""
            ),
        )
        if user.payload and isinstance(user.payload.body, dict):
            separate_payload_data = user.payload.body
            user.payload.body = record.shortname + ".json"

            if user.payload.schema_shortname:
                await validate_payload_with_schema(
                    payload_data=separate_payload_data,
                    space_name=MANAGEMENT_SPACE,
                    branch_name=MANAGEMENT_BRANCH,
                    schema_shortname=user.payload.schema_shortname,
                )

    await db.create(entity, user, separate_payload_data)

    await plugin_manager.after_action(entity.to_event_data(core.ActionType.create))

    return api.Response(status=api.Status.success)


@router.post(
    "/login",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def login(response: Response, request: UserLoginRequest) -> api.Response:
    """Login and generate refresh token"""

    shortname: str | None = None
    user: core.User | None = None
    user_updates: dict[str, Any] = {}
    identifier = request.check_fields()
    try:
        if request.invitation:
            invitation_token: str | None = await operational_repo.find_key(
                f"users:login:invitation:{request.invitation}"
            )
            if (
                not invitation_token
                or len(token_data := invitation_token.split(":")) < 3
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="jwtauth",
                        code=InternalErrorCode.INVALID_INVITATION,
                        message="Invalid invitation",
                    ),
                )

            # data = decode_jwt(request.invitation)
            shortname = token_data[0]
            channel = token_data[1]
            token_identifier = token_data[2]

            entity = core.EntityDTO(
                space_name=MANAGEMENT_SPACE,
                subpath=USERS_SUBPATH,
                shortname=shortname,
                resource_type=ResourceType.user,
                user_shortname=shortname,
            )
            user = await db.load(entity)

            if (
                user
                and request.shortname != user.shortname
                and request.msisdn != user.msisdn
                and request.email != user.email
            ):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="jwtauth",
                        code=InternalErrorCode.INVALID_INVITATION,
                        message="Invalid invitation or data provided",
                    ),
                )

            if user and channel == "EMAIL" and user.email == token_identifier:
                user_updates["is_email_verified"] = True
            elif user and channel == "SMS" and user.msisdn == token_identifier:
                user_updates["is_msisdn_verified"] = True
        else:
            if identifier is None:
                raise api.Exception(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    api.Error(
                        type="request",
                        code=InternalErrorCode.INVALID_IDENTIFIER,
                        message="Invalid identifier [2]",
                    ),
                )

            if "shortname" in identifier:
                shortname = identifier["shortname"]
                entity = core.EntityDTO(
                    space_name=MANAGEMENT_SPACE,
                    subpath=USERS_SUBPATH,
                    shortname=shortname,
                    resource_type=ResourceType.user,
                    user_shortname=shortname,
                )
                user = await db.load(entity)
            else:
                key, value = list(identifier.items())[0]
                if isinstance(value, str) and isinstance(key, str):
                    user = await access_control.get_user_by_criteria(
                        key, value
                    )
                    if not user:
                        raise Exception("Invalid identifier")

                    if (key == "msisdn" and not user.is_msisdn_verified) or (
                        key == "email" and not user.is_email_verified
                    ):
                        raise api.Exception(
                            status.HTTP_401_UNAUTHORIZED,
                            api.Error(
                                type="auth",
                                code=InternalErrorCode.USER_ISNT_VERIFIED,
                                message="This user is not verified",
                            ),
                        )
                else:
                    shortname = None
                if shortname is None:
                    raise api.Exception(
                        status.HTTP_401_UNAUTHORIZED,
                        api.Error(
                            type="auth",
                            code=InternalErrorCode.INVALID_USERNAME_AND_PASS,
                            message="Invalid username or password [1]",
                        ),
                    )

        #! TODO: Implement check agains is_email_verified && is_msisdn_verified
        if (
            user
            and user.is_active
            and (
                request.invitation
                or password_hashing.verify_password(
                    request.password or "", user.password or ""
                )
            )
        ):
            record = await process_user_login(
                user, response, user_updates, request.firebase_token
            )

            await plugin_manager.after_action(
                core.Event(
                    space_name=MANAGEMENT_SPACE,
                    branch_name=MANAGEMENT_BRANCH,
                    subpath=USERS_SUBPATH,
                    shortname=shortname,
                    action_type=core.ActionType.update,
                    resource_type=ResourceType.user,
                    user_shortname=shortname,
                )
            )
            return api.Response(status=api.Status.success, records=[record])
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="auth",
                code=InternalErrorCode.INVALID_USERNAME_AND_PASS,
                message="Invalid username or password [2]",
            ),
        )
    except api.Exception as e:
        if e.error.type == "db":
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(
                    type="auth",
                    code=InternalErrorCode.INVALID_USERNAME_AND_PASS,
                    message="Invalid username or password [3]",
                    info=[{"details": str(e)}],
                ),
            )
        else:
            raise e


@router.get("/profile", response_model=api.Response, response_model_exclude_none=True)
async def get_profile(shortname=Depends(JWTBearer())) -> api.Response:

    entity = core.EntityDTO(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        resource_type=ResourceType.user,
        user_shortname=shortname,
    )

    await plugin_manager.before_action(entity.to_event_data(core.ActionType.view))

    user: core.User = await db.load(entity)

    attributes: dict[str, Any] = {}
    if user.email:
        attributes["email"] = user.email
    if user.displayname:
        attributes["displayname"] = user.displayname
    if user.msisdn:
        attributes["msisdn"] = user.msisdn
    if user.payload:
        attributes["payload"] = user.payload
        path = settings.spaces_folder / MANAGEMENT_SPACE / USERS_SUBPATH
        if (
            user.payload
            and user.payload.content_type
            and user.payload.content_type == ContentType.json
            and (path / str(user.payload.body)).is_file()
        ):
            async with aiofiles.open(
                path / str(user.payload.body), "r"
            ) as payload_file_content:
                attributes["payload"].body = json.loads(
                    await payload_file_content.read()
                )

    attributes["type"] = user.type
    attributes["language"] = user.language
    attributes["is_email_verified"] = user.is_email_verified
    attributes["is_msisdn_verified"] = user.is_msisdn_verified
    attributes["force_password_change"] = user.force_password_change

    attributes["permissions"] = await access_control.get_user_permissions_doc(shortname)
    attributes["roles"] = user.roles
    attributes["groups"] = user.groups

    attachments_path = (
        settings.spaces_folder
        / MANAGEMENT_SPACE
        / USERS_SUBPATH
        / ".dm"
        / user.shortname
    )
    user_avatar = await db.get_entry_attachments(
        subpath=f"{USERS_SUBPATH}/{user.shortname}",
        attachments_path=attachments_path,
        branch_name=MANAGEMENT_BRANCH,
        filter_shortnames=["avatar"],
    )

    record = core.Record(
        subpath=USERS_SUBPATH,
        shortname=user.shortname,
        resource_type=core.ResourceType.user,
        attributes=attributes,
        attachments=user_avatar,
    )

    await plugin_manager.after_action(entity.to_event_data(core.ActionType.view))

    return api.Response(status=api.Status.success, records=[record])


@router.post("/profile", response_model=api.Response, response_model_exclude_none=True)
async def update_profile(
    profile: core.Record, shortname=Depends(JWTBearer())
) -> api.Response:
    """Update user profile"""

    profile_user = core.Meta.check_record(
        record=profile, owner_shortname=profile.shortname
    )
    if profile_user.password and not re.match(rgx.PASSWORD, profile_user.password):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="jwtauth",
                code=InternalErrorCode.INVALID_USERNAME_AND_PASS,
                message="Invalid username or password",
            ),
        )

    entity = core.EntityDTO.from_record(profile, MANAGEMENT_SPACE, shortname)

    await plugin_manager.before_action(entity.to_event_data(core.ActionType.update))

    user: core.User = await db.load(entity)

    # old_version_flattend = flatten_dict(user.model_dump())

    if profile_user.password and "old_password" in profile.attributes:
        if not password_hashing.verify_password(
            profile.attributes["old_password"], user.password or ""
        ):
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(
                    type="request",
                    code=InternalErrorCode.UNMATCHED_DATA,
                    message="mismatch with the information provided",
                ),
            )

    # if "force_password_change" in profile.attributes:
    #     user.force_password_change = profile.attributes["force_password_change"]

    separate_payload_data: dict[str, Any] = {}
    if profile_user.password:
        user.password = password_hashing.hash_password(profile_user.password)
        user.force_password_change = False
    if "displayname" in profile.attributes:
        user.displayname = profile_user.displayname
    if "language" in profile.attributes:
        user.language = profile_user.language

    if "confirmation" in profile.attributes:
        result = None
        if profile_user.email:
            result = await operational_repo.find_key(
                f"users:otp:confirmation/email/{profile_user.email}"
            )
        elif profile_user.msisdn:
            result = await operational_repo.find_key(
                f"users:otp:confirmation/msisdn/{profile_user.msisdn}"
            )

        if result is None or result != profile.attributes["confirmation"]:
            raise Exception(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_CONFIRMATION,
                    message="Invalid confirmation code [1]",
                ),
            )

        if profile_user.email:
            user.is_email_verified = True
        elif profile_user.msisdn:
            user.is_msisdn_verified = True
    else:
        await operational_repo.validate_uniqueness(entity, profile.attributes, RequestType.update)
        if "email" in profile.attributes and user.email != profile_user.email:
            user.email = profile_user.email
            user.is_email_verified = False

        if profile_user.msisdn and user.msisdn != profile_user.msisdn:
            user.msisdn = profile_user.msisdn
            user.is_msisdn_verified = False

        if "payload" in profile.attributes and "body" in profile.attributes["payload"]:
            user.payload = core.Payload(
                content_type=ContentType.json,
                schema_shortname=profile_user.payload.schema_shortname,
                body="",
            )
            if profile.attributes["payload"]["body"]:
                separate_payload_data = profile.attributes["payload"]["body"]
                user.payload.body = shortname + ".json"

            if user.payload and separate_payload_data:
                if profile_user.payload.schema_shortname:
                    await validate_payload_with_schema(
                        payload_data=separate_payload_data,
                        space_name=MANAGEMENT_SPACE,
                        branch_name=MANAGEMENT_BRANCH,
                        schema_shortname=str(user.payload.schema_shortname),
                    )

    history_diff = await db.update(entity, user, separate_payload_data)

    await plugin_manager.after_action(
        entity.to_event_data(core.ActionType.update, {"history_diff": history_diff})
    )

    return api.Response(status=api.Status.success)


# cookie_options = {
#    "key": "auth_token",
#    "httponly": True,
#    "secure": True,
#    "samesite": "none",
# }
# "samesite": "lax" }
# samesite="none",
# secure=True,


@router.post(
    "/logout",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def logout(
    response: Response,
    shortname=Depends(JWTBearer()),
) -> api.Response:
    response.set_cookie(
        value="",
        max_age=0,
        key="auth_token",
        httponly=True,
        secure=True,
        samesite="none",
    )

    await remove_redis_active_session(shortname)
    
    entity = core.EntityDTO(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        resource_type=ResourceType.user,
        shortname=shortname,
        user_shortname=shortname,
        
    )

    user: core.User = await db.load(entity)
    
    if user.firebase_token:
        await operational_repo.internal_sys_update_model(entity, user, {"firebase_token": None})

    return api.Response(status=api.Status.success, records=[])


@router.post("/delete", response_model=api.Response, response_model_exclude_none=True)
async def delete_account(shortname=Depends(JWTBearer())) -> api.Response:
    """Delete own user"""
    
    entity = core.EntityDTO(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        resource_type=ResourceType.user,
        user_shortname=shortname,
    )
    await plugin_manager.before_action(entity.to_event_data(core.ActionType.delete))
    
    await db.delete(entity)

    await remove_redis_active_session(shortname)

    await plugin_manager.after_action(entity.to_event_data(core.ActionType.delete))

    return api.Response(status=api.Status.success)


@router.post(
    "/otp-request",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def otp_request(
    user_request: SendOTPRequest,
    skel_accept_language=Header(default=None),
    shortname=Depends(JWTBearer()),
) -> api.Response:
    """Request new OTP"""

    result = user_request.check_fields()
    entity = core.EntityDTO(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        resource_type=ResourceType.user,
        user_shortname=shortname,
    )
    user: core.User = await db.load(entity)
    
    exception = api.Exception(
        status.HTTP_401_UNAUTHORIZED,
        api.Error(
            type="request",
            code=InternalErrorCode.UNMATCHED_DATA,
            message="mismatch with the information provided",
        ),
    )

    # FIXME instead of matching user with user_request we should simply get the data from user?

    if "msisdn" in result:
        if user.msisdn != result["msisdn"]:
            raise exception
        else:
            await send_otp(result["msisdn"], skel_accept_language or "")
    else:
        if user.email != result["email"]:
            raise exception
        await email_send_otp(result["email"], skel_accept_language or "")

    return api.Response(status=api.Status.success)


@router.post(
    "/password-reset-request",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def reset_password(user_request: PasswordResetRequest) -> api.Response:
    result = user_request.check_fields()
    exception = api.Exception(
        status.HTTP_401_UNAUTHORIZED,
        api.Error(
            type="request",
            code=InternalErrorCode.UNMATCHED_DATA,
            message="mismatch with the information provided",
        ),
    )

    key, value = list(result.items())[0]
    user: core.User | None = await access_control.get_user_by_criteria(key, value)
    if user is None:
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="auth",
                code=InternalErrorCode.USERNAME_NOT_EXIST,
                message="This username does not exist",
            ),
        )

    entity = core.EntityDTO(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=user.shortname,
        resource_type=ResourceType.user,
        user_shortname=user.shortname,
    )
    
    user.force_password_change = True

    await plugin_manager.before_action(entity.to_event_data(core.ActionType.update))

    await db.update(entity, user)

    await plugin_manager.after_action(entity.to_event_data(core.ActionType.update))

    reset_password_message = "Reset password via this link: {link}, This link can be used once and within the next 48 hours."

    if "msisdn" in result:
        if not user.msisdn or user.msisdn != result["msisdn"]:
            raise exception
        token = await operational_repo.store_user_invitation_token(user, "SMS")
        if not token:
            raise exception
        shortened_link = await operational_repo.url_shortener(token)
        await send_sms(
            msisdn=user.msisdn,
            message=reset_password_message.replace("{link}", shortened_link),
        )
    else:
        if not user.email or user.email != result["email"]:
            raise exception
        token = await operational_repo.store_user_invitation_token(user, "EMAIL")
        if not token:
            raise exception

        shortened_link = await operational_repo.url_shortener(token)
        await send_email(
            from_address=settings.email_sender,
            to_address=user.email,
            message=reset_password_message.replace("{link}", shortened_link),
            subject="Reset password",
        )
    return api.Response(status=api.Status.success)


@router.post(
    "/otp-confirm",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def confirm_otp(
    user_request: ConfirmOTPRequest, user=Depends(JWTBearer())
) -> api.Response:
    """Confirm OTP"""

    result = user_request.check_fields()
    key = ""
    if "msisdn" in result:
        key = f"middleware:otp:otps/{result['msisdn']}"
    elif "email" in result:
        key = f"middleware:otp:otps/{result['email']}"

    code = await operational_repo.find_key(key)

    if not code:
        raise Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="OTP",
                code=InternalErrorCode.OTP_EXPIRED,
                message="Expired OTP",
            ),
        )

    if code != user_request.code:
        raise Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="OTP",
                code=InternalErrorCode.OTP_INVALID,
                message="Invalid OTP",
            ),
        )

    confirmation = gen_alphanumeric()
    data: core.Record = core.Record(
        resource_type=ResourceType.user,
        subpath="users",
        attributes={"confirmation": confirmation},
        shortname=user,
    )

    if "msisdn" in result:
        key = f"users:otp:confirmation/msisdn/{user_request.msisdn}"
        data.attributes["msisdn"] = user_request.msisdn
    else:
        key = f"users:otp:confirmation/email/{user_request.email}"
        data.attributes["email"] = user_request.email

    await operational_repo.set_key(key, confirmation)

    response = await update_profile(data, shortname=user)

    if response.status == api.Status.success:
        return api.Response(status=api.Status.success, records=[])
    else:
        raise Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="OTP",
                code=InternalErrorCode.OTP_FAILED,
                message=response.error.message if response.error else "Internal error",
            ),
        )


@router.post("/reset", response_model=api.Response, response_model_exclude_none=True)
async def user_reset(
    shortname: str = Body(
        ..., pattern=rgx.SHORTNAME, embed=True, examples=["john_doo"]
    ),
    logged_user=Depends(JWTBearer()),
) -> api.Response:
    
    entity = core.EntityDTO(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        resource_type=ResourceType.user,
        user_shortname=logged_user,
    )

    user: core.User = await db.load(entity)
    
    if not await access_control.check_access(
        entity=entity,
        meta=user,
        action_type=ActionType.update,
    ):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=InternalErrorCode.NOT_ALLOWED,
                message="You don't have permission to this action",
            ),
        )

    if not user.force_password_change:
        await operational_repo.internal_sys_update_model(entity, user, {"force_password_change": True})

    sms_link = None
    email_link = None

    if user.msisdn and not user.is_msisdn_verified:
        token = await operational_repo.store_user_invitation_token(user, "SMS")
        if token:
            sms_link = await operational_repo.url_shortener(token)
            await send_sms(
                msisdn=user.msisdn,
                message=languages[user.language]["invitation_message"].replace(
                    "{link}", sms_link
                ),
            )
    if user.email and not user.is_email_verified:
        token = await operational_repo.store_user_invitation_token(user, "SMS")
        if token:
            email_link = await operational_repo.url_shortener(token)
            await send_email(
                from_address=settings.email_sender,
                to_address=user.email,
                message=generate_email_from_template(
                    "activation",
                    {
                        "link": email_link,
                        "name": user.displayname.en if user.displayname else "",
                        "shortname": user.shortname,
                        "msisdn": user.msisdn,
                    },
                ),
                subject=generate_subject("activation"),
            )

    return api.Response(
        status=api.Status.success,
        attributes={"sms_sent": bool(sms_link), "email_sent": bool(email_link)},
    )


@router.post(
    "/validate_password",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def validate_password(
    password: str, shortname=Depends(JWTBearer())
) -> api.Response:
    
    entity = core.EntityDTO(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        resource_type=ResourceType.user,
        user_shortname=shortname,
    )
    
    user: core.User = await db.load(entity)
    
    if password_hashing.verify_password(password, user.password or ""):
        return api.Response(status=api.Status.success)
    else:
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="jwtauth",
                code=InternalErrorCode.PASSWORD_NOT_VALIDATED,
                message="Password dose not match",
            ),
        )


async def process_user_login(
    user: core.User,
    response: Response,
    user_updates: dict = {},
    firebase_token: str | None = None,
) -> core.Record:
    access_token = await sign_jwt(
        {"username": user.shortname}, settings.jwt_access_expires
    )

    response.set_cookie(
        value=access_token,
        max_age=settings.jwt_access_expires,
        key="auth_token",
        httponly=True,
        secure=True,
        samesite="none",
    )
    record = core.Record(
        resource_type=core.ResourceType.user,
        subpath="users",
        shortname=user.shortname,
        attributes={
            "access_token": access_token,
            "type": user.type,
        },
    )
    entity = core.EntityDTO.from_record(record, MANAGEMENT_SPACE, user.shortname)
    if user.displayname:
        record.attributes["displayname"] = user.displayname

    if firebase_token:
        user_updates["firebase_token"] = firebase_token

    if user_updates:
        await operational_repo.internal_sys_update_model(entity, user, user_updates)

    return record


if settings.social_login_allowed:

    @router.post("/google/login")
    async def google_profile(
        response: Response,
        access_token: str = Body(default=...),
        firebase_token: str = Body(default=None),
        google_sso: GoogleSSO = Depends(get_google_sso),
    ):
        user_model = await social_login(access_token, google_sso, "google")

        record = await process_user_login(
            user=user_model, response=response, firebase_token=firebase_token
        )

        return api.Response(status=api.Status.success, records=[record])

    @router.post("/facebook/login")
    async def facebook_login(
        response: Response,
        access_token: str = Body(default=...),
        firebase_token: str = Body(default=None),
        facebook_sso: FacebookSSO = Depends(get_facebook_sso),
    ):
        user_model = await social_login(access_token, facebook_sso, "facebook")

        record = await process_user_login(
            user=user_model, response=response, firebase_token=firebase_token
        )

        return api.Response(status=api.Status.success, records=[record])

    async def social_login(access_token: str, sso: SSOBase, provider: str) -> core.User:
        async with AsyncRequest() as session:
            user_profile_endpoint = await sso.userinfo_endpoint
            if not user_profile_endpoint:
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="auth",
                        code=InternalErrorCode.INVALID_DATA,
                        message="Misconfigured provider",
                    ),
                )
            response = await session.get(
                user_profile_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status != 200:
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="auth",
                        code=InternalErrorCode.INVALID_DATA,
                        message="Invalid access token",
                    ),
                )
            content = await response.json()
            provider_user = await sso.openid_from_response(content)

        search_res: tuple[int, list[dict[str, Any]]] = (
            await operational_repo.search(
                api.Query(
                    type=QueryType.search,
                    space_name=MANAGEMENT_SPACE,
                    branch_name=MANAGEMENT_BRANCH,
                    subpath=USERS_SUBPATH,
                    search=f"@{provider}_id:{provider_user.id}",
                    limit=1,
                    offset=0
                )
            )
        )

        if not search_res or search_res[0] == 0:
            uuid = uuid4()
            shortname = str(uuid)[:8]
            user_model = core.User(
                shortname=shortname,
                owner_shortname=shortname,
                displayname=core.Translation(
                    en=f"{provider_user.first_name} provider_user.last_name"
                ),
                email=provider_user.email,
                is_email_verified=True,
                social_avatar_url=provider_user.picture,
            )
            setattr(user_model, f"{provider}_id", provider_user.id)

            await db.create(
                entity=core.EntityDTO(
                    space_name=MANAGEMENT_SPACE,
                    subpath=USERS_SUBPATH,
                    shortname=shortname,
                    resource_type=ResourceType.user
                ),
                meta=user_model
            )

        else:
            user_record = await operational_repo.db_doc_to_record(
                space_name=MANAGEMENT_SPACE,
                db_entry=search_res[1][0],
                retrieve_json_payload=True,
            )
            user_model = core.User.from_record(
                user_record,
                owner_shortname=(search_res[1][0]).get("owner_shortname", ""),
            )

        return user_model
