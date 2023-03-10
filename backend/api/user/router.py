""" Session Apis """
import json
import re
import uuid
import aiofiles
from fastapi import APIRouter, Body, status, Depends, Response, Header
import models.api as api
import models.core as core
from models.enums import RequestType, ResourceType, ContentType
from utils.custom_validations import validate_uniqueness
import utils.db as db
from utils.access_control import access_control
from utils.helpers import flatten_dict
from utils.custom_validations import validate_payload_with_schema
from utils.jwt import JWTBearer, sign_jwt, decode_jwt
from typing import Any
from utils.settings import settings
import utils.repository as repository
from utils.plugins import plugin_manager
import utils.password_hashing as password_hashing
from utils.redis_services import RedisServices
from models.api import Error, Exception, Status
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
from pathlib import Path


router = APIRouter()

MANAGEMENT_SPACE: str = settings.management_space
MANAGEMENT_BRANCH: str = settings.management_space_branch
USERS_SUBPATH: str = "users"


@router.post("/create", response_model=api.Response, response_model_exclude_none=True)
async def create_user(record: core.Record) -> api.Response:
    """Register a new user by invitation"""
    if not record.attributes:
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(type="create", code=50, message="Empty attributes"),
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

    await plugin_manager.before_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            branch_name=MANAGEMENT_BRANCH,
            subpath=USERS_SUBPATH,
            shortname=record.shortname,
            action_type=core.ActionType.create,
            resource_type=ResourceType.user,
            user_shortname=record.shortname,
        )
    )

    user = core.User.from_record(record=record, owner_shortname=record.shortname)
    await validate_uniqueness(MANAGEMENT_SPACE, record)

    separate_payload_data = {}
    if "payload" in record.attributes and "body" in record.attributes["payload"]:
        schema_shortname = getattr(user.payload, "schema_shortname", None)
        user.payload = core.Payload(
            content_type=ContentType.json,
            schema_shortname=schema_shortname,
            body="",
        )
        if user.payload:
            separate_payload_data = user.payload.body
            user.payload.body = record.shortname + ".json"

        if user.payload and separate_payload_data:
            if not isinstance(separate_payload_data, str) and not isinstance(
                separate_payload_data, Path
            ):
                if user.payload.schema_shortname:
                    await validate_payload_with_schema(
                        payload_data=separate_payload_data,
                        space_name=MANAGEMENT_SPACE,
                        branch_name=MANAGEMENT_BRANCH,
                        schema_shortname=user.payload.schema_shortname,
                    )

    await db.create(MANAGEMENT_SPACE, USERS_SUBPATH, user, MANAGEMENT_BRANCH)

    if separate_payload_data:
        await db.save_payload_from_json(
            MANAGEMENT_SPACE,
            USERS_SUBPATH,
            user,
            separate_payload_data,  # type: ignore
            MANAGEMENT_BRANCH,
        )
    async with RedisServices() as redis_services:
        await redis_services.save_meta_doc(
            space_name=MANAGEMENT_SPACE,
            branch_name=MANAGEMENT_BRANCH,
            subpath=USERS_SUBPATH,
            meta=user,
        )

    await plugin_manager.after_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            branch_name=MANAGEMENT_BRANCH,
            subpath=USERS_SUBPATH,
            shortname=record.shortname,
            action_type=core.ActionType.create,
            resource_type=ResourceType.user,
            user_shortname=record.shortname,
        )
    )

    return api.Response(status=api.Status.success)


