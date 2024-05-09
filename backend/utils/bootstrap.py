import asyncio
from models.enums import ResourceType
from utils.settings import settings
import models.core as core
from utils.regex import FILE_PATTERN, SPACES_PATTERN
from utils.operational_repo import operational_repo
from utils import db

async def load_permissions_and_roles() -> None:
    management_path = settings.spaces_folder / settings.management_space

    access_control_modules : dict[str, type[core.Meta]] = {
        "groups": core.Group,
        "roles": core.Role,
        "permissions": core.Permission
    }
    
    access_control_models: dict[str, list[core.Meta]] = {}

    for module_name, module_class in access_control_modules.items():
        path = management_path / module_name
        entries_glob = ".dm/*/meta.*.json"
        for one in path.glob(entries_glob):
            match = FILE_PATTERN.search(str(one))
            if not match or not one.is_file():
                continue
            shortname = match.group(1)
            try:
                dto = core.EntityDTO(
                    space_name=settings.management_space,
                    subpath=module_name,
                    shortname=shortname,
                    resource_type=ResourceType(module_class.__name__.lower()),
                    user_shortname="anonymous"
                )
                resource_obj : core.Meta = await db.load(dto)
                if resource_obj and resource_obj.is_active:
                    access_control_models.setdefault(module_name, [])
                    access_control_models[module_name].append(resource_obj)
            except Exception as ex:
                print(f"Error processing @{settings.management_space}/{module_name}/{shortname} ... ", ex)
                raise ex

    await create_user_permission_index_and_data()
    await store_modules_to_operational_db(access_control_models)
    
async def create_user_permission_index_and_data() -> None:
    await operational_repo.create_index_drop_existing(
        name="user_permission",
        fields={"name": "string"},
        prefix="users_permissions",
        delete_docs=True
    )
    
async def store_modules_to_operational_db(access_control_models: dict[str, list[core.Meta]]) -> None:
    for access_control_module, models in access_control_models.items():
        for model in models:
            await operational_repo.create(
                dto=core.EntityDTO(
                    space_name=settings.management_space,
                    branch_name=settings.management_space_branch,
                    subpath=access_control_module,
                    shortname=model.shortname
                ),
                meta=model
            )

async def load_spaces() -> None:
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

    await operational_repo.save_at_id("spaces", spaces)
        
        
async def bootstrap_all():
    await load_permissions_and_roles()
    await load_spaces()
    
    
if __name__ == "__main__":
    asyncio.run(bootstrap_all())