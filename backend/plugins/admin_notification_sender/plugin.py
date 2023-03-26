import json
from sys import modules as sys_modules
from models.core import Notification, NotificationData, PluginBase, Event, Translation
from utils.helpers import branch_path, camel_case
from utils.notification import NotificationManager
from utils.redis_services import RedisServices
from utils.repository import _save_model, get_entry_attachments
from utils.settings import settings
from fastapi.logger import logger
from utils.db import load, load_resource_payload, save_payload_from_json


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
            logger.error(
                f"data.shortname is None and str is required at system_notification_sender"
            )
            return

        notification_request_meta = await load(
            data.space_name, 
            data.subpath, 
            data.shortname,
            getattr(sys_modules["models.core"], camel_case(data.resource_type)),
            data.user_shortname,
            data.branch_name
        )
        notification_dict = notification_request_meta.dict()
        notification_dict["subpath"] = data.subpath
        notification_dict["branch_name"] = data.branch_name

        notification_request_payload = load_resource_payload(
            data.space_name, 
            data.subpath, 
            notification_request_meta.payload.body,
            getattr(sys_modules["models.core"], camel_case(data.resource_type)),
            data.branch_name
        )
        notification_dict.update(notification_request_payload)
        
        if not notification_dict or notification_dict.get("scheduled_at", False):
            return

        # Get msisdns users
        redis = await RedisServices()
        receivers = await redis.search(
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            search=f"@subpath:users @msisdn:{'|'.join(notification_dict['msisdns'])}",
            filters={},
            limit=10000,
            offset=0
        )
        if not receivers or receivers.get("total", 0) == 0:
            return

        receivers_shortnames = set()
        for receiver in receivers['data']:
            receivers_shortnames.add(json.loads(receiver.json)['shortname'])

        # await send_notification(
        #     notification_dict=notification_dict,
        #     receivers=receivers_shortnames
        # )
        notification_manager = NotificationManager()
        formatted_req = await self.prepare_request(notification_dict)
        for receiver in set(receivers_shortnames):
                
            if not formatted_req["push_only"]:
                notification_obj = await Notification.from_request(
                    notification_dict
                )
                await _save_model(
                    "personal",
                    f"people/{receiver}/notifications",
                    notification_obj,
                    notification_dict["branch_name"]
                )

            for platform in formatted_req["platforms"]:
                await notification_manager.send(
                    platform=platform,
                    data=NotificationData(
                        receiver=receiver, 
                        title=formatted_req["title"],
                        body=formatted_req["body"],
                        image_urls=formatted_req["images_urls"],
                    )
                )

        

        notification_request_payload["status"] = "finished"
        await save_payload_from_json(
            space_name=data.space_name,
            subpath=data.subpath,
            meta=notification_request_meta,
            payload_data=notification_request_payload,
            branch_name=data.branch_name
        )

    async def prepare_request(self, notification_dict):
        # Get Notification Request Images
        attachments_path = (
            settings.spaces_folder
            / f"{settings.management_space}/{branch_path(notification_dict['branch_name'])}/{notification_dict['subpath']}/.dm/{notification_dict['shortname']}"
        )
        notification_attachments = await get_entry_attachments(
            subpath=f"{notification_dict['subpath']}/{notification_dict['shortname']}",
            branch_name=notification_dict["branch_name"],
            attachments_path=attachments_path
        )
        notification_images = {
            "en": notification_attachments.get("media", {}).get("en"),
            "ar": notification_attachments.get("media", {}).get("ar"),
            "kd": notification_attachments.get("media", {}).get("kd"),
        }

        return {
            "platforms":notification_dict["types"],
            "title":Translation(**notification_dict["displayname"]),
            "body":Translation(**notification_dict["description"]),
            "images_urls":Translation(**notification_images),
            "push_only":notification_dict.get("push_only", False)
        }

        
