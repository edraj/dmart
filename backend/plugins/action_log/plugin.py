import sys
from typing import Any
import aiofiles
from utils.middleware import get_request_data
from models.core import ActionType, PluginBase, Event, Payload
from models.enums import ContentType, ResourceType
from models.core import Action, Locator, Meta
from utils.helpers import camel_case
from utils.settings import settings
from datetime import datetime
from fastapi.logger import logger
from data_adapters.adapter import data_adapter as db


class Plugin(PluginBase):
    async def hook(self, data: Event):
        if settings.active_data_db == "sql":
            return

        if (
            not isinstance(data.shortname, str)
            or not isinstance(data.action_type, ActionType)
            or not isinstance(data.resource_type, ResourceType)
            or not isinstance(data.attributes, dict)
        ):
            logger.warning("invalid data at action_log")
            return

        class_type = getattr(
            sys.modules["models.core"], camel_case(ResourceType(data.resource_type))
        )

        if data.action_type == ActionType.delete:
            entry = data.attributes["entry"]
        else:
            entry = await db.load_or_none(
                space_name=data.space_name,
                subpath=data.subpath,
                shortname=data.shortname,
                class_type=class_type,
                user_shortname=data.user_shortname,
            )

            if entry is None:
                return

        action_attributes = {}
        if data.action_type == ActionType.create:
            payload: dict[str,Any] = {}
            if(
                entry.payload and
                isinstance(entry.payload, Payload) and
                entry.payload.content_type and
                entry.payload.content_type == ContentType.json
                and entry.payload.body
            ):
                mypayload = await db.load_resource_payload(
                    space_name=data.space_name,
                    subpath=data.subpath,
                    filename=entry.payload.body if isinstance(entry.payload.body, str) else data.shortname,
                    class_type=class_type,
                )
                payload = mypayload if mypayload else {}
            action_attributes = self.generate_create_event_attributes(entry, payload)

        elif data.action_type == ActionType.update:
            action_attributes = data.attributes.get("history_diff", {})

        action_attributes = {**action_attributes, **get_request_data()}
        action_attributes.pop("_sa_instance_state", None)
        event_obj = Action(
            resource=Locator(
                uuid=entry.uuid,
                type=data.resource_type,
                space_name=data.space_name,
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

        # Remove binary content in the event object before serializing to json
        if isinstance(event_obj.attributes, dict) and "media" in event_obj.attributes:
            del event_obj.attributes["media"]

        file_content = (
            f"{event_obj.model_dump_json()}\n"
        )
        async with aiofiles.open(events_file_path, "a") as events_file:
            await events_file.write(file_content)

    def generate_create_event_attributes(self, entry: Meta, attributes: dict):
        generated_attributes = {}
        for key, value in entry.__dict__.items():
            if key not in Meta.model_fields:
                generated_attributes[key] = value

        if entry.payload:
            if isinstance(entry.payload, Payload):
                generated_attributes["payload"] = entry.payload.model_dump()
            else:
                generated_attributes["payload"] = entry.payload

        if attributes:
            generated_attributes["payload"]["body"] = attributes

        return generated_attributes
