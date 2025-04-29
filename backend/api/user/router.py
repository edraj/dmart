""" Session Apis """
import json
import re
from pathlib import Path
from uuid import uuid4
import aiofiles
from utils.async_request import AsyncRequest
from utils.generate_email import generate_subject
from utils.generate_email import generate_email_from_template
from fastapi import APIRouter, Body, Query, status, Depends, Response, Header
import models.api as api
import models.core as core
from models.enums import ActionType, RequestType, ResourceType, ContentType
from data_adapters.adapter import data_adapter as db
from utils.access_control import access_control
from utils.helpers import flatten_dict
from utils.internal_error_code import InternalErrorCode
from utils.jwt import JWTBearer, sign_jwt, decode_jwt
from typing import Any, Dict
from utils.settings import settings
import utils.repository as repository
from utils.plugin_manager import plugin_manager
import utils.password_hashing as password_hashing
from models.api import Error, Exception, Status
from utils.social_sso import get_facebook_sso, get_google_sso
from .service import (
    gen_alphanumeric,
    get_otp_key,
    send_email,
    send_sms,
    send_otp,
    email_send_otp,
    get_shortname_from_identifier,
    check_user_validation,
    set_user_profile,
    update_user_payload, 
    get_otp_confirmation_email_or_msisdn,
)
from .model.requests import (
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
from fastapi.logger import logger
from data_adapters.file.adapter_helpers import get_record_from_redis_doc

router = APIRouter()

MANAGEMENT_SPACE: str = settings.management_space
USERS_SUBPATH: str = "users"


@router.get(
    "/check-existing", response_model=api.Response, response_model_exclude_none=True
)
async def check_existing_user_fields(
    _=Depends(JWTBearer()),
    shortname: str | None = Query(
        default=None, pattern=rgx.SHORTNAME, examples=["john_doo"]),
    msisdn: str | None = Query(
        default=None, pattern=rgx.EXTENDED_MSISDN, examples=["7777778110"]),
    email: str | None = Query(default=None, pattern=rgx.EMAIL, examples=[
                              "john_doo@mail.com"]),
):
    unique_fields = {"shortname": shortname,
                     "msisdn": msisdn, "email_unescaped": email}

    search_str = f"@subpath:{USERS_SUBPATH}"
    redis_escape_chars = str.maketrans(
        {".": r"\.", "@": r"\@", ":": r"\:", "/": r"\/", "-": r"\-", " ": r"\ "}
    )

    attributes = await db.check_uniqueness(unique_fields, search_str, redis_escape_chars)
    return api.Response(status=api.Status.success, attributes=attributes)


@router.post("/create", response_model=api.Response, response_model_exclude_none=True)
async def create_user(response: Response, record: core.Record) -> api.Response:
    """Register a new user by invitation"""
    if not settings.is_registrable:
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(type="create", code=50,
                            message="Register API is disabled"),
        )

    validation_message: str | None = None
    if "email" not in record.attributes and "msisdn" not in record.attributes:
        validation_message = "Email or MSISDN is required"
        
    if record.attributes.get("email") and not record.attributes.get("email_otp"):
        validation_message = "Email OTP is required"

    if record.attributes.get("msisdn") and not record.attributes.get("msisdn_otp"):
        validation_message = "MSISDN OTP is required"

    if record.attributes.get("password") and not re.match(rgx.PASSWORD, record.attributes["password"]):
        validation_message = "password dose not match required rules"
    
    if validation_message:
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(type="create", code=50,
                            message=validation_message),
        )
    await db.validate_uniqueness(MANAGEMENT_SPACE, record, RequestType.create, "dmart")

    await plugin_manager.before_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            shortname=record.shortname,
            action_type=core.ActionType.create,
            resource_type=ResourceType.user,
            user_shortname=record.shortname,
        )
    )
    
    record.resource_type = ResourceType.user
    user = core.User.from_record(
        record=record,
        owner_shortname="dmart"
    )
    separate_payload_data: str | dict[str, Any] = {}
    if record.attributes.get("payload", {}).get("body"):
        schema_shortname = getattr(user.payload, "schema_shortname", None)
        user.payload = core.Payload(
            content_type=ContentType.json,
            schema_shortname=schema_shortname,
            body=record.attributes["payload"].get("body", ""),
        )
        if user.payload:
            separate_payload_data = user.payload.body # type: ignore
            user.payload.body = record.shortname + ".json"

        if user.payload and separate_payload_data:
            if not isinstance(separate_payload_data, str) and not isinstance(
                separate_payload_data, Path
            ):
                if user.payload.schema_shortname:
                    await db.validate_payload_with_schema(
                        payload_data=separate_payload_data,
                        space_name=MANAGEMENT_SPACE,
                        schema_shortname=user.payload.schema_shortname,
                    )
                    
    if user.msisdn:
        is_valid_otp = await verify_user(ConfirmOTPRequest(
            msisdn=record.attributes.get("msisdn"),
            email=None,
            code=record.attributes.get("msisdn_otp", "")
        ))
        if not is_valid_otp:
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(type="create", code=50,
                                message="Invalid MSISDN OTP"),
            )
        user.is_msisdn_verified = True
    if user.email:
        is_valid_otp = await verify_user(ConfirmOTPRequest(
            email=record.attributes.get("email"),
            msisdn=None,
            code=record.attributes.get("email_otp", "")
        ))
        if not is_valid_otp:
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(type="create", code=50,
                                message="Invalid Email OTP"),
            )
        user.is_email_verified = True
        
    user.is_active = True
                
    await db.create(MANAGEMENT_SPACE, USERS_SUBPATH, user)
    if isinstance(separate_payload_data, dict) and separate_payload_data:
        await db.update_payload(
            MANAGEMENT_SPACE, USERS_SUBPATH, user, separate_payload_data, user.owner_shortname
        )
        
    response_record = await process_user_login(user, response, {})
    
    await plugin_manager.after_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            shortname=record.shortname,
            action_type=core.ActionType.create,
            resource_type=ResourceType.user,
            user_shortname=record.shortname,
        )
    )

    return api.Response(
        status=api.Status.success,
        records=[
            core.Record(
                shortname=user.shortname,
                subpath=USERS_SUBPATH,
                resource_type=ResourceType.user,
                attributes=response_record.attributes
            )
        ]
    )
  
