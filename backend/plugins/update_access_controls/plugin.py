from models.core import PluginBase, Event
from utils.bootstrap import load_permissions_and_roles


class Plugin(PluginBase):

    async def hook(self, data: Event):
        await load_permissions_and_roles()