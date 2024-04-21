#!/usr/bin/env -S BACKEND_ENV=config.env python3
from datetime import datetime, timedelta
from models.api import Query
from models.core import Content, EntityDTO, Notification, NotificationData, Translation
from models.enums import QueryType, ResourceType
from utils.db import load as load_meta, get_entry_attachments
from utils.helpers import branch_path
from utils.notification import NotificationManager
from utils.operational_repo import operational_repo
from utils.settings import settings
from fastapi.logger import logger
import asyncio


async def trigger_admin_notifications() -> None:
    from_time = int((datetime.now() - timedelta(minutes=15)).timestamp() * 1000)
    to_time = int(datetime.now().timestamp() * 1000)
    admin_notifications = await operational_repo.search(Query(
        type=QueryType.search,
        space_name=settings.management_space,
        branch_name=settings.management_space_branch,
        filter_schema_names=["admin_notification_request"],
        subpath="/notifications/admin",
        search=f"(-@status:finished) @scheduled_at:[{from_time} {to_time}]",
        limit=10000,
        offset=0,
    ))

    if admin_notifications[0] == 0:
        return

    notification_manager = NotificationManager()
    for notification_dict in admin_notifications[1]:
        formatted_req = await prepare_request(notification_dict)

        # Get notification receivers users
        receivers = await operational_repo.search(Query(
            type=QueryType.search,
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            subpath="users",
            search=f"@msisdn:{'|'.join(notification_dict['msisdns'])}",
            limit=10000,
            offset=0,
        ))


        if receivers[0] == 0:
            continue

        # Try to send the notification
        # and update the notification status to finished
        formatted_req = await prepare_request(notification_dict)
        try:
            for receiver_data in receivers[1]:
                if not formatted_req["push_only"]:
                    notification_obj = await Notification.from_request(
                        notification_dict
                    )
                    await operational_repo.internal_save_model(
                        entity=EntityDTO(
                            space_name="personal",
                            subpath=f"people/{receiver_data['shortname']}/notifications",
                            branch_name=notification_dict["branch_name"],
                            shortname=notification_obj.shortname,
                            resource_type=ResourceType.notification
                        ),
                        meta=notification_obj,
                    )

                for platform in formatted_req["platforms"]:
                    await notification_manager.send(
                        platform=platform,
                        data=NotificationData(
                            receiver=receiver_data["shortname"],
                            title=formatted_req["title"],
                            body=formatted_req["body"],
                            image_urls=formatted_req["images_urls"],
                        ),
                    )

            entity = EntityDTO(
                space_name=settings.management_space,
                subpath=notification_dict["subpath"],
                shortname=notification_dict["shortname"],
                resource_type=ResourceType.content,
                user_shortname=notification_dict["owner_shortname"],
            )
            notification_meta: Content = await load_meta(entity)
            await operational_repo.internal_sys_update_model(
                entity=entity,
                meta=notification_meta,
                updates={"status": "finished"},
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
        / f"{settings.management_space}/{branch_path(notification_dict['branch_name'])}"
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
