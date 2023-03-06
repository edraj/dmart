from models.core import PluginBase, Event
from utils.spaces import initialize_spaces


class Plugin(PluginBase):

    async def hook(self, data: Event):
        await initialize_spaces()