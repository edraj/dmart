from models.enums import QueryType
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
from utils.spaces import get_spaces
from data_adapters.adapter import data_adapter as db
import models.api as api
from fastapi import status


async def is_space_exist(space_name, should_exist=True):
    if settings.active_data_db == "file":
        spaces = await get_spaces()
        if (space_name in spaces) ^ should_exist:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message=f"Space name {space_name} provided is empty or invalid [3]",
                ),
            )

    else:
        _, spaces = await db.query(api.Query(type=QueryType.spaces, space_name="management", subpath="/"))
        if (space_name in [space.shortname for space in spaces]) ^ should_exist:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                api.Error(
                    type="request",
                    code=InternalErrorCode.INVALID_SPACE_NAME,
                    message=f"Space name {space_name} provided is empty or invalid [3]",
                ),
            )