async def verify_user(user_request: ConfirmOTPRequest):
    user_identifier = user_request.check_fields()
    key = get_otp_key(user_identifier)
    code = await db.get_otp(key)
    if not code or code != user_request.code:
        return False
    
    return True  
   
@router.post(
    "/login",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def login(response: Response, request: UserLoginRequest) -> api.Response:
    """Login and generate refresh token"""
    shortname: str | None = None
    user = None
    user_updates: dict[str, Any] = {}
    identifier: Dict[str, str] | None = request.check_fields()
    try:
        if request.invitation:
            invitation_token = await db.get_invitation(request.invitation)
            if invitation_token is None:
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="jwtauth",
                        code=InternalErrorCode.INVALID_INVITATION,
                        message="Expired or invalid invitation",
                    ),
                )

            data = decode_jwt(request.invitation)
            shortname = data.get("shortname", None)
            if (shortname is None) or (request.shortname is not None and request.shortname != shortname):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="jwtauth",
                        code=InternalErrorCode.INVALID_INVITATION,
                        message="Invalid invitation or data provided",
                    ),
                )

            user = await db.load(
                space_name=MANAGEMENT_SPACE,
                subpath=USERS_SUBPATH,
                shortname=shortname,
                class_type=core.User,
                user_shortname=shortname,
            )
            if (
                request.shortname != user.shortname
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

            await db.delete_invitation(request.invitation)
            await db.delete_url_shortner_by_token(request.invitation)
            user_updates["force_password_change"] = True

            user_updates = check_user_validation(user, data, user_updates, invitation_token)

        else:
            if identifier is None:
                raise api.Exception(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    api.Error(
                        type="request", code=InternalErrorCode.INVALID_IDENTIFIER, message="Invalid identifier [2]"
                    ),
                )

            if "shortname" in identifier:
                shortname = identifier["shortname"]
            else:
                _list = list(identifier.items())
                if len(_list) != 1:
                    raise api.Exception(
                        status.HTTP_422_UNPROCESSABLE_ENTITY,
                        api.Error(
                            type="request",
                            code=InternalErrorCode.INVALID_IDENTIFIER,
                            message="Only one valid identifier is allowed!",
                        ),
                    )

                key, value = _list[0]
                shortname = await get_shortname_from_identifier(key, value)
                if shortname is None:
                    raise api.Exception(
                        status.HTTP_401_UNAUTHORIZED,
                        api.Error(
                            type="auth",
                            code=InternalErrorCode.INVALID_USERNAME_AND_PASS,
                            message="Invalid username or password [1]",
                        ),
                    )
            user = await db.load(
                space_name=MANAGEMENT_SPACE,
                subpath=USERS_SUBPATH,
                shortname=shortname,
                class_type=core.User,
                user_shortname=shortname,
            )
        
        is_password_valid = password_hashing.verify_password(
            request.password or "", user.password or ""
        )
        if (
            user
            and user.is_active
            and (
                request.invitation
                or is_password_valid
            )
        ):
            await db.clear_failed_password_attempts(shortname)
            
            record = await process_user_login(user, response, user_updates, request.firebase_token)
            await reset_failed_login_attempt(user)
            await plugin_manager.after_action(
                core.Event(
                    space_name=MANAGEMENT_SPACE,
                    subpath=USERS_SUBPATH,
                    shortname=shortname,
                    action_type=core.ActionType.update,
                    resource_type=ResourceType.user,
                    user_shortname=shortname,
                )
            )
            return api.Response(status=api.Status.success, records=[record])
        # Check if user entered a wrong password
        if not is_password_valid:
            await handle_failed_login_attempt(user)
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(type="auth", code=InternalErrorCode.INVALID_USERNAME_AND_PASS,
                      message="Invalid username or password [2]"),
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

    await plugin_manager.before_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            shortname=shortname,
            action_type=core.ActionType.view,
            resource_type=ResourceType.user,
            user_shortname=shortname,
        )
    )

    user = await db.load(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        class_type=core.User,
        user_shortname=shortname,
    )
    attributes: dict[str, Any] = {}
    if user.email:
        attributes["email"] = user.email

    if user.displayname:
        attributes["displayname"] = user.displayname

    if user.description:
        attributes["description"] = user.description

    if user.msisdn:
        attributes["msisdn"] = user.msisdn

    if user.payload:
        attributes["payload"] = user.payload
        if settings.active_data_db == 'file':
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

    attributes["permissions"] = await db.get_user_permissions(shortname)
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
        filter_shortnames=["avatar"],
    )

    record = core.Record(
        subpath=USERS_SUBPATH,
        shortname=user.shortname,
        resource_type=core.ResourceType.user,
        attributes=attributes,
        attachments=user_avatar,
    )

    await plugin_manager.after_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            shortname=shortname,
            action_type=core.ActionType.view,
            resource_type=ResourceType.user,
            user_shortname=shortname,
        )
    )

    return api.Response(status=api.Status.success, records=[record])


