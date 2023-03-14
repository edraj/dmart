import sys
from models.core import ActionType, PluginBase, Event, Space
from utils.helpers import camel_case
from utils.spaces import get_spaces
import utils.db as db
from models import core
from models.enums import ContentType
from utils.redis_services import RedisServices


class Plugin(PluginBase):
    async def hook(self, data: Event):
        spaces = await get_spaces()
        if not Space.parse_raw(spaces[data.space_name]).indexing_enabled:
            return

        redis = await RedisServices()
        if data.action_type in ActionType.delete:
            doc_id = redis.generate_doc_id(
                data.space_name, data.branch_name, "meta", data.shortname, data.subpath
            )
            meta_doc = await redis.get_doc_by_id(doc_id)
            # Delete meta doc
            await redis.delete_doc(
                data.space_name, data.branch_name, "meta", data.shortname, data.subpath
            )
            # Delete payload doc
            await redis.delete_doc(
                data.space_name,
                data.branch_name,
                meta_doc["payload"]["schema_shortname"],
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
        if data.action_type in [ActionType.create, ActionType.update, ActionType.query]:
            meta_doc_id, meta_json = await redis.save_meta_doc(
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
                await redis.save_payload_doc(
                    data.space_name,
                    data.branch_name,
                    data.subpath,
                    meta,
                    payload,
                    data.resource_type,
                )

        elif data.action_type == ActionType.move:
            await redis.move_meta_doc(
                data.space_name,
                data.branch_name,
                data.attributes["src_shortname"],
                data.attributes["src_subpath"],
                data.subpath,
                meta,
            )
            if meta.payload and meta.payload.schema_shortname:
                await redis.move_payload_doc(
                    data.space_name,
                    data.branch_name,
                    meta.payload.schema_shortname,
                    data.attributes["src_shortname"],
                    data.attributes["src_subpath"],
                    meta.shortname,
                    data.subpath,
                    meta.is_active,
                    meta.owner_shortname,
                )
