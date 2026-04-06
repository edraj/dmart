from models.core import Event, PluginBase
from utils.async_request import AsyncRequest
from utils.settings import settings


class Plugin(PluginBase):
    async def hook(self, data: Event):
        all_MKW = "__ALL__"

        state = data.attributes.get("state", all_MKW)

        # if subpath = parent/child
        # send to channels with subpaths "parent" and "parent/child"
        channels = []
        subpath = ""
        for subpath_part in data.subpath.split("/"):
            if not subpath_part:
                continue
            subpath += subpath_part

            # Consider channels with __ALL__ magic word
            if not subpath.startswith("/"):
                subpath = "/" + subpath
            channels.extend(
                [
                    f"{data.space_name}:{subpath}:{all_MKW}:{data.action_type}:{state}",
                    f"{data.space_name}:{subpath}:{all_MKW}:{all_MKW}:{state}",
                    f"{data.space_name}:{subpath}:{all_MKW}:{data.action_type}:{all_MKW}",
                    f"{data.space_name}:{subpath}:{all_MKW}:{all_MKW}:{all_MKW}",
                ]
            )
            if data.schema_shortname:
                channels.extend(
                    [
                        f"{data.space_name}:{subpath}:{data.schema_shortname}:{data.action_type}:{state}",
                        f"{data.space_name}:{subpath}:{data.schema_shortname}:{all_MKW}:{state}",
                        f"{data.space_name}:{subpath}:{data.schema_shortname}:{data.action_type}:{all_MKW}",
                        f"{data.space_name}:{subpath}:{data.schema_shortname}:{all_MKW}:{all_MKW}",
                    ]
                )
            subpath += "/"

        # Use WebTransport HTTP endpoint (TCP) for broadcasting
        # WebTransport server runs on webtransport_port and exposes HTTP endpoints
        webtransport_url = f"http://{settings.listening_host}:{settings.webtransport_port}"

        async with AsyncRequest() as client:
            print({
                "url": f"{webtransport_url}/broadcast-to-channels",
                "channels": [*set(channels)],
                "message": {
                    "title": "updated",
                    "subpath": data.subpath,
                    "space": data.space_name,
                    "shortname": data.shortname,
                    "action_type": data.action_type,
                    "owner_shortname": data.user_shortname,
                }
            })
            await client.post(
                f"{webtransport_url}/broadcast-to-channels",
                json={
                    "type": "notification_subscription",
                    "channels": [*set(channels)],
                    "message": {
                        "title": "updated",
                        "subpath": data.subpath,
                        "space": data.space_name,
                        "shortname": data.shortname,
                        "action_type": data.action_type,
                        "owner_shortname": data.user_shortname,
                    },
                },
            )
