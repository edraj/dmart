
from datetime import datetime, timedelta
import json
from models.core import Content
from utils.db import load as load_meta
from utils.notification import send_notification
from utils.redis_services import RedisServices
from utils.repository import _sys_update_model
from utils.settings import settings
from fastapi.logger import logger
import asyncio

async def trigger_admin_notifications():
    from_time = int((datetime.now() - timedelta(minutes=15)).timestamp()*1000)
    to_time = int(datetime.now().timestamp()*1000)
    async with RedisServices() as redis_services:
        admin_notifications = await redis_services.search(
            space_name=settings.management_space,
            branch_name=settings.management_space_branch,
            schema_name="admin_notification_request",
            search=f"@subpath:/notifications/admin (-@status:finished) @scheduled_at:[{from_time} {to_time}]",
            filters={},
            limit=10000,
            offset=0
        )

    if admin_notifications["total"] == 0:
        return

    for notification_doc in admin_notifications["data"]:
        notification = json.loads(notification_doc.json)

        # Get notification receivers users
        async with RedisServices() as redis_services:
            receivers = await redis_services.search(
                space_name=settings.management_space,
                branch_name=settings.management_space_branch,
                search=f"@subpath:users @msisdn:{'|'.join(notification['msisdns'])}",
                filters={},
                limit=10000,
                offset=0
            )

        # Try to send the notification 
        # and update the notification status to finished
        try:
            if receivers:
                receivers_shortnames = set()
                for receiver in receivers['data']:
                    receivers_shortnames.add(json.loads(receiver.json)['shortname'])
                await send_notification(
                    notification_dict=notification,
                    receivers=receivers_shortnames
                )

            notification_meta = await load_meta(
                settings.management_space,
                notification["subpath"],
                notification["shortname"],
                Content,
                notification["owner_shortname"],
                settings.management_space_branch,
            )
            await _sys_update_model(
                settings.management_space,
                notification["subpath"],
                notification_meta,
                settings.management_space_branch,
                {"status": "finished"}
            )
        except Exception as e:
            logger.error(f"Error at sending/updating admin based notification: {e.args}")
            pass

        
if __name__ == "__main__":
    asyncio.run(trigger_admin_notifications())
