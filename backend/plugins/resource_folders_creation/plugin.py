from models.core import Folder, PluginBase, Event
from models.enums import ResourceType
from utils.redis_services import RedisServices
from utils.repository import internal_save_model
from fastapi.logger import logger


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
            ]
        elif data.resource_type == ResourceType.space:
            # sys_schemas = ["meta_schema", "folder_rendering"]
            # for schema_name in sys_schemas:
            #     await clone(
            #         src_space=settings.management_space,
            #         src_subpath="schema",
            #         src_shortname=schema_name,
            #         dest_space=data.shortname,
            #         dest_subpath="schema",
            #         dest_shortname=schema_name,
            #         class_type=Schema,
            #     )

            async with RedisServices() as redis_services:
                await redis_services.create_indices(
                    for_space=data.shortname,
                    # for_schemas=sys_schemas,
                    for_custom_indices=False,
                    del_docs=False,
                )

            # redis_update_plugin = RedisUpdatePlugin()
            # for schema_name in sys_schemas:
            #     await redis_update_plugin.hook(Event(
            #         space_name=data.shortname,
            #         subpath="schema",
            #         shortname=schema_name,
            #         action_type=ActionType.create,
            #         resource_type=ResourceType.schema,
            #         user_shortname=data.user_shortname
            #     ))

            folders = [(data.shortname, "/", "schema")]

        for folder in folders:
            await internal_save_model(
                space_name=folder[0],
                subpath=folder[1],
                meta=Folder(
                    shortname=folder[2],
                    is_active=True,
                    owner_shortname=data.user_shortname,
                ),
            )
