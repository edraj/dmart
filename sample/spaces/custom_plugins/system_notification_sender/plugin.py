import json
from sys import modules as sys_modules
from models.enums import ContentType
from models.core import ActionType, PluginBase, Event
from utils.helpers import camel_case
from .notification import send_notification
from utils.redis_services import RedisServices
from utils.repository import get_group_users
from utils.settings import settings
from fastapi.logger import logger
from utils.db import load, load_resource_payload


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
            logger.error(
                f"data.shortname is None and str is required at system_notification_sender"
            )
            return
        if data.action_type == ActionType.delete:
            entry = data.attributes["entry"].dict()
        else:
            entry = (
                await load(
                    data.space_name,
                    data.subpath,
                    data.shortname,
                    getattr(sys_modules["models.core"], camel_case(data.resource_type)),
                    data.user_shortname,
                )
            ).dict()
            if (
                entry["payload"]
                and entry["payload"]["content_type"] == ContentType.json
            ):
                entry["payload"]["body"] = load_resource_payload(
                    space_name=data.space_name,
                    subpath=data.subpath,
                    filename=entry["payload"]["body"],
                    class_type=getattr(
                        sys_modules["models.core"], camel_case(data.resource_type)
                    ),
                )
        entry["space_name"] = data.space_name
        entry["resource_type"] = str(data.resource_type)
        entry["subpath"] = data.subpath

        # 1- get the matching SystemNotificationRequests
        search_subpaths = list(filter(None, data.subpath.split("/")))
        async with RedisServices() as redis:
            matching_notification_requests = await redis.search(
                space_name=settings.management_space,
                schema_name="system_notification_request",
                filters={"subpath": ["notifications/system"]},
                limit=30,
                offset=0,
                search=f"@on_space:{data.space_name} @on_subpath:({'|'.join(search_subpaths)}) @on_action:{data.action_type}",
            )
        if not matching_notification_requests.get("data", {}):
            return True

        # 2- get list of subscribed users
        notification_subscribers = [entry["owner_shortname"]]
        # if entry.get("collaborators", None):
        #     notification_subscribers.extend(entry["collaborators"].values())  # type: ignore
        if entry.get("owner_group_shortname", None):
            group_users = await get_group_users(entry["owner_group_shortname"])
            group_members = [
                json.loads(user_doc.json)["shortname"] for user_doc in group_users
            ]
            notification_subscribers.extend(group_members)

        if data.user_shortname in notification_subscribers:
            notification_subscribers.remove(data.user_shortname)

        # 3- send the notification
        for redis_document in matching_notification_requests["data"]:
            matching_notification_request = json.loads(redis_document.json)
            if (
                "state" in entry
                and "on_state" in matching_notification_request
                and matching_notification_request["on_state"] != entry["state"]
            ):
                continue
            await send_notification(
                notification_dict=matching_notification_request,
                entry=entry,
                receivers=set(notification_subscribers),
            )
