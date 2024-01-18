from models.core import PluginBase, Event


class Plugin(PluginBase):
    async def hook(self, data: Event):
        print(f"Reached to the dummy custom plugin, data recieved: {data}")
