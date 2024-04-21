from models.api import Query
from models.enums import ContentType, QueryType
from models.core import ActionType, EntityDTO, PluginBase, Event
from .notification import send_notification
from utils.settings import settings
from fastapi.logger import logger
from utils.db import load, load_resource_payload
from utils.operational_repo import operational_repo

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
            entity = EntityDTO.from_event_data(data)
            entry = (
                await load(entity)
            ).dict()
            if (
                entry["payload"]
                and entry["payload"]["content_type"] == ContentType.json
            ):
                entry["payload"]["body"] = load_resource_payload(entity)
        entry["space_name"] = data.space_name
        entry["resource_type"] = str(data.resource_type)
        entry["subpath"] = data.subpath
        entry["branch_name"] = str(data.branch_name)

        # 1- get the matching SystemNotificationRequests
        search_subpaths = list(filter(None, data.subpath.split("/")))
        total, matching_notification_requests = await operational_repo.search(
            query=Query(
                type=QueryType.search,
                space_name=settings.management_space,
                subpath="notifications/system",
                branch_name=data.branch_name,
                filter_schema_names=["system_notification_request"],
                limit=30,
                offset=0,
                search=f"@on_space:{data.space_name} @on_subpath:({'|'.join(search_subpaths)}) @on_action:{data.action_type}",
            )
        )
        if total <= 0:
            return

        # 2- get list of subscribed users
        notification_subscribers = [entry["owner_shortname"]]
        # if entry.get("collaborators", None):
        #     notification_subscribers.extend(entry["collaborators"].values())  # type: ignore
        if entry.get("owner_group_shortname", None):
            _, group_users = await operational_repo.search(
                Query(
                    type=QueryType.search,
                    space_name=settings.management_space,
                    branch_name=settings.management_space_branch,
                    subpath="users",
                    filter_schema_names=["meta"],
                    search=f"@groups:{{{entry['owner_group_shortname']}}}",
                    limit=10000,
                    offset=0,
                )
            )
            group_members = [
                user_doc["shortname"] for user_doc in group_users
            ]
            notification_subscribers.extend(group_members)

        if data.user_shortname in notification_subscribers:
            notification_subscribers.remove(data.user_shortname)

        # 3- send the notification
        for matching_notification_request in matching_notification_requests:
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
