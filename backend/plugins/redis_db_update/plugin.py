import sys
from models.core import ActionType, Attachment, EntityDTO, PluginBase, Event, Space
from utils.helpers import camel_case
from utils.data_database import data_adapter as db
from models import core
from models.enums import ResourceType
from fastapi.logger import logger
# from create_index import main as reload_redis
from create_index_manticore import main as reload_redis
from utils.operational_repository import operational_repo


class Plugin(PluginBase):
    async def hook(self, data: Event):
        self.data = data
        # Type narrowing for PyRight
        if (
            not isinstance(data.shortname, str)
            or not isinstance(data.resource_type, ResourceType)
            or not isinstance(data.attributes, dict)
        ):
            logger.error("invalid data at redis_db_update")
            return

        spaces = await operational_repo.find_by_id("spaces")
        if (
            data.space_name not in spaces
            or not Space.model_validate_json(spaces[data.space_name]).indexing_enabled
        ):
            return

        class_type = getattr(
            sys.modules["models.core"],
            camel_case(core.ResourceType(data.resource_type)),
        )
        if issubclass(class_type, Attachment):
            await self.update_parent_entry_payload_string()
            return

        if data.resource_type in ResourceType.folder and data.action_type in [
            ActionType.delete,
            ActionType.move,
        ]:
            await reload_redis(for_space=data.space_name)
            return
        
        if data.resource_type in ResourceType.schema and data.action_type == ActionType.create:
            await operational_repo.create_application_indexes(for_space=data.space_name, del_docs=False)

        dto_dto: EntityDTO = EntityDTO.from_event_data(data)
        if data.action_type == ActionType.delete:
            await operational_repo.delete(dto_dto)

            return

        dto = EntityDTO.from_event_data(data)
        meta = await db.load_or_none(dto) # type: ignore
        if not meta:
            return

        if data.action_type in [
            ActionType.create,
            ActionType.update,
            ActionType.progress_ticket,
        ]:

            await operational_repo.create(dto_dto, meta)

        elif data.action_type == ActionType.move and data.shortname is not None:
            await operational_repo.move(
                space_name=data.space_name,
                src_subpath=data.attributes["src_subpath"],
                src_shortname=data.attributes["src_shortname"],
                dest_subpath=data.subpath,
                dest_shortname=data.shortname,
                meta=meta,
            )

    async def update_parent_entry_payload_string(self) -> None:
        subpath_parts = self.data.subpath.strip("/").split("/")
        if len(subpath_parts) <= 1:
            return
        parent_subpath, parent_shortname = (
            "/".join(subpath_parts[:-1]),
            subpath_parts[-1],
        )
        parent_dto_dto = EntityDTO(
            space_name=self.data.space_name,
            branch_name=self.data.branch_name,
            schema_shortname="meta",
            shortname=parent_shortname,
            subpath=parent_subpath,
        )
        meta: None | core.Meta = await operational_repo.find(parent_dto_dto)

        if not meta:
            return

        await operational_repo.create(dto=parent_dto_dto, meta=meta)
