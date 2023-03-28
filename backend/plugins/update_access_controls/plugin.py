from models.core import PluginBase, Event
from utils.access_control import access_control


class Plugin(PluginBase):

    async def hook(self, data: Event):
        await access_control.load_permissions_and_roles()