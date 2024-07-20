from models.core import Content, EntityDTO, Payload, PluginBase, Event
from models.enums import ContentType, ResourceType
from utils.db import load, save
from uuid import uuid4
from fastapi.logger import logger


class Plugin(PluginBase):

    async def hook(self, data: Event):
       
        # Type narrowing for PyRight
        if not isinstance(data.shortname, str):
            logger.error("data.shortname is None and str is required at system_notification_sender")
            return

        entity = EntityDTO.from_event_data(data)
        entry = await load(entity)

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
        notification_obj = {
            "entry_space": data.space_name,
            "entry_subpath": data.subpath,
            "entry_shortname": data.shortname,
            "action_by": data.user_shortname,
            "action_type": data.action_type,
            "is_read": "no"
        }
        await save(
            EntityDTO(
                space_name="personal",
                subpath=f"people/{entry.owner_shortname}/notifications",
                shortname=meta_obj.shortname,
                resource_type=ResourceType.content,
                schema_shortname="notification"
            ),
            meta_obj,
            notification_obj
        )
