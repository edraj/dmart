import json
from sys import modules as sys_modules

from models import api
from models.core import Notification, NotificationData, PluginBase, Event, Translation
from utils.helpers import camel_case
from utils.notification import NotificationManager
from utils.settings import settings
from fastapi.logger import logger
from data_adapters.adapter import data_adapter as db

class Plugin(PluginBase):
    async def hook(self, data: Event):
        """
        after creating a new admin notification request
        1- get the notification request
        2- if it's scheduled for later, ignore it and let the cron job handle it
        3- else send it to all its msisdns
        """

        # Type narrowing for PyRight
        if not isinstance(data.shortname, str):
            logger.warning(
                "data.shortname is None and str is required at system_notification_sender"
            )
            return

        notification_request_meta = await db.load(
            data.space_name,
            data.subpath,
            data.shortname,
            getattr(sys_modules["models.core"], camel_case(data.resource_type)),
            data.user_shortname,
        )

        notification_dict = notification_request_meta.dict()
        notification_dict["subpath"] = data.subpath
        notification_request_payload = await db.get_payload_from_event(data)

        notification_dict.update(notification_request_payload)

        if not notification_dict or notification_dict.get("scheduled_at", False):
            return

        # Get msisdns users
        search_criteria = notification_dict.get('search_string', '')
        if not search_criteria:
            search_criteria = '@msisdn:' + '|'.join(notification_dict.get('msisdns', ''))

        total, receivers = await db.query(api.Query(
            space_name=data.space_name,
            subpath=notification_dict['subpath'],
            filters={},
            search=search_criteria,
            limit=10000,
            offset=0
        ))
        if total == 0:
            return

        sub_receivers: dict = receivers[0].model_dump()

        receivers_shortnames = set()
        for receiver in sub_receivers["data"]:
            receivers_shortnames.add(json.loads(receiver)["shortname"])

        # await send_notification(
        #     notification_dict=notification_dict,
        #     receivers=receivers_shortnames
        # )
        notification_manager = NotificationManager()
        formatted_req = await self.prepare_request(notification_dict)
        for receiver in set(receivers_shortnames):
            if not formatted_req["push_only"]:
                notification_obj = await Notification.from_request(notification_dict)
                await db.internal_save_model(
                    "personal",
                    f"people/{receiver}/notifications",
                    notification_obj,
                )
            for platform in formatted_req["platforms"]:
                await notification_manager.send(
                    platform=platform,
                    data=NotificationData(
                        receiver=receiver,
                        title=formatted_req["title"],
                        body=formatted_req["body"],
                        image_urls=formatted_req["images_urls"],
                    ),
                )


        notification_request_payload["status"] = "finished"
        await db.save_payload_from_json(
            space_name=data.space_name,
            subpath=data.subpath,
            meta=notification_request_meta,
            payload_data=notification_request_payload,
        )

    async def prepare_request(self, notification_dict) -> dict:
        # Get Notification Request Images
        attachments_path = (
            settings.spaces_folder
            / f"{settings.management_space}/"
            f"{notification_dict['subpath']}/.dm/{notification_dict['shortname']}"
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
