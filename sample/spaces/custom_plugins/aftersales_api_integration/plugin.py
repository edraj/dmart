from models import core
from models.core import PluginBase, Event
from models.enums import ContentType, ResourceType
from utils import db
from utils.async_request import AsyncRequest
from utils.db import load, load_resource_payload, save_payload_from_json
from fastapi.logger import logger
from utils.redis_services import RedisServices
from utils.settings import settings


class Plugin(PluginBase):

    async def hook(self, data: Event):

        # Type narrowing for PyRight
        if not isinstance(data.resource_type, ResourceType) or not isinstance(data.shortname, str):
            logger.error(f"invalid data at aftersales_api_integration")
            return

        primary_roles = [
            'account_manager',
            'zain_superadmin',
            'b2c',
            'distributor',
            'sales_rep',
            'activating_pos',
            'voucher_pos',
            'ros',
            'zain_lite',
            'd2d_promoter',
            'franchise',
            'd2d_promoter'
        ]
        required_update = False

        # RECOMMENDED: load the meta entry from the db
        meta: core.Ticket = await load(
            space_name=data.space_name,
            subpath=data.subpath,
            shortname=data.shortname,
            class_type=core.Ticket,
            user_shortname=data.user_shortname,
            branch_name=data.branch_name
        )
        # meta: core.Ticket = core.Ticket.from_record(
        #     record=core.Record(
        #         resource_type=data.resource_type,
        #         subpath=data.subpath,
        #         shortname=data.shortname,
        #         attributes=data.attributes
        #     ), owner_shortname=data.user_shortname
        # )

        payload = load_resource_payload(
            space_name=data.space_name,
            subpath=data.subpath,
            filename=f"{data.shortname}.json",  # type: ignore
            class_type=core.Ticket,
            branch_name=data.branch_name
        )
        # inject reporter details
        user: core.User = await db.load(
            space_name=settings.management_space,
            subpath="users",
            shortname=data.user_shortname,
            class_type=core.User,
            user_shortname=data.user_shortname,
            branch_name=settings.management_space_branch,
        )
        if not user.payload or type(user.payload.body) != str:
            raise Exception("Invalid User data at aftersales_api_integration")
        payload_body = db.load_resource_payload(
            space_name=settings.management_space,
            subpath="users",
            filename=user.payload.body,
            class_type=core.User,
            branch_name=settings.management_space_branch,
        )
        channel_location = {}
        if payload_body.get('channel_shortname'):
            channel: core.User = await db.load(
                space_name=settings.management_space,
                subpath="users",
                shortname=payload_body.get('channel_shortname', ''),
                class_type=core.User,
                user_shortname=data.user_shortname,
                branch_name=settings.management_space_branch,
            )
            if not channel.payload or type(channel.payload.body) != str:
                raise Exception("Invalid channel")
            channel_body = db.load_resource_payload(
                space_name=settings.management_space,
                subpath="users",
                filename=channel.payload.body,
                class_type=core.User,
                branch_name=settings.management_space_branch,
            )
            channel_location = channel_body.get('location')
        role = ''
        for user_role in user.roles:
            if user_role in primary_roles:
                role = user_role
                break

        governorate_shortname = ''
        if payload_body.get('address', {}).get('governorate', {}).get('name'):
            governorate_shortname = payload_body['address']['governorate']['name']

        distributor_shortname = ''
        if payload_body.get('address', {}).get('governorate', {}).get('distributor_shortname'):
            distributor_shortname = payload_body['address']['governorate']['distributor_shortname']

        display_name = ''
        if user.displayname and user.displayname.en:
            display_name = user.displayname.en

        reporter = core.Reporter(
            type=role,
            name=display_name,
            channel=user.owner_shortname,
            distributor=governorate_shortname,
            governorate=distributor_shortname,
            msisdn=user.msisdn,
            channel_address=channel_location
        )
        required_update = True
        meta.reporter = reporter

        # inject check_usim_irm_status [registration_name, sim_status]
        try:
            if data.space_name == 'b2c' and 'tickets' in data.subpath:
                msisdn = data.attributes.get('payload', {}).get('body', {}).get('msisdn')
                if msisdn:
                    async with AsyncRequest() as client:
                        response = await client.get(
                            url=f"{settings.middleware_api}/api/sim/check_subscriber_irm_status/{msisdn}",
                            headers={'Cookie': f'auth_token={data.attributes.get("logged_in_user_token")}'}
                        )
                        response_json: dict = await response.json()

                    irm_info = response_json.get('data', {}).get('irm_info', {})
                    crm_status = response_json.get('data', {}).get('crm_status', {})
                    if irm_info:
                        payload['registration_name'] = str(irm_info.get('Subscriber'))
                        payload['irm_info'] = irm_info

                    if crm_status:
                        payload['sim_status'] = str((crm_status.get('crm_status_code') == 'B01'
                                                     and str(crm_status.get('cbs_status_code')) == '1'))

                    required_update = True
        except Exception as e:
            logger.error(f"Plugin:aftersales_api_integration:{str(e)}")

        if not required_update:
            return

        await db.update(
            space_name=data.space_name,
            subpath=data.subpath,
            meta=meta,
            old_version_flattend={},
            new_version_flattend={},
            updated_attributes_flattend=[],
            branch_name=data.branch_name,
            user_shortname=data.user_shortname,
            schema_shortname=data.schema_shortname,
        )
        await save_payload_from_json(
            data.space_name,
            data.subpath,
            meta,
            payload,
            data.branch_name
        )
        redis = await RedisServices()
        meta_doc_id, meta_json = await redis.save_meta_doc(data.space_name, data.branch_name, data.subpath, meta)
        if(
            meta.payload and 
            meta.payload.content_type == ContentType.json and
            type(meta.payload.body) == str
        ):
            payload = db.load_resource_payload(
                space_name=data.space_name,
                subpath=data.subpath,
                filename=meta.payload.body,
                class_type=core.Ticket,
                branch_name=data.branch_name
            )

            payload.update(meta_json)
            await redis.save_payload_doc(
                data.space_name,
                data.branch_name,
                data.subpath,
                meta,
                payload,
                data.resource_type,
            )
