import os
import random
import string
import urllib.parse
import time
from models.api import Error, Exception
from utils.async_request import AsyncRequest
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
from fastapi.logger import logger
from utils.operational_repository import operational_repo

# comms_api = zain backend api
send_otp_api = urllib.parse.urljoin(settings.comms_api, "sms/otp/send")
send_sms_api = urllib.parse.urljoin(settings.comms_api, "sms/send")
send_email_api = urllib.parse.urljoin(settings.comms_api, "smtp/send")


path = f"{os.path.dirname(__file__)}/mocks/"

headers = {"Content-Type": "application/json"}


def gen_alphanumeric(length=16):
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(length)
    )


async def mock_sending_otp(msisdn) -> dict:
    key = f"users:otp:otps/{msisdn}"
    await operational_repo.set_key(key, "123456", settings.otp_token_ttl)
    json = {"status": "success", "data": {"status": "success"}}
    return json


async def send_otp(msisdn: str, language: str):
    json = {}
    status: int
    if settings.mock_smpp_api:
        return await mock_sending_otp(msisdn)
    else:
        async with AsyncRequest() as client:
            response = await client.post(
                send_otp_api,
                headers={**headers, "skel-accept-language": language},
                json={"msisdn": msisdn},
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
        await operational_repo.set_key(f"middleware:otp:otps/{email}", code, settings.otp_token_ttl)
        message = f"<p>Your OTP code is <b>{code}</b></p>"
        return await send_email(settings.email_sender, email, message, "OTP")


async def send_sms(msisdn: str, message: str) -> bool:
    json = {}
    status: int
    if settings.mock_smpp_api:
        return True
        
    async with AsyncRequest() as client:
        response = await client.post(
            send_sms_api,
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


async def send_email(from_address: str, to_address: str, message: str, subject: str) -> bool:
    json = {}
    status: int
    start_time = time.time()
    if settings.mock_smpp_api:
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
