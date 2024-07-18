from models.core import PluginBase, Event
from utils.bootstrap import load_permissions_and_roles
from utils.settings import settings


class Plugin(PluginBase):

    async def hook(self, data: Event):
        if settings.active_data_db == "file":
            await load_permissions_and_roles()
