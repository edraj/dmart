from models.core import Folder, PluginBase, Event, User
from models.enums import ResourceType
from fastapi.logger import logger
from data_adapters.adapter import data_adapter as db


class Plugin(PluginBase):
    async def hook(self, data: Event):
        # Type narrowing for PyRight
        if (
            not isinstance(data.shortname, str)
            or not isinstance(data.resource_type, ResourceType)
        ):
            logger.error("invalid data at resource_folders_creation")
            return
        print(data.resource_type == ResourceType.user)
        if data.resource_type == ResourceType.user:
            user = await db.load_or_none(
                space_name='management',
                subpath='/users',
                shortname=data.shortname,
                class_type=User,
            )
            if user is None:
                return
            if "seller" in user.roles:
                await db.internal_sys_update_model(
                    space_name='management',
                    subpath='/users',
                    meta=user,
                    updates={"is_msisdn_verified": True, "is_email_verified": True,"is_active": True}
                )

                folders = [
                    ("e_commerce", "available", data.shortname),
                    ("e_commerce", "sellers_coupons", data.shortname),
                    ("e_commerce", "discounts", data.shortname),
                    ("e_commerce", "orders", data.shortname),
                    ("e_commerce", "shipping_and_service", data.shortname),
                    ("e_commerce", "warranties", data.shortname),
                ]

                for folder in folders:
                    await db.internal_save_model(
                        space_name=folder[0],
                        subpath=folder[1],
                        meta=Folder(
                            shortname=folder[2],
                            is_active=True,
                            owner_shortname=data.user_shortname,
                        ),
                    )
