from models.core import Folder, PluginBase, Event
from utils.repository import _save_model


class Plugin(PluginBase):

    async def hook(self, data: Event):
        folders = [
            ("people", data.shortname),
            (f"people/{data.shortname}", "notifications"),
            (f"people/{data.shortname}", "private"),
            (f"people/{data.shortname}", "protected"),
            (f"people/{data.shortname}", "public"),
        ]
        for folder in folders:
            await _save_model(
                space_name="personal",
                subpath=folder[0],
                branch_name=data.branch_name,
                meta=Folder(
                    shortname=folder[1],
                    is_active=True,
                    owner_shortname=data.user_shortname
                )
            )