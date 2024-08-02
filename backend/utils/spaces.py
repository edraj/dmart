import models.core as core
from utils.settings import settings
from utils.redis_services import RedisServices
from utils.regex import SPACES_PATTERN


async def initialize_spaces() -> None:
    if settings.active_data_db == "file":
        if not settings.spaces_folder.is_dir():
            raise NotADirectoryError(
                f"{settings.spaces_folder} directory does not exist!"
            )

        spaces: dict[str, str] = {}
        for one in settings.spaces_folder.glob("*/.dm/meta.space.json"):
            match = SPACES_PATTERN.search(str(one))
            if not match:
                continue
            space_name = match.group(1)

            space_obj = core.Space.model_validate_json(one.read_text())
            spaces[space_name] = space_obj.model_dump_json()

        async with RedisServices() as redis_services:
            await redis_services.save_doc("spaces", spaces)


async def get_spaces() -> dict:
    async with RedisServices() as redis_services:
        value = await redis_services.get_doc_by_id("spaces")
        if isinstance(value, dict):
            return value
        return {}
