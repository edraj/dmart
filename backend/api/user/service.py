import os
import random
import string
import time
from data_adapters.adapter import data_adapter as db
from models import core
from models.api import Error, Exception
from models.enums import ContentType
from utils import password_hashing
from utils.async_request import AsyncRequest
from utils.internal_error_code import InternalErrorCode
from utils.redis_services import RedisServices
from utils.settings import settings
from utils.custom_validations import validate_payload_with_schema
from fastapi.logger import logger
from fastapi import status


MANAGEMENT_SPACE: str = settings.management_space
USERS_SUBPATH: str = "users"

path = f"{os.path.dirname(__file__)}/mocks/"

headers = {"Content-Type": "application/json"}


def gen_alphanumeric(length=16):
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(length)
    )


def gen_numeric(length=6):
    return "".join(random.choice(string.digits) for _ in range(length))


async def mock_sending_otp(msisdn) -> dict:
    key = f"users:otp:otps/{msisdn}"
    async with RedisServices() as redis_services:
        await redis_services.set_key(key, "123456", settings.otp_token_ttl)
    json = {"status": "success", "data": {"status": "success"}}
    return json


async def send_otp(msisdn: str, language: str):
    json = {}
    status: int
    if settings.mock_smpp_api:
        return await mock_sending_otp(msisdn)
    else:
        # Creating SMS message body
        code = gen_numeric()
        message = ""
        match language:
            case "ckb":
                message = f"کۆدی دڵنیابوونی تایبەت بەخۆت {code}"
            case "en":
                message = f"Your otp code is {code}"
            case _:
                message = f"رمز التحقق الخاص بك {code}"

        async with RedisServices() as redis_services:
            await redis_services.set(f"middleware:otp:otps/{msisdn}", code, settings.otp_token_ttl)
        
        async with AsyncRequest() as client:
            response = await client.post(
                settings.send_sms_otp_api,
                headers={**headers, "skel-accept-language": language},
                json={"msisdn": msisdn, "message": message},
            )
            json = await response.json()
            status = response.status

    if status != 200:
        raise Exception(
            status, Error(type="otp", code=InternalErrorCode.OTP_ISSUE, message="OTP issue", info=[json])
        )

    return json.get("data")


async def email_send_otp(email: str, language: str):
    if settings.mock_smtp_api:
        return await mock_sending_otp(email)
    else:
        code = "".join(random.choice("0123456789") for _ in range(6))
        async with RedisServices() as redis_services:
            await redis_services.set_key(f"middleware:otp:otps/{email}", code, settings.otp_token_ttl)
        message = f"<p>Your OTP code is <b>{code}</b></p>"
        return await send_email(settings.email_sender, email, message, "OTP", settings.send_email_otp_api)


async def send_sms(msisdn: str, message: str) -> bool:
    json = {}
    status: int
    if settings.mock_smpp_api:
        return True
        
    async with AsyncRequest() as client:
        response = await client.post(
            settings.send_sms_api,
            headers={**headers},
            json={"msisdn": msisdn, "message": message},
        )
        json = await response.json()
        status = response.status

    if status != 200:
        logger.warning(
            "sms_sender_exception",
            extra={
                "props": {
                    "status": status,
                    "response": json,
                    "target": msisdn
                }
            },
        )
        return False

    return True


async def send_email(from_address: str, to_address: str, message: str, subject: str, send_email_api=settings.send_email_api) -> bool:
    json = {}
    status: int
    start_time = time.time()
    if settings.mock_smtp_api:
        return True
    
    async with AsyncRequest() as client:
        response = await client.post(
            send_email_api,
            headers={**headers},
            json={
                "from_address": from_address,
                "to": to_address,
                "msg": message,
                "subject": subject,
            },
        )
        json = await response.json()
        status = response.status
        logger.info(
            "Email Service",
            extra={
                "props": {
                    "duration": 1000 * (time.time() - start_time),
                    "request": {
                        "from_address": from_address,
                        "to": to_address,
                        "msg": message,
                    },
                    "response": {"status": status, "json": json},
                }
            },
        )

    if status != 200:
        logger.warning(
            "Email Service",
            extra={
                "props": {
                    "status": status,
                    "response": json,
                    "target": to_address,
                    "sender": from_address
                }
            },
        )
        return False

    return True


