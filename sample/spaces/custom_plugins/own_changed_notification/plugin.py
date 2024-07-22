import sys
from models.core import Content, Payload, PluginBase, Event
from models.enums import ContentType, ResourceType
from utils.helpers import camel_case
from data_adapters.adapter import data_adapter as db
from uuid import uuid4
from fastapi.logger import logger


class Plugin(PluginBase):

    async def hook(self, data: Event):
       
        # Type narrowing for PyRight
        if not isinstance(data.shortname, str):
            logger.error(f"data.shortname is None and str is required at system_notification_sender")
            return

        class_type = getattr(
            sys.modules["models.core"], camel_case(ResourceType(data.resource_type))
        )

        entry = await db.load(
            space_name=data.space_name,
            subpath=data.subpath,
            shortname=data.shortname,
            class_type=class_type,
            user_shortname=data.user_shortname
        )

        if not entry.owner_shortname or entry.owner_shortname == data.user_shortname:
            return

        
        uuid = uuid4()
        meta_obj = Content(
            uuid=uuid,
            shortname=str(uuid)[:8],
            owner_shortname=data.user_shortname,
            payload=Payload(
                content_type=ContentType.json,
                schema_shortname="notification",
                body=f"{str(uuid)[:8]}.json"
            )
        )
        await db.save(
            "personal",
            f"people/{entry.owner_shortname}/notifications",
            meta_obj,
        )

        notification_obj = {
            "entry_space": data.space_name,
            "entry_subpath": data.subpath,
            "entry_shortname": data.shortname,
            "action_by": data.user_shortname,
            "action_type": data.action_type,
            "is_read": "no"
        }
        await db.save_payload_from_json(
            "personal",
            f"people/{entry.owner_shortname}/notifications",
            meta_obj,
            notification_obj,  # type: ignore
        )
