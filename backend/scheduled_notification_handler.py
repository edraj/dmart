#!/usr/bin/env -S BACKEND_ENV=config.env python3
from datetime import datetime, timedelta

from models.api import Query
from models.core import Content, Notification, NotificationData, Translation
from data_adapters.adapter import data_adapter as db
from utils.notification import NotificationManager
from utils.settings import settings
from fastapi.logger import logger
import asyncio


async def trigger_admin_notifications() -> None:
    from_time = int((datetime.now() - timedelta(minutes=15)).timestamp() * 1000)
    to_time = int(datetime.now().timestamp() * 1000)
    total, admin_notifications = await db.query(Query(
        space_name=settings.management_space, schema_name="admin_notification_request",
        search=f"@subpath:/notifications/admin (-@status:finished) @scheduled_at:[{from_time} {to_time}]",
        filters={}, limit=10000, offset=0)
    )

    if total == 0:
        return

    notification_manager = NotificationManager()
    for notification in admin_notifications:
        notification_dict = notification.model_dump()
        formatted_req = await prepare_request(notification_dict)

        # Get notification receivers users
        search_criteria = notification_dict.get('msisdns_search_string')
        if not search_criteria:
            search_criteria = '@msisdn:' + '|'.join(notification_dict.get('msisdns', ""))

        total, receivers = await db.query(Query(
            space_name=settings.management_space, schema_name="user",
            search=f"@subpath:users {search_criteria}",
            filters={}, limit=10000, offset=0)
        )

        if total == 0:
            continue

        # Try to send the notification
        # and update the notification status to finished
        formatted_req = await prepare_request(notification_dict)
        try:
            for receiver_data in receivers:
                if not formatted_req["push_only"]:
                    notification_obj = await Notification.from_request(
                        notification_dict
                    )
                    await db.internal_save_model(
                        space_name="personal",
                        subpath=f"people/{receiver_data.shortname}/notifications",
                        meta=notification_obj,
                    )

                for platform in formatted_req["platforms"]:
                    await notification_manager.send(
                        platform=platform,
                        data=NotificationData(
                            receiver=receiver_data.to_dict(),
                            title=formatted_req["title"],
                            body=formatted_req["body"],
                            image_urls=formatted_req["images_urls"],
                        ),
                    )

            notification_meta = await db.load_or_none(
                settings.management_space,
                notification_dict["subpath"],
                notification_dict["shortname"],
                Content,
                notification_dict["owner_shortname"],
            )

            if notification_meta is None:
                return

            await db.internal_sys_update_model(
                settings.management_space,
                notification_dict["subpath"],
                notification_meta,
                {"status": "finished"},
            )
        except Exception as e:
            logger.error(
                f"Error at sending/updating admin based notification: {e.args}"
            )
            pass


async def prepare_request(notification_dict) -> dict:
    # Get Notification Request Images
    attachments_path = (
        settings.spaces_folder
        / f"{settings.management_space}"
        f"/{notification_dict['subpath']}/.dm/{notification_dict['shortname']}"
    )
    notification_attachments = await db.get_entry_attachments(
        subpath=f"{notification_dict['subpath']}/{notification_dict['shortname']}",
        attachments_path=attachments_path,
    )
    notification_images = {
        "en": notification_attachments.get("media", {}).get("en"),
        "ar": notification_attachments.get("media", {}).get("ar"),
        "ku": notification_attachments.get("media", {}).get("ku"),
    }

    return {
        "platforms": notification_dict["types"],
        "title": Translation(**notification_dict["displayname"]),
        "body": Translation(**notification_dict["description"]),
        "images_urls": Translation(**notification_images),
        "push_only": notification_dict.get("push_only", False),
    }


if __name__ == "__main__":
    asyncio.run(trigger_admin_notifications())