async def fetch_invitation(invitation: str):
    if settings.active_data_db == "file":
        async with RedisServices() as redis_services:
            # FIXME invitation_token = await redis_services.getdel_key(
            invitation_token = await redis_services.get_key(
                f"users:login:invitation:{invitation}"
            )
    else:
        invitation_token = await db.get_invitation_token(invitation)
    if not invitation_token:
        raise Exception(
            status.HTTP_401_UNAUTHORIZED,
            Error(
                type="jwtauth", code=InternalErrorCode.INVALID_INVITATION, message="Invalid invitation"),
        )

    return invitation_token


async def get_shortname_from_identifier(access_control, key, value):
    if isinstance(value, str) and isinstance(key, str):
        shortname = await access_control.get_user_by_criteria(key, value)
        if not (await access_control.is_user_verified(shortname, key)):
            raise Exception(
                status.HTTP_401_UNAUTHORIZED,
                Error(
                    type="auth",
                    code=InternalErrorCode.USER_ISNT_VERIFIED,
                    message="This user is not verified",
                ),
            )
        return shortname
    else:
        return None


def check_user_validation(user, data, user_updates, invitation_token):
    if (
            data.get("channel") == "EMAIL"
            and user.email
            and f"EMAIL:{user.email}" in invitation_token
    ):
        user_updates["is_email_verified"] = True
    elif (
            data.get("channel") == "SMS"
            and user.msisdn
            and f"SMS:{user.msisdn}" in invitation_token
    ):
        user_updates["is_msisdn_verified"] = True

    return user_updates


async def set_user_profile(profile, profile_user, user):
    if profile_user.password:
        user.password = password_hashing.hash_password(profile_user.password)
        user.force_password_change = False
        # Clear the failed password attempts
        async with RedisServices() as redis_services:
            await redis_services.del_keys([f"users:failed_login_attempts/{profile.shortname}"])
    if "displayname" in profile.attributes:
        user.displayname = profile_user.displayname.model_dump()
    if "description" in profile.attributes:
        user.description = profile_user.description.model_dump()
    if "language" in profile.attributes:
        user.language = profile_user.language

    return user


async def get_otp_confirmation_email_or_msisdn(profile_user):
    async with RedisServices() as redis_services:
        if profile_user.email:
            return await redis_services.get_content_by_id(
                f"users:otp:confirmation/email/{profile_user.email}"
            )
        elif profile_user.msisdn:
            return await redis_services.get_content_by_id(
                f"users:otp:confirmation/msisdn/{profile_user.msisdn}"
            )

async def update_user_payload(profile, profile_user, user, shortname):
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
                schema_shortname=str(user.payload.schema_shortname),
            )

    await db.save_payload_from_json(
        MANAGEMENT_SPACE,
        USERS_SUBPATH,
        user,
        separate_payload_data,
    )

async def clear_failed_password_attempts(shortname: str):
    if settings.active_data_db == "file":
        async with RedisServices() as redis_services:
            await redis_services.del_keys([f"users:failed_login_attempts/{shortname}"])
    else:
        return await db.clear_failed_password_attempts(shortname)

async def get_failed_password_attempt_count(shortname: str) -> int:
    if settings.active_data_db == "file":
        async with RedisServices() as redis_services:
            failed_login_attempts_count = 0
            raw_failed_login_attempts_count = await redis_services.get(f"users:failed_login_attempts/{shortname}")
            if raw_failed_login_attempts_count:
                failed_login_attempts_count = int(raw_failed_login_attempts_count)
            return failed_login_attempts_count
    else:
        failed_password_count: int = await db.get_failed_password_attempt_count(shortname)
        return failed_password_count
    
async def set_failed_password_attempt_count(shortname: str, attempt_count: int):
    if settings.active_data_db == "file":
        async with RedisServices() as redis_services:
            await redis_services.set(f"users:failed_login_attempts/{shortname}", attempt_count)
    else:
        return await db.set_failed_password_attempt_count(shortname, attempt_count)
    