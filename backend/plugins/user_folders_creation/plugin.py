from models.core import Folder, PluginBase, Event
from utils.repository import _save_model


class Plugin(PluginBase):

    async def hook(self, data: Event):
        # Create user main folder
        await _save_model(
            space_name="personal",
            subpath=f"people",
            branch_name=data.branch_name,
            meta=Folder(
                shortname=data.shortname,
                is_active=True,
                owner_shortname=data.user_shortname
            )
        )

        # Create user subfolders
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