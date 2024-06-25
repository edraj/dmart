import json
import requests
from uuid import uuid4
from api.user.service import send_sms
from api.user.router import MANAGEMENT_SPACE, USERS_SUBPATH
from models.core import Notification, Locator, Translation, User
from models.enums import NotificationType
from utils.db import save
from re import sub as res_sub
from firebase_admin import credentials, messaging, initialize_app
from utils.helpers import divide_chunks, flatten_dict, lang_code
from utils.redis_services import RedisServices
from utils.settings import settings
from utils.regex import FILENAME
import os
from pathlib import Path
import utils.db as db
from fastapi.logger import logger


async def send_notification(
    notification_dict: dict,
    receivers: set,
    entry: dict = {},
):
    notification_required_keys = [
        "displayname",
        "description",
        "priority",
        "types",
    ]
    if not all(key in notification_dict for key in notification_required_keys):
        raise Exception(
            "One or more of the Main keys 'displayname', 'description', or 'priority' are missing"
        )
    if isinstance(notification_dict["displayname"], Translation):
        notification_dict["displayname"] = notification_dict["displayname"].dict()
    if isinstance(notification_dict["description"], Translation):
        notification_dict["description"] = notification_dict["description"].dict()

    for locale in ["ar", "en", "ku"]:
        notification_dict["displayname"][locale] = translate_message_vars(
            notification_dict["displayname"][locale], entry, locale
        )
        notification_dict["description"][locale] = translate_message_vars(
            notification_dict["description"][locale], entry, locale
        )

    for receiver in receivers:
        if "web" in notification_dict["types"]:
            try:
                if not notification_dict.get("push_only", False):
                    await store_notification(notification_dict, receiver, entry)

                # Send push notification
                requests.post(
                    url=f"{settings.websocket_url}/send-message/{receiver}",
                    data=json.dumps(
                        {
                            "title": notification_dict["displayname"],
                            "description": notification_dict["description"],
                        }
                    ),
                )
            except Exception as e:
                logger.error(
                    "Notification",
                    extra={
                        "props": {"title": "FAIL at store_notification", "message": e}
                    },
                )
        user = None
        if "mobile" in notification_dict["types"]:
            try:
                user = await db.load(
                    space_name=MANAGEMENT_SPACE,
                    subpath=USERS_SUBPATH,
                    shortname=receiver,
                    class_type=User,
                    user_shortname="dmart",
                )
                await send_notification_firebase(user, notification_dict, entry)
            except Exception as e:
                logger.error(
                    "Notification",
                    extra={
                        "props": {
                            "title": "FAIL at send_notification_firebase",
                            "message": e,
                        }
                    },
                )
        if "sms" in notification_dict["types"]:
            try:
                user = (
                    user
                    if user
                    else await db.load(
                        space_name=MANAGEMENT_SPACE,
                        subpath=USERS_SUBPATH,
                        shortname=receiver,
                        class_type=User,
                        user_shortname="dmart",
                    )
                )
                user_lang_code = lang_code(user.language)
                await send_sms(
                    user.msisdn or "",
                    notification_dict["displayname"][user_lang_code],
                )
            except Exception as e:
                logger.error(
                    "Notification",
                    extra={"props": {"title": "FAIL at send_sms", "message": e}},
                )


def translate_message_vars(message: str, entry: dict, locale: str):
    entry_dict = flatten_dict(entry)
    for field, value in entry_dict.items():
        if type(value) == dict and locale in value:
            value = value[locale]
        if field in ["created_at", "updated_at"]:
            message = message.replace(
                f"{{{field}}}", str(value.strftime("%Y-%m-%d %H:%M:%S"))
            )
        else:
            message = message.replace(f"{{{field}}}", str(value))

    return res_sub(r"\{\w*.*\}", "", message)