@router.get("/profile", response_model=api.Response, response_model_exclude_none=True)
async def get_profile(shortname=Depends(JWTBearer())) -> api.Response:

    await plugin_manager.before_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            branch_name=MANAGEMENT_BRANCH,
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
        branch_name=MANAGEMENT_BRANCH,
    )
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
            and (path / user.payload.body).is_file()  # type: ignore
        ):
            async with aiofiles.open(
                path / user.payload.body, "r"  # type: ignore
            ) as payload_file_content:
                attributes["payload"].body = json.loads(
                    await payload_file_content.read()
                )

    attributes["type"] = user.type
    attributes["language"] = user.language
    attributes["is_email_verified"] = user.is_email_verified
    attributes["is_msisdn_verified"] = user.is_msisdn_verified
    attributes["force_password_change"] = user.force_password_change

    attributes["permissions"] = await access_control.get_user_premissions(shortname)
    attributes["roles"] = user.roles
    attributes["groups"] = user.groups

    attachments_path = (
        settings.spaces_folder
        / MANAGEMENT_SPACE
        / USERS_SUBPATH
        / ".dm"
        / user.shortname
    )
    user_avatar = await repository.get_entry_attachments(
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

    await plugin_manager.after_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            branch_name=MANAGEMENT_BRANCH,
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
    if profile_user.password and not re.match(rgx.PASSWORD, profile_user.password):
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="jwtauth",
                code=14,
                message="password dose not match required rules",
            ),
        )
    await plugin_manager.before_action(
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

    user = await db.load(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        class_type=core.User,
        user_shortname=shortname,
        branch_name=MANAGEMENT_BRANCH,
    )

    old_version_flattend = flatten_dict(user.dict())

    if profile_user.password and "old_password" in profile.attributes:
        if not password_hashing.verify_password(
            profile.attributes["old_password"], user.password or ""
        ):
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(type="request", code=19, message="Credential does not match"),
            )

    # if "force_password_change" in profile.attributes:
    #     user.force_password_change = profile.attributes["force_password_change"]

    if profile_user.password:
        user.password = password_hashing.hash_password(profile_user.password)
        user.force_password_change = False
    if "displayname" in profile.attributes:
        user.displayname = profile_user.displayname
    if "language" in profile.attributes:
        user.language = profile_user.language

    if "confirmation" in profile.attributes:
        result = None
        async with RedisServices() as redis_services:
            if profile_user.email:
                result = await redis_services.get_content_by_id(
                    f"users:otp:confirmation/email/{profile_user.email}"
                )
            elif profile_user.msisdn:
                result = await redis_services.get_content_by_id(
                    f"users:otp:confirmation/msisdn/{profile_user.msisdn}"
                )

        if result is None or result != profile.attributes["confirmation"]:
            raise Exception(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                api.Error(type="request", code=422, message="Something went wrong [1]"),
            )

        if profile_user.email:
            user.is_email_verified = True
        elif profile_user.msisdn:
            user.is_msisdn_verified = True
    else:
        await validate_uniqueness(MANAGEMENT_SPACE, profile, RequestType.update)
        if "email" in profile.attributes and user.email != profile_user.email:
            user.email = profile_user.email
            user.is_email_verified = False

        if profile_user.msisdn and user.msisdn != profile_user.msisdn:
            user.msisdn = profile_user.msisdn
            user.is_msisdn_verified = False

        if "payload" in profile.attributes and "body" in profile.attributes["payload"]:
            separate_payload_data = {}
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
                        schema_shortname=user.payload.schema_shortname,  # type: ignore
                    )

            if separate_payload_data:
                await db.save_payload_from_json(
                    MANAGEMENT_SPACE,
                    USERS_SUBPATH,
                    user,
                    separate_payload_data,  # type: ignore,
                    MANAGEMENT_BRANCH,
                )

    history_diff = await db.update(
        MANAGEMENT_SPACE,
        USERS_SUBPATH,
        user,
        old_version_flattend,
        flatten_dict(user.dict()),
        list(profile.attributes.keys()),
        MANAGEMENT_BRANCH,
        shortname,
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
            attributes={"history_diff": history_diff},
        )
    )

    return api.Response(status=api.Status.success)


cookie_options = {
    "key": "auth_token",
    "httponly": True,
    "secure": True,
    "samesite": "none",
}
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
) -> api.Response:
    response.set_cookie(value="", max_age=0, **cookie_options)

    return api.Response(status=api.Status.success, records=[])


