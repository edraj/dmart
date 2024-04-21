from os import scandir
from re import sub
from models.core import EntityDTO, PluginBase, Event
from models.enums import QueryType, ResourceType, SortType
from utils.db import load, load_resource_payload
from models.core import Content
from models.api import Query
from utils.helpers import branch_path
from utils.settings import settings
from utils.operational_repo import operational_repo


class Plugin(PluginBase):
    async def hook(self, data: Event):
        if data.subpath[0] == "/":
            data.subpath = data.subpath[1:]
        reports_path = (
            settings.spaces_folder
            / data.space_name
            / branch_path(data.branch_name)
            / data.subpath
        )

        reports_iterator = scandir(reports_path)
        for report_entry in reports_iterator:
            if not report_entry.is_file():
                continue

            shortname, _ = report_entry.name.split(".")
            subpath, class_type = "reports", Content

            try:
                report_entity = EntityDTO(
                    space_name=data.space_name,
                    subpath=subpath,
                    shortname=shortname,  # type: ignore
                    resource_type=ResourceType.content,
                    user_shortname=data.user_shortname,
                    branch_name=data.branch_name,
                )
                report_meta = await load(report_entity)

                report_payload = await load_resource_payload(report_entity)
            except Exception:
                continue
            
            report_payload["query"]["search"] = sub(
                r"\$\w*", "", report_payload["query"]["search"]
            )
            
            report_query = Query(**report_payload["query"])
            report_query.limit = 0
            total, records = await operational_repo.query_handler(
                report_query, data.user_shortname
            )
            report_query = Query(
                type=QueryType.search,
                space_name=data.space_name,
                branch_name=data.branch_name or settings.default_branch,
                subpath="/",
                search=f"@schema_shortname:{'|'.join(report_payload['query']['filter_schema_names'])}",
                filter_schema_names=["meta"],
                sort_by="updated_at",
                sort_type=SortType.descending,
                limit=50,  # to be in safe side if the query filtered out some invalid entries
            )
            _, records = await operational_repo.query_handler(report_query, data.user_shortname)

            report_last_updated_entry = records[0] if records else None

            report_updates: dict = {
                "number_of_records": total
            }
            if report_last_updated_entry:
                report_updates["last_updated"] = str(
                    report_last_updated_entry.attributes["updated_at"]
                )
                
            await operational_repo.internal_sys_update_model(report_entity, report_meta, report_updates)

