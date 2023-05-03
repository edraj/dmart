from models.core import Folder, PluginBase, Event
from utils.repository import _save_model


class Plugin(PluginBase):

    async def hook(self, data: Event):
        
        folders = [
            "notifications",
            "private",
            "protected",
            "public",
        ]
        for folder in folders:
            await _save_model(
                space_name="personal",
                subpath=f"people/{data.shortname}",
                branch_name=data.branch_name,
                meta=Folder(
                    shortname=folder,
                    is_active=True,
                    owner_shortname=data.user_shortname
                )
            )