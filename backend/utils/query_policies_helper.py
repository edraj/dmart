from models.enums import ResourceType, ConditionType
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


async def get_user_query_policies(
    db,
    user_shortname: str,
    space_name: str,
    subpath: str
) -> list:
    """
    Generate list of query policies based on user's permissions
    ex: [
        "products:offers:content:true:admin_shortname", # IF conditions = {"is_active", "own"}
        "products:offers:content:true:*", # IF conditions = {"is_active"}
        "products:offers:content:false:admin_shortname|products:offers:content:true:admin_shortname",
        # ^^^ IF conditions = {"own"}
        "products:offers:content:*", # IF conditions = {}
    ]
    """
    user_permissions = await db.get_user_permissions(user_shortname)
    user_groups = (await db.load_user_meta(user_shortname)).groups or []
    user_groups.append(user_shortname)

    redis_query_policies = []
    for perm_key, permission in user_permissions.items():
        if (
                not perm_key.startswith(space_name) and
                not perm_key.startswith(settings.all_spaces_mw)
        ):
            continue
        perm_key = perm_key.replace(settings.all_spaces_mw, space_name)
        perm_key = perm_key.replace(settings.all_subpaths_mw, subpath.strip("/"))
        perm_key = perm_key.strip("/")
        if (
                ConditionType.is_active in permission["conditions"]
                and ConditionType.own in permission["conditions"]
        ):
            for user_group in user_groups:
                redis_query_policies.append(f"{perm_key}:true:{user_group}")
        elif ConditionType.is_active in permission["conditions"]:
            redis_query_policies.append(f"{perm_key}:true:*")
        elif ConditionType.own in permission["conditions"]:
            for user_group in user_groups:
                redis_query_policies.append(
                    f"{perm_key}:true:{user_shortname}|{perm_key}:false:{user_group}"
                )
        else:
            redis_query_policies.append(f"{perm_key}:*")
    return redis_query_policies