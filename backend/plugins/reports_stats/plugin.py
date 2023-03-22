from os import scandir
from models.core import PluginBase, Event
from utils.access_control import access_control
from utils.db import load, load_resource_payload, update, save_payload_from_json
from models.core import Content
from models.api import Query
from utils.helpers import branch_path, flatten_dict
from utils.repository import get_last_updated_entry, serve_query
from utils.settings import settings
from datetime import datetime


class Plugin(PluginBase):
    async def hook(self, data: Event):
        print(f"{data=}")
        if data.subpath[0] == "/":
            data.subpath = data.subpath[1:]
        reports_path = (
            settings.spaces_folder
            / data.space_name
            / branch_path(data.branch_name)
            / data.subpath
        )

        shortname, ext = "", ""
        if data.attributes.get("shortname"):
            shortname, ext = data.attributes.get("shortname"), ".json"
        else:
            reports_iterator = scandir(reports_path)
            for report_entry in reports_iterator:
                if not report_entry.is_file():
                    continue

                shortname, ext = report_entry.name.split(".")
                if ext == "json":
                    break
        subpath, class_type = "reports", Content

        report_meta = await load(
            space_name=data.space_name,
            subpath=subpath,
            shortname=shortname,  # type: ignore
            class_type=class_type,
            user_shortname=data.user_shortname,
            branch_name=data.branch_name,
        )

        report_payload = load_resource_payload(
            space_name=data.space_name,
            subpath=subpath,
            filename=report_meta.payload.body,  # type: ignore
            class_type=class_type,
            branch_name=data.branch_name,
        )
        old_version_flattend = {"payload.body": flatten_dict(report_payload)}
        report_query = Query(**report_payload["query"])
        report_query.limit = 0
        redis_query_policies = await access_control.get_user_query_policies(
            data.user_shortname
        )
        total, records = await serve_query(
            report_query, data.user_shortname, redis_query_policies
        )
        report_last_updated_entry = await get_last_updated_entry(
            data.space_name,
            data.branch_name,
            report_payload["query"]["filter_schema_names"],
            False,
            data.user_shortname,
        )

        report_payload["number_of_records"] = data.attributes.get("number_of_records", 0)
        if report_last_updated_entry:
            report_payload["last_updated"] = str(
                report_last_updated_entry.attributes["updated_at"]
            )
        report_payload["downloaded_by"] = data.user_shortname
        report_payload["last_downloaded"] = str(datetime.now())
        await update(
            data.space_name,
            "reports",
            report_meta,
            old_version_flattend,
            {"payload.body": flatten_dict(report_payload)},
            [
                "payload.body.number_of_records",
                "payload.body.last_updated",
                "payload.body.downloaded_by",
                "payload.body.last_downloaded",
            ],
            data.branch_name,
            data.user_shortname,
        )
        await save_payload_from_json(
            data.space_name,
            "reports",
            report_meta,
            report_payload,
            data.branch_name,
        )

        data.resource_type = "content"
        data.shortname = data.attributes.get("shortname")
        data.subpath = "reports"
        # await RedisDBUpdatePlugin().hook(data)
