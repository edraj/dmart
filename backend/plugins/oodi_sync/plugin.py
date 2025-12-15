from aiohttp import ClientResponse
from models.core import Payload, PluginBase, Event, User
from data_adapters.adapter import data_adapter as db
from fastapi.logger import logger
from fastapi import status
from utils.async_request import AsyncRequest


class Plugin(PluginBase):
    async def hook(self, data: Event):
        """Hook to register user in OODI system upon user creation."""
        if not isinstance(data.shortname, str):
            logger.error("data.shortname is None and str is required at oodi_sync plugin")
            return

        OODI_URL = "http://10.90.33.7:32287" # UAT
        REGISTER_URL = f"{OODI_URL}/user/v2/register/anonymous"

        user: User = await db.load(
            space_name=data.space_name,
            subpath=data.subpath,
            shortname=data.shortname,
            class_type=User,
            user_shortname=data.user_shortname
        )

        async with AsyncRequest() as client:
            try:
                res: ClientResponse = await client.post(
                    REGISTER_URL,
                    json={
                        "email": user.email,
                        "language": user.language,
                        "phone": user.msisdn,
                        "iccid": (
                            user.payload.body.get("iccid")
                            if isinstance(user.payload, Payload)
                            and isinstance(user.payload.body, dict)
                            else None
                        ),
                    },
                )
                body = await res.json()
                if res.status > status.HTTP_201_CREATED:
                    logger.error(
                        f"plugins.oodi_sync, Failed to register user in OODI. Status: {res.status}. Body: {body}"
                    )
                    return

                await db.internal_sys_update_model(
                    space_name=data.space_name,
                    subpath=data.subpath,
                    meta=user,
                    updates={
                        "matrix_id": body.get("externalId"),  # Matrix ID
                        "external_id": body.get("userId"),  # OODI user ID
                    },
                    sync_redis=False,
                )

            except Exception as e:
                logger.error(f"plugins.oodi_sync, Failed to register user in OODI, Internal Error: {str(e)}")
                await db.internal_sys_update_model(
                    space_name=data.space_name,
                    subpath=data.subpath,
                    meta=user,
                    updates={
                        "is_active": False, "oodi_number": None
                    },
                    sync_redis=False,
                )
