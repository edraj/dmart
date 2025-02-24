import sys
from models.core import Content, Payload, PluginBase, Event, Ticket, Reaction, Comment
from models.enums import ContentType, ResourceType
from utils.helpers import camel_case
from data_adapters.adapter import data_adapter as db
from uuid import uuid4
from fastapi.logger import logger
from utils.async_request import AsyncRequest
from utils.settings import settings


class Plugin(PluginBase):
    async def hook(self, data: Event):
        if not isinstance(data.shortname, str):
            logger.error("data.shortname is None and str is required at local_notification")
            return

        if data.resource_type not in [ResourceType.ticket, ResourceType.reaction, ResourceType.comment, ResourceType.media]:
            return

        class_type = getattr(
            sys.modules["models.core"], camel_case(ResourceType(data.resource_type))
        )
        parent_subpath, parent_shortname, parent_owner = None, None, None

        entry = await db.load(
            space_name=data.space_name,
            subpath=data.subpath,
            shortname=data.shortname,
            class_type=class_type,
            user_shortname=data.user_shortname
        )
        if class_type in [Reaction, Comment]:
            parent_subpath, parent_shortname = data.subpath.rsplit("/", 1)

            parent = await db.load(
                space_name=data.space_name,
                subpath=parent_subpath,
                shortname=parent_shortname,
                class_type=Ticket,
                user_shortname=data.user_shortname
            )
            if parent.owner_shortname == data.user_shortname:
                return

            parent_owner = parent.owner_shortname

        else:
            if not entry.owner_shortname or entry.owner_shortname == data.user_shortname:
                return

        uuid = uuid4()
        meta_obj = Content(
            uuid=uuid,
            shortname=str(uuid)[:8],
            owner_shortname=data.user_shortname,
            is_active=True,
            payload=Payload(
                content_type=ContentType.json,
                schema_shortname="notification",
                body=f"{str(uuid)[:8]}.json"
            )
        )
        await db.save(
            "personal",
            f"people/{parent_owner}/notifications",
            meta_obj,
        )

        notification_obj = {
            "parent_subpath": parent_subpath,
            "parent_shortname": parent_shortname,
            "parent_owner": parent_owner,

            "entry_space": data.space_name,
            "entry_subpath": data.subpath,
            "entry_shortname": data.shortname,

            "action_by": data.user_shortname,
            "action_type": data.action_type,
            "resource_type": data.resource_type,
            "is_read": "no"
        }

        await db.save_payload_from_json(
            "personal",
            f"people/{parent_owner}/notifications",
            meta_obj,
            notification_obj,
        )

        if not settings.websocket_url:
            return

        async with AsyncRequest() as client:
            await client.post(
                f"{settings.websocket_url}/send-message/{parent_owner}",
                json={
                    "type": "notification",
                    "channels": [
                        f"{data.space_name}:__ALL__:__ALL__:__ALL__:__ALL__",
                    ],
                    "message": notification_obj
                }
            )
