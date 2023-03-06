from models.core import PluginBase, Event


class Plugin(PluginBase):
    def __init__(self) -> None:
        print('{"name": "DUMMY PLUGIN INIT"}')

    async def hook(self, data: Event):
        print('{"name": "DUMMY PLUGIN HOOK CALLED"}')
