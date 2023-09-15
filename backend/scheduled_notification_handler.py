#!/usr/bin/env -S BACKEND_ENV=config.env python3
from datetime import datetime, timedelta
import json
from models.core import Content, Notification, NotificationData, Translation
from utils.db import load as load_meta
from utils.helpers import branch_path
from utils.notification import NotificationManager
from utils.redis_services import RedisServices
from utils.repository import internal_save_model, internal_sys_update_model, get_entry_attachments
from utils.settings import settings
from fastapi.logger import logger
import asyncio

async def trigger_admin_notifications() -> None:
    from_time = int((datetime.now() - timedelta(minutes=15)).timestamp()*1000)
    to_time = int(datetime.now().timestamp()*1000)
    async with RedisServices() as redis_services:
        admin_notifications = await redis_services.search(
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            schema_name="admin_notification_request",
            search=f"@subpath:/notifications/admin (-@status:finished) @scheduled_at:[{from_time} {to_time}]",
            filters={},
            limit=10000,
            offset=0
        )
    if admin_notifications["total"] == 0:
        return

    notification_manager = NotificationManager()
    for notification_doc in admin_notifications["data"]:
        notification_dict = json.loads(notification_doc)
        formatted_req = await prepare_request(notification_dict)

        # Get notification receivers users
        async with RedisServices() as redis_services:
            receivers = await redis_services.search(
                space_name=settings.management_space,
                branch_name=settings.management_space_branch,
                search=f"@subpath:users @msisdn:{'|'.join(notification_dict['msisdns'])}",
                filters={},
                limit=10000,
                offset=0
            )

        if not receivers:
            continue

        # Try to send the notification 
        # and update the notification status to finished
        formatted_req = await prepare_request(notification_dict)
        try:
            for receiver in receivers['data']:
                receiver_data = json.loads(receiver)
                if not formatted_req["push_only"]:
                    notification_obj = await Notification.from_request(notification_dict)
                    await internal_save_model(
                        space_name="personal",
                        subpath=f"people/{receiver_data['shortname']}/notifications",
                        meta=notification_obj,
                        branch_name=notification_dict["branch_name"],
                    )

                for platform in formatted_req["platforms"]:
                    await notification_manager.send(
                        platform=platform,
                        data=NotificationData(
                            receiver=receiver_data['shortname'],
                            title=formatted_req["title"],
                            body=formatted_req["body"],
                            image_urls=formatted_req["images_urls"],
                        ),
                    )

            notification_meta = await load_meta(
                settings.management_space,
                notification_dict["subpath"],
                notification_dict["shortname"],
                Content,
                notification_dict["owner_shortname"],
                settings.management_space_branch,
            )
            await internal_sys_update_model(
                settings.management_space,
                notification_dict["subpath"],
                notification_meta,
                settings.management_space_branch,
                {"status": "finished"}
            )
        except Exception as e:
            logger.error(f"Error at sending/updating admin based notification: {e.args}")
            pass

    await RedisServices.POOL.disconnect(True)


async def prepare_request(notification_dict) -> dict:
    # Get Notification Request Images
    attachments_path = (
        settings.spaces_folder / f"{settings.management_space}/{branch_path(notification_dict['branch_name'])}"
        f"/{notification_dict['subpath']}/.dm/{notification_dict['shortname']}"
    )
    notification_attachments = await get_entry_attachments(
        subpath=f"{notification_dict['subpath']}/{notification_dict['shortname']}",
        branch_name=notification_dict["branch_name"],
        attachments_path=attachments_path,
    )
    notification_images = {
        "en": notification_attachments.get("media", {}).get("en"),
        "ar": notification_attachments.get("media", {}).get("ar"),
        "kd": notification_attachments.get("media", {}).get("kd"),
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
