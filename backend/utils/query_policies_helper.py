from models.enums import ResourceType
from utils.settings import settings


def generate_query_policies(
        space_name: str,
        subpath: str,
        resource_type: str,
        is_active: bool,
        owner_shortname: str,
        owner_group_shortname: str | None,
        entry_shortname: str | None = None,
) -> list:
    subpath_parts = ["/"]
    subpath_parts += subpath.strip("/").split("/")

    if resource_type == ResourceType.folder and entry_shortname:
        subpath_parts.append(entry_shortname)

    query_policies: list = []
    full_subpath = ""
    for subpath_part in subpath_parts:
        full_subpath += subpath_part
        query_policies.append(
            f"{space_name}:{full_subpath.strip('/')}:{resource_type}:{str(is_active).lower()}:{owner_shortname}"
        )
        if owner_group_shortname is None:
            query_policies.append(
                f"{space_name}:{full_subpath.strip('/')}:{resource_type}:{str(is_active).lower()}"
            )
        else:
            query_policies.append(
                f"{space_name}:{full_subpath.strip('/')}:{resource_type}:{str(is_active).lower()}:{owner_group_shortname}"
            )

        full_subpath_parts = full_subpath.split("/")
        if len(full_subpath_parts) > 1:
            subpath_with_magic_keyword = (
                    "/".join(full_subpath_parts[:1]) + "/" + settings.all_subpaths_mw
            )
            if len(full_subpath_parts) > 2:
                subpath_with_magic_keyword += "/" + "/".join(full_subpath_parts[2:])
            query_policies.append(
                f"{space_name}:{subpath_with_magic_keyword.strip('/')}:{resource_type}:{str(is_active).lower()}"
            )

        if full_subpath == "/":
            full_subpath = ""
        else:
            full_subpath += "/"

    return query_policies
