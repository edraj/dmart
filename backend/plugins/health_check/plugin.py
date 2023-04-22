import asyncio

from health_check import soft_health_check
from models.core import PluginBase, Event
from utils.settings import settings


class Plugin(PluginBase):
    async def hook(self, data: Event):
        task_1 = await asyncio.create_task(soft_health_check(data.space_name, data.shortname, settings.default_branch))
        # await run_in_threadpool(soft_health_check, data.space_name, data.shortname, settings.default_branch)