@router.post("/profile", response_model=api.Response, response_model_exclude_none=True)
async def update_profile(
    profile: core.Record, shortname=Depends(JWTBearer())
) -> api.Response:
    """Update user profile"""
    profile_user = core.Meta.check_record(
        record=profile, owner_shortname=profile.shortname
    )
    
    if profile.attributes.get("email") and not profile.attributes.get("email_otp"):
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(type="create", code=50,
                            message="Email OTP is required to update your email"),
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

    await plugin_manager.before_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            shortname=shortname,
            action_type=core.ActionType.update,
            resource_type=ResourceType.user,
            user_shortname=shortname,
        )
    )

    user = await db.load(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        class_type=core.User,
        user_shortname=shortname,
    )

    old_version_flattened = flatten_dict(user.model_dump())

    if profile_user.password and "old_password" in profile.attributes:
        if not password_hashing.verify_password(
            profile.attributes["old_password"], user.password or ""
        ):
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(type="request", code=InternalErrorCode.UNMATCHED_DATA,
                            message="mismatch with the information provided"),
            )

    # if "force_password_change" in profile.attributes:
    #     user.force_password_change = profile.attributes["force_password_change"]

    user = await set_user_profile(profile, profile_user, user)

    if "confirmation" in profile.attributes:
        result = await get_otp_confirmation_email_or_msisdn(profile_user)

        if result is None or result != profile.attributes["confirmation"]:
            raise Exception(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                api.Error(type="request", code=InternalErrorCode.INVALID_CONFIRMATION,
                            message="Invalid confirmation code [1]"),
            )

        if profile_user.email:
            user.is_email_verified = True
        elif profile_user.msisdn:
            user.is_msisdn_verified = True
    else:
        await db.validate_uniqueness(MANAGEMENT_SPACE, profile, RequestType.update, shortname)
        if "email" in profile.attributes and user.email != profile_user.email:
            is_valid_otp = await verify_user(ConfirmOTPRequest(
                email=profile.attributes.get("email"),
                msisdn=None,
                code=profile.attributes.get("email_otp", "")
            ))
            if not is_valid_otp:
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(type="create", code=50,
                                    message="Invalid Email OTP"),
                )
            user.email = profile_user.email
            user.is_email_verified = True

        if profile_user.msisdn and user.msisdn != profile_user.msisdn:
            user.msisdn = profile_user.msisdn
            user.is_msisdn_verified = False

        if "payload" in profile.attributes and "body" in profile.attributes["payload"]:
            await update_user_payload(profile, profile_user, user, shortname)

    if user.is_active and profile.attributes.get("is_active", None) is not None:
        if not profile.attributes.get("is_active"):
            await db.remove_user_session(user.shortname)

    history_diff = await db.update(
        MANAGEMENT_SPACE,
        USERS_SUBPATH,
        user,
        old_version_flattened,
        flatten_dict(user.model_dump()),
        list(profile.attributes.keys()),
        shortname,
        retrieve_lock_status=profile.retrieve_lock_status,
    )

    await plugin_manager.after_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            shortname=shortname,
            action_type=core.ActionType.update,
            resource_type=ResourceType.user,
            user_shortname=shortname,
            attributes={"history_diff": history_diff},
        )
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
    response.set_cookie(value="", max_age=0, key="auth_token",
                        httponly=True, secure=True, samesite="none")

    await db.remove_user_session(shortname)

    user = await db.load(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            shortname=shortname,
            class_type=core.User,
            user_shortname=shortname,
        )
    if user.firebase_token:
        await db.internal_sys_update_model(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            meta=user,
            updates={
                "firebase_token": None
            }

        )

    return api.Response(status=api.Status.success, records=[])