@router.post(
    "/login",
    response_model=api.Response,
    response_model_exclude_none=True,
)
async def login(response: Response, request: UserLoginRequest) -> api.Response:
    """Login and generate refresh token"""

    shortname = ""
    user = None
    identifier = request.check_fields()
    try:
        if request.invitation:
            async with RedisServices() as redis_services:
                invitation_token = await redis_services.getdel(
                    f"users:login:invitation:{request.invitation}"
                )
            if not invitation_token:
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(type="jwtauth", code=12, message="Invalid invitation"),
                )

            data = decode_jwt(request.invitation)
            shortname = data.get("shortname", None)
            if shortname is None:
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(type="jwtauth", code=12, message="Invalid invitation"),
                )
            user = await db.load(
                space_name=MANAGEMENT_SPACE,
                subpath=USERS_SUBPATH,
                shortname=shortname,
                class_type=core.User,
                user_shortname=shortname,
                branch_name=MANAGEMENT_BRANCH,
            )

            old_version_flattend = flatten_dict(user.dict())
            if (
                data.get("channel") == "EMAIL"
                and user.email
                and f"EMAIL:{user.email}" in invitation_token
            ):
                user.is_email_verified = True
            elif (
                data.get("channel") == "SMS"
                and user.msisdn
                and f"SMS:{user.msisdn}" in invitation_token
            ):
                user.is_msisdn_verified = True
            await db.update(
                MANAGEMENT_SPACE,
                USERS_SUBPATH,
                user,
                old_version_flattend,
                flatten_dict(user.dict()),
                ["is_email_verified", "is_msisdn_verified"],
                MANAGEMENT_BRANCH,
                shortname,
            )
        else:
            if request.password and not re.match(rgx.PASSWORD, request.password):
                raise api.Exception(
                    status.HTTP_401_UNAUTHORIZED,
                    api.Error(
                        type="jwtauth",
                        code=14,
                        message="password dose not match required rules",
                    ),
                )
            if identifier is None:
                raise api.Exception(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    api.Error(
                        type="request", code=422, message="Something went wrong [2]"
                    ),
                )

            if "shortname" in identifier:
                shortname = identifier["shortname"]
                user = await db.load(
                    space_name=MANAGEMENT_SPACE,
                    subpath=USERS_SUBPATH,
                    shortname=identifier["shortname"],
                    class_type=core.User,
                    user_shortname=identifier["shortname"],
                    branch_name=MANAGEMENT_BRANCH,
                )
            else:
                key, value = list(identifier.items())[0]
                shortname = await access_control.get_user_by_criteria(key, value)
                if shortname is None:
                    raise api.Exception(
                        status.HTTP_401_UNAUTHORIZED,
                        api.Error(
                            type="auth",
                            code=10,
                            message=f"Invalid username or password [1] {key=} {value=}",
                        ),
                    )
                user = await db.load(
                    space_name=MANAGEMENT_SPACE,
                    subpath=USERS_SUBPATH,
                    shortname=shortname,
                    class_type=core.User,
                    user_shortname=shortname,
                    branch_name=MANAGEMENT_BRANCH,
                )
        #! TODO: Implement check agains is_email_verified && is_msisdn_verified
        if user and user.is_active and (
            request.invitation
            or password_hashing.verify_password(
                request.password or "", user.password or ""
            )
        ):
            access_token = sign_jwt(
                {"username": shortname}, settings.jwt_access_expires
            )
            response.set_cookie(
                value=access_token,
                max_age=settings.jwt_access_expires,
                **cookie_options,
            )
            record = core.Record(
                resource_type=core.ResourceType.user,
                subpath="users",
                shortname=shortname,
                attributes={
                    "access_token": access_token,
                    "type": user.type,
                },
            )
            if user.displayname:
                record.attributes["displayname"] = user.displayname

            if request.firebase_token:
                user.firebase_token = request.firebase_token
                await db.update(
                    space_name=MANAGEMENT_SPACE,
                    subpath=USERS_SUBPATH,
                    meta=user,
                    old_version_flattend=flatten_dict(user.dict()),
                    new_version_flattend=flatten_dict(
                        {"firebase_token": request.firebase_token}
                    ),
                    updated_attributes_flattend=["firebase_token"],
                    branch_name=MANAGEMENT_BRANCH,
                    user_shortname=shortname,
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
            api.Error(type="auth", code=14, message="Invalid username or password [2]"),
        )
    except api.Exception as e:
        raise e
        if e.error.type == "db":
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(type="auth", code=14, message="Invalid username or password [3]"),
            )
        else:
            raise e


