from fastapi.logger import logger

from data_adapters.adapter import data_adapter as db
from models.core import Event, Folder, PluginBase
from models.enums import ResourceType


class Plugin(PluginBase):
    async def hook(self, data: Event):
        # Type narrowing for PyRight
        if (
            not isinstance(data.shortname, str)
            or not isinstance(data.resource_type, ResourceType)
            or not isinstance(data.attributes, dict)
        ):
            logger.error("invalid data at resource_folders_creation")
            return

        folders = []
        if data.resource_type == ResourceType.user:
            folders = [
                ("personal", "people", data.shortname),
                ("personal", f"people/{data.shortname}", "notifications"),
                ("personal", f"people/{data.shortname}", "private"),
                ("personal", f"people/{data.shortname}", "protected"),
                ("personal", f"people/{data.shortname}", "public"),
                ("personal", f"people/{data.shortname}", "inbox"),
            ]
        elif data.resource_type == ResourceType.space:
            folders = [(data.shortname, "/", "schema")]

        for folder in folders:
            existing_folder = await db.load_or_none(
                space_name=folder[0],
                subpath=folder[1],
                shortname=folder[2],
                class_type=Folder,
                user_shortname=data.user_shortname,
            )
            if existing_folder is None:
                await db.internal_save_model(
                    space_name=folder[0],
                    subpath=folder[1],
                    meta=Folder(
                        shortname=folder[2],
                        is_active=True,
                        owner_shortname=data.user_shortname,
                    ),
                )
