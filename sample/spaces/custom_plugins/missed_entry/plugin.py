import json
import sys
import aiofiles
from models.core import ActionType, PluginBase, Event, Space
from utils.helpers import camel_case
from utils.redis_services import RedisServices
from utils.spaces import get_spaces
from data_adapters.adapter import data_adapter as db
from models import core
from models.enums import ContentType, ResourceType
from utils.settings import settings
from fastapi.logger import logger

class Plugin(PluginBase):

    def __init__(self) -> None:
        pass


    async def hook(self, data: Event):

        # Type narrowing for PyRight
        if not isinstance(data.shortname, str) and not isinstance(data.attributes, dict):
            logger.error(f"invalid data at missed_entry")
            return

        spaces = await get_spaces()
        if not Space.parse_raw(spaces[data.space_name]).capture_misses:
            return

        if data.action_type == ActionType.query and "filter_shortnames" in data.attributes:
            for shortname in data.attributes["filter_shortnames"]:
                data.shortname = shortname
                data.resource_type = data.resource_type or ResourceType.content
                await self.check_miss(data)

        else:
            await self.check_miss(data)

        

    async def check_miss(self, data: Event):
        # Type narrowing for PyRight
        if not isinstance(data.shortname, str):
            logger.error(f"data.shortname is None and str is required at missed_entry")
            return

        class_type = getattr(
            sys.modules["models.core"], camel_case(core.ResourceType(data.resource_type))
        )
        path, filename = db.metapath(data.space_name, data.subpath, data.shortname, class_type)
        if (path/filename).is_file():
            return

        if data.subpath[0] == "/":
            data.subpath = data.subpath.replace("/", "", 1)

        miss_shortname = f"{data.subpath}_{data.shortname}"
        if len(miss_shortname) > 32:
            miss_shortname = miss_shortname[:32]

        miss_file = (
            settings.spaces_folder / 
            data.space_name / 
            f"misses/{miss_shortname}.json"
        )
        miss_content = None
        if miss_file.is_file():
            async with aiofiles.open(miss_file, "r") as file:
                miss_content = json.loads(await file.read())

        missed_obj_meta = core.Content(
            shortname=miss_shortname,
            owner_shortname=data.user_shortname,
            is_active=True,
            payload=core.Payload(
                content_type=ContentType.json,
                schema_shortname="miss",
                body=miss_shortname + ".json",
            ),
        )
        async with RedisServices() as redis_services:
            meta_doc_id, meta_json = redis_services.prepate_meta_doc(
                data.space_name, "misses", missed_obj_meta
            )
            if not miss_content:
                await db.save(data.space_name, "misses", missed_obj_meta)
                await redis_services.save_doc(meta_doc_id, meta_json)
                num_of_requests = 1

            else:
                num_of_requests = miss_content["num_of_requests"] + 1

            await db.save_payload_from_json(
                data.space_name,
                "misses",
                missed_obj_meta,
                {
                    "requested_subpath": data.subpath,
                    "requested_shortname": data.shortname,
                    "num_of_requests": num_of_requests,
                    "actioned": "No",
                },
            )
            payload_dict = {
                **meta_json,
                "requested_subpath": data.subpath,
                "requested_shortname": data.shortname,
                "num_of_requests": num_of_requests,
                "actioned": "No"
                
            }
            await redis_services.save_payload_doc(
                space_name=data.space_name,
                subpath="misses",
                meta=missed_obj_meta,
                payload=payload_dict,
                resource_type=ResourceType.content
            )
