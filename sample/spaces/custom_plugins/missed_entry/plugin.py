import json
import aiofiles
from models.core import ActionType, EntityDTO, PluginBase, Event, Space
from utils.helpers import branch_path
import utils.db as db
from models import core
from models.enums import ContentType, ResourceType
from utils.settings import settings
from fastapi.logger import logger
from utils.operational_repo import operational_repo

class Plugin(PluginBase):

    def __init__(self) -> None:
        pass


    async def hook(self, data: Event):

        # Type narrowing for PyRight
        if not isinstance(data.shortname, str) and not isinstance(data.attributes, dict):
            logger.error(f"invalid data at missed_entry")
            return

        spaces = await operational_repo.find_by_id("spaces")
        if not Space.model_validate_json(spaces[data.space_name]).capture_misses:
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
            logger.error("data.shortname is None and str is required at missed_entry")
            return

        entity = EntityDTO.from_event_data(data)
        path, filename = db.metapath(entity)
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
            branch_path(data.branch_name) /
            f"misses/{miss_shortname}.json"
        )
        miss_content = {}
        if miss_file.is_file():
            async with aiofiles.open(miss_file, "r") as file:
                miss_content = json.loads(await file.read())
            
        if miss_content and "num_of_requests" in miss_content:
            miss_content["num_of_requests"] += 1
        else:
            miss_content = {
                "requested_subpath": data.subpath,
                "requested_shortname": data.shortname,
                "num_of_requests": 1,
                "actioned": "No",
            }
            
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
        
        await db.save(entity, missed_obj_meta, miss_content)
        await operational_repo.create(entity, missed_obj_meta, miss_content)