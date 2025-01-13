import sys
from models.core import ActionType, Attachment, PluginBase, Event, Space
from utils.helpers import camel_case
from data_adapters.file.adapter_helpers import generate_payload_string
from data_adapters.adapter import data_adapter as db
from models import core
from models.enums import ContentType, ResourceType
from data_adapters.file.redis_services import RedisServices
from fastapi.logger import logger
from data_adapters.file.create_index import main as reload_redis
from utils.settings import settings
from typing import Any


class Plugin(PluginBase):
    async def hook(self, data: Event):
        if settings.active_data_db == "sql":
            return

        self.data = data
        # Type narrowing for PyRight
        if (
            not isinstance(data.shortname, str)
            or not isinstance(data.resource_type, ResourceType)
            or not isinstance(data.attributes, dict)
        ):
            logger.error("invalid data at redis_db_update")
            return

        spaces = await db.get_spaces()
        if (
            data.space_name not in spaces
            or not Space.model_validate_json(spaces[data.space_name]).indexing_enabled
        ):
            return

        class_type = getattr(
            sys.modules["models.core"],
            camel_case(core.ResourceType(data.resource_type)),
        )
        if issubclass(class_type, Attachment):
            await self.update_parent_entry_payload_string()
            return

        async with RedisServices() as redis_services:
            if data.resource_type == ResourceType.folder and data.action_type in [
                ActionType.delete,
                ActionType.move,
            ]:
                await reload_redis(for_space=data.space_name)
                return

            if data.action_type == ActionType.delete:
                doc_id = redis_services.generate_doc_id(
                    data.space_name,
                    "meta",
                    data.shortname,
                    data.subpath,
                )
                meta_doc = await redis_services.get_doc_by_id(doc_id)
                # Delete meta doc
                await redis_services.delete_doc(
                    data.space_name,
                    "meta",
                    data.shortname,
                    data.subpath,
                )
                # Delete payload doc
                await redis_services.delete_doc(
                    data.space_name,
                    (
                        meta_doc.get("payload", {}).get("schema_shortname", "meta")
                        if meta_doc
                        else "meta"
                    ),
                    data.shortname,
                    data.subpath,
                )
                return
            try:
                meta = await db.load(
                    space_name=data.space_name,
                    subpath=data.subpath,
                    shortname=data.shortname,
                    class_type=class_type,
                    user_shortname=data.user_shortname,
                )
            except Exception as _:
                return

            if data.action_type in [
                ActionType.create,
                ActionType.update,
                ActionType.progress_ticket,
            ]:
                meta_doc_id, meta_json = redis_services.prepare_meta_doc(
                    data.space_name, data.subpath, meta
                )
                payload: dict[str, Any] = {}
                if (
                    meta.payload
                    and meta.payload.content_type == ContentType.json
                    and meta.payload.body is not None
                ):
                    mypayload = await db.load_resource_payload(
                        space_name=data.space_name,
                        subpath=data.subpath,
                        filename=str(meta.payload.body),
                        class_type=class_type,
                    )
                    payload = mypayload if mypayload else {}

                meta_json["payload_string"] = await generate_payload_string(
                    db,
                    space_name=data.space_name,
                    subpath=meta_json["subpath"],
                    shortname=meta_json["shortname"],
                    payload=payload,
                ) if settings.store_payload_string else ""

                await redis_services.save_doc(meta_doc_id, meta_json)
                if meta.payload:
                    payload.update(meta_json)
                    await redis_services.save_payload_doc(
                        data.space_name,
                        data.subpath,
                        meta,
                        payload,
                        data.resource_type,
                    )

            elif data.action_type == ActionType.move:
                await redis_services.move_meta_doc(
                    data.space_name,
                    data.attributes["src_shortname"],
                    data.attributes["src_subpath"],
                    data.subpath,
                    meta,
                )
                if meta.payload and meta.payload.schema_shortname:
                    await redis_services.move_payload_doc(
                        data.space_name,
                        meta.payload.schema_shortname,
                        data.attributes["src_shortname"],
                        data.attributes["src_subpath"],
                        meta.shortname,
                        data.subpath,
                    )

    async def update_parent_entry_payload_string(self) -> None:
        async with RedisServices() as redis_services:
            # get the parent meta doc
            subpath_parts = self.data.subpath.strip("/").split("/")
            if len(subpath_parts) <= 1:
                return
            parent_subpath, parent_shortname = (
                "/".join(subpath_parts[:-1]),
                subpath_parts[-1],
            )
            doc_id = redis_services.generate_doc_id(
                self.data.space_name,
                "meta",
                parent_shortname,
                parent_subpath,
            )
            meta_doc: dict = await redis_services.get_doc_by_id(doc_id)

            if meta_doc is None:
                raise Exception("Meta doc not found")

            payload = {}
            if meta_doc.get("payload_doc_id"):
                payload_doc = await redis_services.get_doc_by_id(
                    meta_doc["payload_doc_id"]
                )
                payload = {k: v for k, v in payload_doc.items() if k not in meta_doc}

            # generate the payload string
            meta_doc["payload_string"] = await generate_payload_string(
                db,
                space_name=self.data.space_name,
                subpath=parent_subpath,
                shortname=parent_shortname,
                payload=payload,
            ) if settings.store_payload_string else ""

            # update parent meta doc
            await redis_services.save_doc(doc_id, meta_doc)
