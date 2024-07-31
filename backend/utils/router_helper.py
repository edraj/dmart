from utils.internal_error_code import InternalErrorCode
from data_adapters.adapter import data_adapter as db
import models.api as api
from fastapi import status


async def is_space_exist(space_name, should_exist=True):

    space = await db.fetch_space(space_name)

    if (space is not None) ^ should_exist:
        raise api.Exception(
            status.HTTP_400_BAD_REQUEST,
            api.Error(
                type="request",
                code=InternalErrorCode.INVALID_SPACE_NAME,
                message=f"Space name {space_name} provided is empty or invalid [3]",
            ),
        )
