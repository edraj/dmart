from models.core import PluginBase, Event
from utils.bootstrap import load_spaces


class Plugin(PluginBase):

    async def hook(self, data: Event):
        await load_spaces()