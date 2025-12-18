import sys
from models.core import Content, Payload, PluginBase, Event, Reaction, Comment, Relationship, Locator
from models.enums import ContentType
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
        
        if data.resource_type is None:
            return
        
        resource_type = data.resource_type
        try:
            class_type = getattr(sys.modules["models.core"], camel_case(resource_type))
        except AttributeError:
            logger.warning(
                f"local_notification: unsupported resource_type={resource_type!s} (no model class found)"
            )
            return
        parent_subpath, parent_shortname, parent_owner = None, None, None

        entry = await db.load(
            space_name=data.space_name,
            subpath=data.subpath,
            shortname=data.shortname,
            class_type=class_type,
            user_shortname=data.user_shortname
        )
        relationship = None
        if class_type in [Reaction, Comment]:
            parent_subpath, parent_shortname = data.subpath.rsplit("/", 1)
            parent = await db.load(
                space_name=data.space_name,
                subpath=parent_subpath,
                shortname=parent_shortname,
                class_type=Content,
                user_shortname=data.user_shortname
            )
            if parent.owner_shortname == data.user_shortname:
                return

            parent_owner = parent.owner_shortname

            relationship = Relationship(
                related_to=Locator(
                    type=resource_type,
                    space_name=data.space_name,
                    subpath=parent_subpath,
                    shortname=parent_shortname
                ),
                attributes={
                    "parent_owner": parent_owner
                }
            )

        else:
            if not entry.owner_shortname or entry.owner_shortname == data.user_shortname:
                return
            parent_owner = entry.owner_shortname

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
            ),
        )
        
        if relationship is not None:
            meta_obj.relationships = [relationship]

        await db.save(
            "personal",
            f"people/{parent_owner}/notifications",
            meta_obj,
        )

        notification_obj = {
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
