import json
from sys import modules as sys_modules

from models import api
from models.enums import ContentType
from models.core import (
    ActionType,
    Notification,
    NotificationData,
    PluginBase,
    Event,
    Translation,
)
from utils.notification import NotificationManager
from utils.helpers import camel_case, replace_message_vars
from utils.redis_services import RedisServices
from utils.repository import internal_save_model, get_entry_attachments, get_group_users
from utils.settings import settings
from fastapi.logger import logger
from data_adapters.adapter import data_adapter as db


class Plugin(PluginBase):
    async def hook(self, data: Event):
        """
        after any action
        1- get the matching SystemNotificationRequest for this action
        2- generate list of users to send the notification to (based on the action entry):
            2.1- entry.owner_shortname, entry.group.members?, and entry.collaborators?
        3- send the notification to the list of generated users
        """
        # Type narrowing for PyRight
        if not isinstance(data.shortname, str):
            logger.warning(
                "data.shortname is None and str is required at system_notification_sender"
            )
            return

        if data.action_type == ActionType.delete and data.attributes.get("entry"):
            entry = data.attributes["entry"].model_dump()
        else:
            entry = (
                await db.load(
                    data.space_name,
                    data.subpath,
                    data.shortname,
                    getattr(sys_modules["models.core"], camel_case(data.resource_type)),
                    data.user_shortname,
                )
            ).model_dump()
            if (
                entry["payload"]
                and entry["payload"]["content_type"] == ContentType.json
                and entry["payload"]["body"]
            ):
                try:
                    entry["payload"]["body"] = await db.load_resource_payload(
                        space_name=data.space_name,
                        subpath=data.subpath,
                        filename=entry["payload"]["body"],
                        class_type=getattr(
                            sys_modules["models.core"], camel_case(data.resource_type)
                        ),
                    )
                except Exception as _:
                    return
        entry["space_name"] = data.space_name
        entry["resource_type"] = str(data.resource_type)
        entry["subpath"] = data.subpath

        # 1- get the matching SystemNotificationRequests
        search_subpaths = list(filter(None, data.subpath.split("/")))
        total, matching_notification_requests = await db.query(api.Query(
            space_name=settings.management_space,
            subpath="notifications/system",
            search=f"@on_space:{data.space_name} @on_subpath:({'|'.join(search_subpaths)}) @on_action:{data.action_type}",
            limit=30,
            offset=0
        ))

        if total == 0:
            return

        matching_notification_requests = matching_notification_requests[0].model_dump()

        # 2- get list of subscribed users
        notification_subscribers = [entry["owner_shortname"]]
        # if entry.get("collaborators", None):
        #     notification_subscribers.extend(entry["collaborators"].values())
        if entry.get("owner_group_shortname", None):
            group_users = await get_group_users(entry["owner_group_shortname"])
            group_members = [
                json.loads(user_doc)["shortname"] for user_doc in group_users
            ]
            notification_subscribers.extend(group_members)

        if data.user_shortname in notification_subscribers:
            notification_subscribers.remove(data.user_shortname)

        users_objects: dict[str, dict] = {}

        for subscriber in notification_subscribers:
            users_objects[subscriber] = (await db.load(
                settings.management_space,
                settings.users_subpath,
                subscriber,
                getattr(sys_modules["models.core"], camel_case("user")),
                data.user_shortname,
            )).model_dump()

        # 3- send the notification
        notification_manager = NotificationManager()
        for redis_document in matching_notification_requests["data"]:
            notification_dict = json.loads(redis_document)
            if (
                "state" in entry
                and notification_dict.get("on_state", "") != ""
                and notification_dict["on_state"] != entry["state"]
            ):
                continue

            formatted_req = await self.prepare_request(notification_dict, entry)
            for receiver in set(notification_subscribers):
                if not formatted_req["push_only"]:
                    notification_obj = await Notification.from_request(
                        notification_dict, entry
                    )
                    await internal_save_model(
                        "personal",
                        f"people/{receiver}/notifications",
                        notification_obj,
                    )

                for platform in formatted_req["platforms"]:
                    await notification_manager.send(
                        platform=platform,
                        data=NotificationData(
                            receiver=users_objects[receiver],
                            title=formatted_req["title"],
                            body=formatted_req["body"],
                            image_urls=formatted_req["images_urls"],
                            deep_link=notification_dict.get("deep_link", {}),
                            entry_id=entry["shortname"],
                        ),
                    )

    async def prepare_request(self, notification_dict: dict, entry: dict) -> dict:
        for locale in ["ar", "en", "ku"]:
            notification_dict["displayname"][locale] = replace_message_vars(
                notification_dict["displayname"][locale], entry, locale
            )
            notification_dict["description"][locale] = replace_message_vars(
                notification_dict["description"][locale], entry, locale
            )
        # Get Notification Request Images
        attachments_path = (
            settings.spaces_folder
            / f"{settings.management_space}"
            f"/{notification_dict['subpath']}/.dm/{notification_dict['shortname']}"
        )
        notification_attachments = await get_entry_attachments(
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
