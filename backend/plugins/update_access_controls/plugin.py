from models.core import PluginBase, Event
from utils.access_control import access_control
from utils.settings import settings


class Plugin(PluginBase):
    async def hook(self, data: Event):
        if settings.active_data_db == "file":
            await access_control.load_permissions_and_roles()
