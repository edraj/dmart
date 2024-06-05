from models.api import Query
from models.core import Content, EntityDTO, Notification, NotificationData, PluginBase, Event, Translation
from models.enums import QueryType, ResourceType
from utils.helpers import branch_path
from utils.notification import NotificationManager
from utils.settings import settings
from fastapi.logger import logger
from utils.data_repo import data_adapter as db
from utils.operational_repo import operational_repo

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

        notification_dto = EntityDTO.from_event_data(data)
        notification_request_meta: Content = await db.load(notification_dto)
        notification_dict = notification_request_meta.model_dump()
        notification_dict["subpath"] = data.subpath
        notification_dict["branch_name"] = data.branch_name

        notification_request_payload = await db.load_resource_payload(notification_dto)
        notification_dict.update(notification_request_payload)

        if not notification_dict or notification_dict.get("scheduled_at", False):
            return

        # Get msisdns users
        receivers = await operational_repo.search(Query(
            type=QueryType.search,
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            subpath="users",
            search=f"@msisdn:{'|'.join(notification_dict['msisdns'])}",
            limit=10000,
            offset=0,
        ))
        if not receivers or receivers[0] == 0:
            return

        receivers_shortnames = set()
        for receiver in receivers[1]:
            receivers_shortnames.add(receiver["shortname"])

        # await send_notification(
        #     notification_dict=notification_dict,
        #     receivers=receivers_shortnames
        # )
        notification_manager = NotificationManager()
        formatted_req = await self.prepare_request(notification_dict)
        for receiver in set(receivers_shortnames):
            if not formatted_req["push_only"]:
                notification_obj = await Notification.from_request(notification_dict)
                await operational_repo.internal_save_model(
                    dto=EntityDTO(
                        space_name="personal",
                        subpath=f"people/{receiver}/notifications",
                        shortname=notification_obj.shortname,
                        resource_type=ResourceType.notification
                    ),
                    meta=notification_obj,
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
            dto=notification_dto,
            meta=notification_request_meta,
            payload_data=notification_request_payload,
        )

    async def prepare_request(self, notification_dict) -> dict:
        # Get Notification Request Images
        attachments_path = (
            settings.spaces_folder
            / f"{settings.management_space}/{branch_path(notification_dict['branch_name'])}/"
            f"{notification_dict['subpath']}/.dm/{notification_dict['shortname']}"
        )
        notification_attachments = await db.get_entry_attachments(
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
