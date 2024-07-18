from pathlib import Path

import aiofiles
from utils.middleware import get_request_data
from models.core import ActionType, EntityDTO, PluginBase, Event
from models.enums import ContentType, ResourceType
from utils.data_database import data_adapter as db
from models.core import Action, Locator, Meta
from utils.settings import settings
from datetime import datetime
from fastapi.logger import logger


class Plugin(PluginBase):
    async def hook(self, data: Event):
        # Type narrowing for PyRight
        if (
            not isinstance(data.shortname, str)
            or not isinstance(data.action_type, ActionType)
            or not isinstance(data.resource_type, ResourceType)
            or not isinstance(data.attributes, dict)
        ):
            logger.warning("invalid data at action_log")
            return

        dto = EntityDTO.from_event_data(data)
        
        if data.action_type == ActionType.delete:
            entry = data.attributes["entry"]
        else:
            entry = await db.load_or_none(dto)
        if not entry:
            return

        action_attributes = {}
        if data.action_type == ActionType.create:
            payload = {}
            if(
                entry.payload and 
                entry.payload.content_type == ContentType.json
                and entry.payload.body
            ):
                payload = await db.load_resource_payload(dto)
            action_attributes = self.generate_create_event_attributes(entry, payload)

        elif data.action_type == ActionType.update:
            action_attributes = data.attributes.get("history_diff", {})

        action_attributes={**action_attributes, **get_request_data()}

        event_obj = Action(
            resource=Locator(
                uuid=entry.uuid,
                type=data.resource_type,
                space_name=data.space_name,
                branch_name=data.branch_name,
                subpath=data.subpath,
                shortname=data.shortname,
                displayname=entry.displayname,
                description=entry.description,
                tags=entry.tags,
            ),
            user_shortname=data.user_shortname,
            request=data.action_type,
            timestamp=datetime.now(),
            attributes=action_attributes,
        )

        events_file_path = (
            settings.spaces_folder
            / data.space_name
            / ".dm"
        )
        events_file_path.mkdir(parents=True, exist_ok=True)
        events_file_path = events_file_path / "events.jsonl"

        file_content = (
            f"\n{event_obj.model_dump_json()}" if events_file_path.is_file() else event_obj.model_dump_json()
        )

        async with aiofiles.open(events_file_path, "a") as events_file:
            await events_file.write(file_content)

    def generate_create_event_attributes(self, entry: Meta, attributes: dict):
        generated_attributes = {}
        for key, value in entry.__dict__.items():
            if key == "_sa_instance_state":
                continue
            if key not in Meta.model_fields:
                generated_attributes[key] = value

        if entry.payload:
            generated_attributes["payload"] = entry.payload.model_dump()

        if attributes:
            generated_attributes["payload"]["body"] = attributes

        return generated_attributes
