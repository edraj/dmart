from models.enums import QueryType
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
from utils.operational_repository import operational_repo
from utils.data_database import data_adapter as db
import models.api as api
from fastapi import status


async def is_space_exist(space_name):
    if settings.active_data_db == "file":
        spaces = await operational_repo.find_by_id("spaces")
        if space_name not in spaces:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message="Space name provided is empty or invalid [3]",
                ),
            )

    else:
        _, spaces = await db.query(api.Query(type=QueryType.spaces, space_name="management", subpath="/"))
        if space_name not in [space.shortname for space in spaces]:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message="Space name provided is empty or invalid [3]",
                ),
            )
