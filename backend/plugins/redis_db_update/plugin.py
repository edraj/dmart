import sys
from models.core import ActionType, PluginBase, Event, Space
from utils.helpers import camel_case
from utils.spaces import get_spaces
import utils.db as db
from models import core
from models.enums import ContentType, ResourceType
from utils.redis_services import RedisServices
from fastapi.logger import logger


class Plugin(PluginBase):
    async def hook(self, data: Event):
        # Type narrowing for PyRight
        if (
            not isinstance(data.shortname, str)
            or not isinstance(data.resource_type, ResourceType)
            or not isinstance(data.attributes, dict)
        ):
            logger.error(f"invalid data at redis_db_update")
            return

        spaces = await get_spaces()
        if not Space.parse_raw(spaces[data.space_name]).indexing_enabled:
            return

        async with RedisServices() as redis_services:
            if data.action_type in ActionType.delete:
                doc_id = redis_services.generate_doc_id(
                    data.space_name, data.branch_name, "meta", data.shortname, data.subpath
                )
                meta_doc = await redis_services.get_doc_by_id(doc_id)
                # Delete meta doc
                await redis_services.delete_doc(
                    data.space_name, data.branch_name, "meta", data.shortname, data.subpath
                )
                # Delete payload doc
                await redis_services.delete_doc(
                    data.space_name,
                    data.branch_name,
                    meta_doc.get("payload", {}).get("schema_shortname", "meta"),
                    data.shortname,
                    data.subpath,
                )
                return

            class_type = getattr(
                sys.modules["models.core"],
                camel_case(core.ResourceType(data.resource_type)),
            )
            meta = await db.load(
                space_name=data.space_name,
                subpath=data.subpath,
                shortname=data.shortname,
                class_type=class_type,
                user_shortname=data.user_shortname,
                branch_name=data.branch_name,
            )

            if data.action_type in [
                ActionType.create,
                ActionType.update,
                ActionType.progress_ticket,
            ]:
                meta_doc_id, meta_json = await redis_services.save_meta_doc(
                    data.space_name, data.branch_name, data.subpath, meta
                )
                if meta.payload and meta.payload.content_type == ContentType.json:
                    payload = db.load_resource_payload(
                        space_name=data.space_name,
                        subpath=data.subpath,
                        filename=meta.payload.body,
                        class_type=class_type,
                        branch_name=data.branch_name,
                    )

                    payload.update(meta_json)
                    await redis_services.save_payload_doc(
                        data.space_name,
                        data.branch_name,
                        data.subpath,
                        meta,
                        payload,
                        data.resource_type,
                    )

            elif data.action_type == ActionType.move:
                await redis_services.move_meta_doc(
                    data.space_name,
                    data.branch_name,
                    data.attributes["src_shortname"],
                    data.attributes["src_subpath"],
                    data.subpath,
                    meta,
                )
                if meta.payload and meta.payload.schema_shortname:
                    await redis_services.move_payload_doc(
                        data.space_name,
                        data.branch_name,
                        meta.payload.schema_shortname,
                        data.attributes["src_shortname"],
                        data.attributes["src_subpath"],
                        meta.shortname,
                        data.subpath,
                    )
