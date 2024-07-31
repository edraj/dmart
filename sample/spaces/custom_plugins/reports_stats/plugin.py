from os import scandir
from re import sub
from models.core import PluginBase, Event
from utils.access_control import access_control
from data_adapters.adapter import data_adapter as db
from models.core import Content
from models.api import Query
from utils.repository import get_last_updated_entry, serve_query, internal_sys_update_model
from utils.settings import settings



class Plugin(PluginBase):
    async def hook(self, data: Event):
        if data.subpath[0] == "/":
            data.subpath = data.subpath[1:]
        reports_path = (
            settings.spaces_folder
            / data.space_name
            / data.subpath
        )

        reports_iterator = scandir(reports_path)
        for report_entry in reports_iterator:
            if not report_entry.is_file():
                continue

            shortname, _ = report_entry.name.split(".")
            subpath, class_type = "reports", Content

            try:
                report_meta = await db.load(
                    space_name=data.space_name,
                    subpath=subpath,
                    shortname=shortname,  # type: ignore
                    class_type=class_type,
                    user_shortname=data.user_shortname,
                )

                report_payload = await db.load_resource_payload(
                    space_name=data.space_name,
                    subpath=subpath,
                    filename=report_meta.payload.body,  # type: ignore
                    class_type=class_type,
                )
            except Exception:
                continue
            
            report_payload["query"]["search"] = sub(
                r"\$\w*", "", report_payload["query"]["search"]
            )
            
            report_query = Query(**report_payload["query"])
            report_query.limit = 0
            redis_query_policies = await access_control.get_user_query_policies(
                data.user_shortname, report_query.space_name, report_query.subpath
            )
            total, records = await serve_query(
                report_query, data.user_shortname, redis_query_policies
            )
            report_last_updated_entry = await get_last_updated_entry(
                data.space_name,
                report_payload["query"]["filter_schema_names"],
                False,
                data.user_shortname,
            )

            report_updates: dict = {
                "number_of_records": total
            }
            if report_last_updated_entry:
                report_updates["last_updated"] = str(
                    report_last_updated_entry.attributes["updated_at"]
                )

            await internal_sys_update_model(
                data.space_name,
                "reports",
                report_meta,
                report_updates
            )

