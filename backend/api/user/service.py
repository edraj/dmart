import asyncio
import os
import random
import string
import time
from email.message import EmailMessage

import aiosmtplib
from data_adapters.adapter import data_adapter as db
from models import core
from models.api import Error, Exception
from models.enums import ContentType
from utils import password_hashing
from utils.async_request import AsyncRequest
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
from fastapi.logger import logger
from fastapi import status


MANAGEMENT_SPACE: str = settings.management_space
USERS_SUBPATH: str = "users"

path = f"{os.path.dirname(__file__)}/mocks/"

headers = {"Content-Type": "application/json", "auth-key": settings.smpp_auth_key}


def gen_alphanumeric(length=16):
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(length)
    )


def gen_numeric(length=6):
    return "".join(random.choice(string.digits) for _ in range(length))


async def mock_sending_otp(msisdn) -> dict:
    key = f"users:otp:otps/{msisdn}"
    await db.save_otp(key, settings.mock_otp_code)
    json = {"status": "success", "data": {"status": "success"}}
    return json

def get_otp_key(user_identifier: dict[str, str]) -> str:
    if "msisdn" in user_identifier:
        return f"users:otp:otps/{user_identifier['msisdn']}"
    elif "email" in user_identifier:
        return f"users:otp:otps/{user_identifier['email']}"
    return ""

async def send_otp(msisdn: str, language: str):
    json = {}
    status: int
    if settings.mock_smpp_api:
        return await mock_sending_otp(msisdn)
        
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

    await db.save_otp(f"users:otp:otps/{msisdn}", code)
    
    sms_payload: dict = {"msisdn": msisdn, "text": message}
    if settings.sms_sender:
        sms_payload["sender"] = settings.sms_sender

    async with AsyncRequest() as client:
        response = await client.post(
            settings.send_sms_otp_api,
            headers={**headers, "skel-accept-language": language},
            json=sms_payload,
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

    code = "".join(random.choice("0123456789") for _ in range(6))
    await db.save_otp(f"users:otp:otps/{email}", code)
    message = f"<p>Your OTP code is <b>{code}</b></p>"
    return await send_email(email, message, "OTP")


async def send_sms(msisdn: str, message: str) -> bool:
    json = {}
    status: int
    if settings.mock_smpp_api:
        return True
        
    sms_payload: dict = {"msisdn": msisdn, "text": message}
    if settings.sms_sender:
        sms_payload["sender"] = settings.sms_sender

    async with AsyncRequest() as client:
        response = await client.post(
            settings.send_sms_api,
            headers={**headers},
            json=sms_payload,
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


async def _do_send_email(to_address: str, message: str, subject: str) -> None:
    """Actual SMTP send; runs in background."""
    start_time = time.time()
    from_header = f"{settings.mail_from_name} <{settings.mail_from_address}>" if settings.mail_from_name else settings.mail_from_address
    msg = EmailMessage()
    msg["From"] = from_header
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(message, subtype="html")
    use_tls = settings.mail_port == 465
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.mail_host,
            port=settings.mail_port,
            username=settings.mail_username or None,
            password=settings.mail_password or None,
            use_tls=use_tls,
        )
        logger.info(
            "Email Service",
            extra={
                "props": {
                    "duration": 1000 * (time.time() - start_time),
                    "to": to_address,
                    "subject": subject,
                }
            },
        )
    except Exception as e:
        logger.warning(
            "Email Service",
            extra={
                "props": {
                    "error": str(e),
                    "target": to_address,
                    "sender": settings.mail_from_address,
                }
            },
        )


def _log_send_email_failure(t: asyncio.Task) -> None:
    if t.cancelled():
        logger.warning("Email send was cancelled")
    elif t.exception() is not None:
        logger.exception("Email send failed: %s", t.exception())


async def send_email(to_address: str, message: str, subject: str) -> bool:
    """Schedule email send in background and return immediately."""
    if settings.mock_smtp_api:
        return True
    if settings.mail_driver != "smtp" or not settings.mail_host:
        logger.warning("Email Service", extra={"props": {"reason": "mail_driver not smtp or mail_host missing"}})
        return False
    task = asyncio.create_task(_do_send_email(to_address, message, subject))
    task.add_done_callback(_log_send_email_failure)
    return True

async def get_shortname_from_identifier(key, value):
    if isinstance(value, str) and isinstance(key, str):
        shortname = await db.get_user_by_criteria(key, value)
        if shortname is None:
            raise Exception(
                status.HTTP_404_NOT_FOUND,
                Error(
                    type="auth",
                    code=InternalErrorCode.SHORTNAME_DOES_NOT_EXIST,
                    message="User not found",
                )
            )
        if not (await db.is_user_verified(shortname, key)):
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
        await db.clear_failed_password_attempts(profile.shortname)
    if "displayname" in profile.attributes:
        user.displayname = profile_user.displayname.model_dump()
    if "description" in profile.attributes:
        user.description = profile_user.description.model_dump()
    if "language" in profile.attributes:
        user.language = profile_user.language
    if "is_active" in profile.attributes:
        user.is_active = profile_user.is_active
    return user


async def get_otp_confirmation_email_or_msisdn(profile_user):
    if profile_user.email:
       return await db.get_otp(f"users:otp:confirmation/email/{profile_user.email}")
    elif profile_user.msisdn:
        return await db.get_otp(f"users:otp:confirmation/msisdn/{profile_user.msisdn}")
    return None


async def update_user_payload(profile, profile_user, user, shortname):
    separate_payload_data = {}
    user.payload = core.Payload(
        content_type=ContentType.json,
        schema_shortname=profile_user.payload.schema_shortname,
        body="",
    )
    if profile.attributes["payload"]["body"]:
        separate_payload_data = profile.attributes["payload"]["body"]
        if settings.active_data_db == "file":
            user.payload.body = f"{shortname}.json"

    if user.payload and separate_payload_data:
        if profile_user.payload.schema_shortname:
            await db.validate_payload_with_schema(
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
    
