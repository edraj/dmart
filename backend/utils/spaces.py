import models.core as core
from utils.settings import settings
from utils.redis_services import RedisServices
from utils.regex import SPACES_PATTERN


async def initialize_spaces():
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

        branches_path = settings.spaces_folder / space_name / "branches"
        branches_names = [settings.default_branch]
        for branch in branches_path.glob("*/.dm/meta.branch.json"):
            branch_obj = core.Branch.model_validate_json(branch.read_text())
            branches_names.append(branch_obj.shortname)

        space_obj = core.Space.model_validate_json(one.read_text())
        space_obj.branches = branches_names
        spaces[space_name] = space_obj.model_dump_json()

    async with RedisServices() as redis_services:
        await redis_services.save_doc("spaces", spaces)


async def get_spaces() -> dict:
    async with RedisServices() as redis_services:
        return await redis_services.get_doc_by_id("spaces")
