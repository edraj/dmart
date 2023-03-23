from models.core import PluginBase, Event
# from utils.spaces import initialize_spaces
import utils.db as db
import models.core as core
from utils.async_request import AsyncRequest
from utils.settings import settings
import logging

logger = logging.getLogger(__name__)
class Plugin(PluginBase):


    async def hook(self, data: Event):
        # Type narrowing for PyRight
        if not isinstance(data.shortname, str):
            logger.error(f"invalid data at delivery_partner_api_call")
            return

        ticket_obj = await db.load(data.space_name, data.subpath, data.shortname, core.Ticket, data.user_shortname)
        if ticket_obj.owner_shortname in settings.talabatey_users_list.split(',') and ticket_obj.state=='approved' and data.action_type=='update':
            async with AsyncRequest() as client:
                response = await client.post(
                    f'http://zain-sim-swap.talabatey.com/auth/login',
                    json={"username": "test_m", "password": "pass"},
                    
                )
                auth_response=await response.json()
                token=auth_response.get('token')
                is_accepted='true' if ticket_obj.state=='approved' else 'false'
                response = await client.get(
                    f'http://zain-sim-swap.talabatey.com/confirmation/?transaction_id={data.shortname}&accepted={is_accepted}',
                    headers={"Authorization": f'Bearer {token}'},
                    
                )
                status = response.status
                logger.info(f"Request sent to talabatey for ticket {data.shortname}")
                