async def store_notification(
    notification_dict: dict, receiver_shortname: str, entry: dict = {}
):
    if notification_dict["payload"]["schema_shortname"] == "admin_notification_request":
        notification_type = NotificationType.admin
    else:
        notification_type = NotificationType.system

    entry_locator = None
    if entry:
        entry_locator = Locator(
            space_name=entry["space_name"],
            type=entry["resource_type"],
            schema_shortname=entry["payload"]["schema_shortname"],
            subpath=entry["subpath"],
            shortname=entry["shortname"],
        )

    uuid = uuid4()
    notification_obj = Notification(
        uuid=uuid,
        shortname=str(uuid)[:8],
        is_active=True,
        displayname=notification_dict["displayname"],
        description=notification_dict["description"],
        owner_shortname=notification_dict["owner_shortname"],
        type=notification_type,
        is_read=False,
        priority=notification_dict["priority"],
        entry=entry_locator,
    )

    await save(
        space_name="personal",
        subpath=f"people/{receiver_shortname}/notifications",
        meta=notification_obj,
    )

    async with await RedisServices() as redis:
        await redis.save_meta_doc(
            "personal",
            f"people/{receiver_shortname}/notifications",
            notification_obj,
        )


firebase_app = None


def init_firbase_app():
    global firebase_app
    firebase_cred = credentials.Certificate(settings.google_application_credentials)
    firebase_app = initialize_app(firebase_cred, name="[DEFAULT]")


async def send_notification_firebase(user: User, data, entry):
    users_fcm_tokens = {}

    firebase_token, msisdn = user.firebase_token, user.msisdn

    lang = lang_code(user.language)
    # if lang not in users_fcm_tokens:
    users_fcm_tokens[lang] = {}
    users_fcm_tokens[lang][msisdn] = firebase_token

    images: dict = {}
    images_folder = Path(
        f"{settings.spaces_folder}/{settings.management_space}/{data['subpath']}/.dm/{data['shortname']}/attachments.media"
    )

    if images_folder.is_dir():
        images_files = os.scandir(images_folder)
        for image_file in images_files:
            match = FILENAME.search(str(image_file.name))
            if not match or not image_file.is_file():
                continue

            images[
                image_file.name.split("_")[0]
            ] = f"{settings.listening_host}/public/payload/media/{settings.management_space}/{data['subpath']}/{data['shortname']}/{image_file.name}"

    for lang, fcm_token_per_lang in users_fcm_tokens.items():
        res = send_multiple_notifications(
            tokens=list(fcm_token_per_lang.values()),
            title=data.get("displayname", {}).get(lang, ""),
            body=data.get("description", {}).get(lang, ""),
            image=images.get(lang, ""),
            data={
                **data.get("deep_link"),
                "id": entry.get("shortname"),
                "space_name": entry.get("space_name"),
                "subpath": entry.get("subpath"),
            },
        )


def send_multiple_notifications(
    tokens: list, title: str, body: str, data: dict, image: str, sound="default"
) -> list:
    if not firebase_app:
        init_firbase_app()
    alert = messaging.ApsAlert(title=title, body=body)
    aps = messaging.Aps(alert=alert, sound="default", content_available=True)
    apns = messaging.APNSConfig(
        payload=messaging.APNSPayload(aps),
        fcm_options=messaging.APNSFCMOptions(image=image),
    )
    android_notification_settings = messaging.AndroidNotification(
        priority="high", channel_id="FCM_CHANNEL_ID", visibility="public", image=image
    )
    android_config = messaging.AndroidConfig(
        priority="high", notification=android_notification_settings
    )
    web_push = messaging.WebpushConfig(headers={"image": image})
    # Firebase sends message to max of 500 registration tokens.
    tokens_chunks = divide_chunks(tokens, 500)
    failed_tokens = []
    for tokens in tokens_chunks:
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            tokens=tokens,
            data=data,
            apns=apns,
            android=android_config,
            webpush=web_push,
        )
        response = messaging.send_multicast(message)

        if response.failure_count > 0:
            responses = response.responses
            for idx, resp in enumerate(responses):
                if not resp.success:
                    # The order of responses corresponds to the order of the registration tokens.
                    failed_tokens.append(tokens[idx])

    return failed_tokens