@router.post("/delete", response_model=api.Response, response_model_exclude_none=True)
async def delete_account(shortname=Depends(JWTBearer())) -> api.Response:
    """Delete own user"""
    await plugin_manager.before_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            branch_name=MANAGEMENT_BRANCH,
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
        branch_name=MANAGEMENT_BRANCH,
    )
    await db.delete(MANAGEMENT_SPACE, USERS_SUBPATH, user, MANAGEMENT_BRANCH, shortname)

    await plugin_manager.after_action(
        core.Event(
            space_name=MANAGEMENT_SPACE,
            branch_name=MANAGEMENT_BRANCH,
            subpath=USERS_SUBPATH,
            shortname=shortname,
            action_type=core.ActionType.delete,
            resource_type=ResourceType.user,
            user_shortname=shortname,
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
    skel_accept_language=Header(default=None),
    shortname=Depends(JWTBearer()),
) -> api.Response:
    """Request new OTP"""

    result = user_request.check_fields()
    user = await db.load(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        class_type=core.User,
        user_shortname=shortname,
        branch_name=MANAGEMENT_BRANCH,
    )
    exception = api.Exception(
        status.HTTP_401_UNAUTHORIZED,
        api.Error(
            type="request",
            code=401,
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
            code=401,
            message="mismatch with the information provided",
        ),
    )

    key, value = list(result.items())[0]
    shortname = await access_control.get_user_by_criteria(key, value)
    if shortname is None:
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="auth",
                code=10,
                message=f"Invalid username or password [4] {key=} {value=}",
            ),
        )

    user = await db.load(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        class_type=core.User,
        user_shortname=shortname,
        branch_name=MANAGEMENT_BRANCH,
    )

    old_version_flattend = flatten_dict(user.dict())
    user.force_password_change = True

    await plugin_manager.before_action(
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

    await db.update(
        MANAGEMENT_SPACE,
        USERS_SUBPATH,
        user,
        old_version_flattend,
        flatten_dict(user.dict()),
        ["force_password_change"],
        MANAGEMENT_BRANCH,
        shortname,
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

    invitation_token = sign_jwt({"shortname": shortname}, settings.jwt_access_expires)
    invitation_link = (
        f"{settings.invitation_link}/auth/invitation?invitation={invitation_token}"
    )

    token_uuid = str(uuid.uuid4())[:8]
    async with RedisServices() as redis_services:
        await redis_services.set(
            f"short/{token_uuid}",
            invitation_link,
            ex=60 * 60 * 48,
            nx=False,
        )
        await redis_services.set(f"users:login:invitation:{invitation_token}", 1)

    link = f"{settings.public_app_url}/managed/s/{token_uuid}"

    reset_password_message = f"Reset password via this link: {link}, This link can be used once and within the next 48 hours."

    if "msisdn" in result:
        if not user.msisdn or user.msisdn != result["msisdn"]:
            raise exception
        await send_sms(
            msisdn=user.msisdn,
            message=reset_password_message,
        )
    else:
        if not user.email or user.email != result["email"]:
            raise exception
        await send_email(
            from_address=settings.email_sender,
            to_address=user.email,
            message=reset_password_message,
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

    async with RedisServices() as redis_services:
        code = await redis_services.get(key)
        if not code:
            raise Exception(
                status.HTTP_400_BAD_REQUEST,
                Error(
                    type="OTP",
                    code=308,
                    message="Expired OTP",
                ),
            )

        if code != user_request.code:
            raise Exception(
                status.HTTP_400_BAD_REQUEST,
                Error(
                    type="OTP",
                    code=307,
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

        await redis_services.set(key, confirmation)

        response = await update_profile(data, shortname=user)

        if response.status == Status.success:
            return api.Response(status=api.Status.success, records=[])
        else:
            raise Exception(
                status.HTTP_400_BAD_REQUEST,
                Error(
                    type="OTP",
                    code=104,
                    message=response.error.message
                    if response.error
                    else "Iternal error",
                ),
            )

    

@router.post("/reset", response_model=api.Response, response_model_exclude_none=True)
async def user_reset(
    shortname: str = Body(..., regex=rgx.SHORTNAME, embed=True),
    logged_user=Depends(JWTBearer()),
) -> api.Response:

    roles = await access_control.get_user_roles(logged_user)
    if "super_admin" not in roles:
        raise api.Exception(
            status.HTTP_401_UNAUTHORIZED,
            api.Error(
                type="request",
                code=401,
                message="You don't have permission to this action",
            ),
        )

    await db.load(
        space_name=MANAGEMENT_SPACE,
        subpath=USERS_SUBPATH,
        shortname=shortname,
        class_type=core.User,
        user_shortname=shortname,
        branch_name=MANAGEMENT_BRANCH,
    )

    invitation_token = sign_jwt({"shortname": shortname}, settings.jwt_access_expires)

    user_login_invitation_key = f"users:login:invitation:{invitation_token}"
    async with RedisServices() as redis_services:
        await redis_services.set(
            user_login_invitation_key, invitation_token, settings.jwt_access_expires
        )

    return api.Response(
        status=api.Status.success, attributes={"invitation_token": invitation_token}
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
            api.Error(type="jwtauth", code=14, message="Password dose not match"),
        )