@router.post("/delete", response_model=api.Response, response_model_exclude_none=True)
async def delete_account(shortname=Depends(JWTBearer())) -> api.Response:
    """Delete own user"""
    await plugin_manager.before_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            shortname=shortname,
            action_type=core.ActionType.delete,
            resource_type=ResourceType.user,
            user_shortname=shortname,
        )
    )
    user = await db.load(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        class_type=core.User,
        user_shortname=shortname,
    )
    await db.delete(MANAGEMENT_SPACE, USERS_SUBPATH, user, shortname)

    await db.remove_user_session(shortname)

    await plugin_manager.after_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            shortname=shortname,
            action_type=core.ActionType.delete,
            resource_type=ResourceType.user,
            user_shortname=shortname,
            attributes={"entry":user}
        )
    )

    return api.Response(status=api.Status.success)


@router.post(
    "/otp-request",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def otp_request(
    user_request: SendOTPRequest,
    skel_accept_language=Header(default=None)
) -> api.Response:
    """Request new OTP"""
    
    user_identifier = user_request.check_fields()
    otp_key = get_otp_key(user_identifier)
    last_otp_since = await db.otp_created_since(otp_key)
    
    if (last_otp_since and last_otp_since < settings.allow_otp_resend_after):
        raise api.Exception(
        status.HTTP_403_FORBIDDEN,
        api.Error(
            type="request",
            code=InternalErrorCode.OTP_RESEND_BLOCKED,
            message=f"Resend OTP is allowed after {int(settings.allow_otp_resend_after - last_otp_since)} seconds",
        ),
    )

    if "msisdn" in user_identifier:
        await send_otp(user_identifier["msisdn"], skel_accept_language or "")
    elif "email" in user_identifier:
        await email_send_otp(user_identifier["email"], skel_accept_language or "")

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
    shortname = await db.get_user_by_criteria(key, value)
    if shortname is None:
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="auth",
                code=InternalErrorCode.USERNAME_NOT_EXIST,
                message="This username does not exist",
            ),
        )

    user = await db.load(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        class_type=core.User,
        user_shortname=shortname,
    )

    """
    # Do not set the "force_password_change" flag right away

    old_version_flattend = flatten_dict(user.model_dump())
    user.force_password_change = True

    await plugin_manager.before_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            shortname=shortname,
            action_type=core.ActionType.update,
            resource_type=ResourceType.user,
            user_shortname=shortname,
        )
    )

    await db.update(
        MANAGEMENT_SPACE,
        USERS_SUBPATH,
        user,
        old_version_flattend,
        flatten_dict(user.model_dump()),
        ["force_password_change"],
        shortname,
    )

    await plugin_manager.after_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            shortname=shortname,
            action_type=core.ActionType.update,
            resource_type=ResourceType.user,
            user_shortname=shortname,
        )
    )
    """

    reset_password_message = "Reset password via this link: {link}, This link can be used once and within the next 48 hours."

    if "msisdn" in result or "shortname" in result:
        if not user.msisdn or ("msisdn" in result and user.msisdn != result["msisdn"]):
            raise exception
        token = await repository.store_user_invitation_token(
            user, "SMS"
        )
        if not token:
            raise exception
        shortened_link = await repository.url_shortner(token)
        await send_sms(
            msisdn=user.msisdn,
            message=reset_password_message.replace("{link}", shortened_link),
        )
    else:
        if not user.email or user.email != result["email"]:
            raise exception
        token = await repository.store_user_invitation_token(
            user, "EMAIL"
        )
        if not token:
            raise exception

        shortened_link = await repository.url_shortner(token)
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
    key = get_otp_key(result)

    code = await db.get_otp(key)
    if not code or code != user_request.code:
        raise Exception(
            status.HTTP_400_BAD_REQUEST,
            Error(
                type="OTP",
                code=InternalErrorCode.OTP_EXPIRED,
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

    await db.save_otp(key, confirmation)

    response = await update_profile(data, shortname=user)

    if response.status == Status.success:
        return api.Response(status=api.Status.success, records=[])
    else:
        raise Exception(
            status.HTTP_400_BAD_REQUEST,
            Error(
                type="OTP",
                code=InternalErrorCode.OTP_FAILED,
                message=response.error.message
                if response.error
                else "Internal error",
            ),
        )


@router.post("/reset", response_model=api.Response, response_model_exclude_none=True)
async def user_reset(
    shortname: str = Body(..., pattern=rgx.SHORTNAME,
                          embed=True, examples=["john_doo"]),
    logged_user=Depends(JWTBearer()),
) -> api.Response:

    user = await db.load(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            shortname=shortname,
            class_type=core.User,
            user_shortname=shortname,
        )
    if not await access_control.check_access(
        user_shortname=logged_user,
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        resource_type=ResourceType.user,
        action_type=ActionType.update,
        resource_is_active=user.is_active,
        resource_owner_shortname=user.owner_shortname,
        resource_owner_group=user.owner_group_shortname,
        entry_shortname=user.shortname,
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
        await db.internal_sys_update_model(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            meta=user,
            updates={"force_password_change": True}
        )

    sms_link = None
    email_link = None

    if user.msisdn and not user.is_msisdn_verified:
        token = await repository.store_user_invitation_token(
            user, "SMS"
        )
        if token:
            sms_link = await repository.url_shortner(token)
            await send_sms(
                msisdn=user.msisdn,
                message=languages[
                    user.language
                ]["reset_message"].replace(
                    "{link}",
                    sms_link
                ),
            )
    if user.email and not user.is_email_verified:
        token = await repository.store_user_invitation_token(
            user, "SMS"
        )
        if token:
            email_link = await repository.url_shortner(token)
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
        attributes={"sms_sent": bool(sms_link), "email_sent": bool(email_link)}
    )


@router.post(
    "/validate_password",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def validate_password(
    password: str, shortname=Depends(JWTBearer())
) -> api.Response:
    """Validate Password"""
    user = await db.load(
        MANAGEMENT_SPACE, USERS_SUBPATH, shortname, core.User, shortname
    )
    if user and password_hashing.verify_password(password, user.password or ""):
        return api.Response(status=api.Status.success)
    else:
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(type="jwtauth", code=InternalErrorCode.PASSWORD_NOT_VALIDATED,
                      message="Password dose not match"),
        )



async def process_user_login(
    user: core.User, 
    response: Response,
    user_updates: dict = {}, 
    firebase_token: str | None = None
) -> core.Record:
    access_token = await sign_jwt(
        {"shortname": user.shortname, "type": user.type}, settings.jwt_access_expires
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
    if user.displayname:
        record.attributes["displayname"] = user.displayname

    if firebase_token:
        user_updates["firebase_token"] = firebase_token

    if user_updates:
        await db.internal_sys_update_model(
            space_name=MANAGEMENT_SPACE,
            subpath=USERS_SUBPATH,
            meta=user,
            updates=user_updates,
            sync_redis=False,
        )
        
    return record


async def reset_failed_login_attempt(user: core.User):
    await db.set_failed_password_attempt_count(user.shortname, 0)

async def handle_failed_login_attempt(user: core.User):
    failed_login_attempts_count: int = await db.get_failed_password_attempt_count(user.shortname)

    # Increment the failed login attempts counter
    failed_login_attempts_count += 1

    if failed_login_attempts_count >= settings.max_failed_login_attempts:
        # If the user reach the configured limit, lock the user by setting the is_active to false
        if user.is_active:
            await db.set_failed_password_attempt_count(user.shortname, failed_login_attempts_count)

            logger.info(f"User {user.shortname} reached the maximum failed login attempts ({settings.max_failed_login_attempts}) disabling the user")

            old_version_flattend = flatten_dict(user.model_dump())
            user.is_active = False

            await db.remove_user_session(user.shortname)

            await db.update(
                MANAGEMENT_SPACE,
                USERS_SUBPATH,
                user,
                old_version_flattend,
                flatten_dict(user.model_dump()),
                ["is_active"],
                user.shortname,
            )

            await plugin_manager.after_action(
                core.Event(
                    space_name=MANAGEMENT_SPACE,
                    subpath=USERS_SUBPATH,
                    shortname=user.shortname,
                    action_type=core.ActionType.update,
                    resource_type=ResourceType.user,
                    user_shortname=user.shortname,
                )
            )
    else:
        # Count until the failed attempts reach the limit
        await db.set_failed_password_attempt_count(user.shortname, failed_login_attempts_count)


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
            user=user_model,
            response=response,
            firebase_token=firebase_token
        )

        return api.Response(status=api.Status.success, records=[record])

    @router.post("/facebook/login")
    async def facebook_login(
        response: Response,
        access_token: str = Body(default=...),
        firebase_token: str = Body(default=None),
        facebook_sso: FacebookSSO = Depends(get_facebook_sso),
        retrieve_lock_status: bool = Body(default=False),
    ):
        user_model = await social_login(access_token, facebook_sso, "facebook", retrieve_lock_status)

        record = await process_user_login(
            user=user_model,
            response=response,
            firebase_token=firebase_token
        )

        return api.Response(status=api.Status.success, records=[record])


    async def social_login(access_token: str, sso: SSOBase, provider: str, retrieve_lock_status: bool = False) -> core.User:
        async with AsyncRequest() as session:
            user_profile_endpoint = await sso.userinfo_endpoint
            if not user_profile_endpoint:
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(type="auth", code=InternalErrorCode.INVALID_DATA, message="Misconfigured provider"),
                )
            response = await session.get(
                user_profile_endpoint, headers={"Authorization": f"Bearer {access_token}"}
            )
            if response.status != 200:
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(type="auth", code=InternalErrorCode.INVALID_DATA, message="Invalid access token"),
                )
            content = await response.json()
            provider_user = await sso.openid_from_response(content)

        from data_adapters.file.redis_services import RedisServices
        async with RedisServices() as redis_man:
            redis_search_res = await redis_man.search(
                space_name=MANAGEMENT_SPACE,
                search=f"@{provider}_id:{provider_user.id}",
                limit=1,
                offset=0,
                filters={},
            )

        if not redis_search_res or redis_search_res["total"] == 0:
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

            await db.create(MANAGEMENT_SPACE, USERS_SUBPATH, user_model)

        else:
            redis_doc_dict = json.loads(redis_search_res["data"][0])
            user_record = await get_record_from_redis_doc(
                db,
                space_name=MANAGEMENT_SPACE,
                doc=redis_doc_dict,
                retrieve_json_payload=True,
                retrieve_lock_status=retrieve_lock_status,
            )
            user_model = core.User.from_record(user_record, owner_shortname=redis_doc_dict.get("owner_shortname"))
            
        return user_model
