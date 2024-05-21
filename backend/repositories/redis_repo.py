from datetime import datetime
import sys

from db.redis_db import RedisDB
from repositories.base_repo import BaseRepo
from typing import Any
from models.api import Query, RedisAggregate, RedisReducer
from models.core import EntityDTO, Meta, Record
from models.enums import ContentType, QueryType, ResourceType, SortType
from utils.helpers import branch_path, camel_case
from utils.settings import settings
from utils import db as main_db
from utils.access_control import access_control

class RedisRepo(BaseRepo):

    def __init__(self) -> None:
        super().__init__(RedisDB())


    async def search(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[dict[str, Any]]]:
        if query.type != QueryType.search:
            return 0, []

        search_res: list[dict[str, Any]] = []
        total: int = 0

        if not query.filter_schema_names:
            query.filter_schema_names = ["meta"]

        created_at_search = ""

        if query.from_date and query.to_date:
            created_at_search = (
                "[" + f"{query.from_date.timestamp()} {query.to_date.timestamp()}" + "]"
            )

        elif query.from_date:
            created_at_search = (
                "["
                + f"{query.from_date.timestamp()} {datetime(2199, 12, 31).timestamp()}"
                + "]"
            )

        elif query.to_date:
            created_at_search = (
                "["
                + f"{datetime(2010, 1, 1).timestamp()} {query.to_date.timestamp()}"
                + "]"
            )

        limit = query.limit
        offset = query.offset
        if len(query.filter_schema_names) > 1 and query.sort_by:
            limit += offset
            offset = 0

        query_policies: list[str] | None = None
        if user_shortname:
            query_policies = await access_control.user_query_policies(
                user_shortname=user_shortname,
                space=query.space_name,
                subpath=query.subpath,
            )
        for schema_name in query.filter_schema_names:
            redis_res = await self.db.search(
                space_name=query.space_name,
                branch_name=query.branch_name,
                schema_name=schema_name,
                search=str(query.search),
                filters={
                    "resource_type": query.filter_types or [],
                    "shortname": query.filter_shortnames or [],
                    "tags": query.filter_tags or [],
                    "subpath": [query.subpath],
                    "query_policies": query_policies,
                    "user_shortname": user_shortname,
                    "created_at": created_at_search,
                },
                exact_subpath=query.exact_subpath,
                limit=limit,
                offset=offset,
                highlight_fields=list(query.highlight_fields.keys()),
                sort_by=query.sort_by,
                sort_type=query.sort_type or SortType.ascending,
            )

            if redis_res:
                search_res.extend(redis_res[1])
                total += redis_res[0]
        return total, search_res

    async def aggregate(
        self, query: Query, user_shortname: str | None = None
    ) -> list[Any]:
        if not query.aggregation_data:
            return []

        if len(query.filter_schema_names) > 1:
            return []

        created_at_search = ""
        if query.from_date and query.to_date:
            created_at_search = (
                "[" + f"{query.from_date.timestamp()} {query.to_date.timestamp()}" + "]"
            )

        elif query.from_date:
            created_at_search = (
                "["
                + f"{query.from_date.timestamp()} {datetime(2199, 12, 31).timestamp()}"
                + "]"
            )

        elif query.to_date:
            created_at_search = (
                "["
                + f"{datetime(2010, 1, 1).timestamp()} {query.to_date.timestamp()}"
                + "]"
            )

        query_policies: list[str] | None = None
        if user_shortname:
            query_policies = await access_control.user_query_policies(
                user_shortname=user_shortname,
                space=query.space_name,
                subpath=query.subpath,
            )
        
        return await self.db.aggregate(
            space_name=query.space_name,
            branch_name=query.branch_name,
            schema_name=query.filter_schema_names[0],
            search=query.search,
            filters={
                "resource_type": query.filter_types or [],
                "shortname": query.filter_shortnames or [],
                "subpath": [query.subpath],
                "query_policies": query_policies,
                "created_at": created_at_search,
            },
            load=query.aggregation_data.load if isinstance(query.aggregation_data, RedisAggregate) else [],
            group_by=query.aggregation_data.group_by if isinstance(query.aggregation_data, RedisAggregate) else [],
            reducers=query.aggregation_data.reducers if isinstance(query.aggregation_data, RedisAggregate) else [],
            exact_subpath=query.exact_subpath,
            sort_by=query.sort_by,
            limit=query.limit,
            sort_type=query.sort_type or SortType.ascending,
        )

    async def find(self, dto: EntityDTO) -> None | Meta:
        """Return an object of the corresponding class of the dto.resource_type
        default dto.resource_type is ResourceType.content
        """
        user_document = await self.db.find(dto)

        if not user_document:
            return None

        try:
            return dto.class_type.model_validate(user_document) #type: ignore
        except Exception as _:
            return None

    async def create(self, dto: EntityDTO, meta: Meta, payload: dict[str, Any] | None = None) -> None:
        meta_doc_id, meta_json = await self.db.prepare_meta_doc(
            dto.space_name, dto.branch_name, dto.subpath, meta
        )

        if payload is None:
            payload = {}
        if (
            not payload
            and meta.payload
            and meta.payload.content_type == ContentType.json
            and isinstance(meta.payload.body, str)
        ):
            payload = await main_db.load_resource_payload(dto)
            

        meta_json["payload_string"] = await self.generate_payload_string(
            dto, payload
        )

        await self.db.save_at_id(meta_doc_id, meta_json)

        if payload:
            payload_doc_id, payload_json = await self.db.prepare_payload_doc(
                dto,
                meta,
                payload,
            )
            payload_json.update(meta_json)
            await self.db.save_at_id(payload_doc_id, payload_json)
            
    async def update(self, dto: EntityDTO, meta: Meta, payload: dict[str, Any] | None = None) -> None:
        await self.create(dto, meta, payload)

    

    async def db_doc_to_record(
        self,
        space_name: str,
        db_entry: dict,
        retrieve_json_payload: bool = False,
        retrieve_attachments: bool = False,
        filter_types: list | None = None,
    ) -> Record:
        meta_doc_content = {}
        payload_doc_content = {}
        resource_class = getattr(
            sys.modules["models.core"],
            camel_case(db_entry["resource_type"]),
        )

        for key, value in db_entry.items():
            if key in resource_class.model_fields.keys():
                meta_doc_content[key] = value
            elif key not in self.db.SYS_ATTRIBUTES:
                payload_doc_content[key] = value

        dto = EntityDTO(
            space_name=space_name,
            subpath=db_entry["subpath"],
            shortname=db_entry["shortname"],
            resource_type=db_entry["resource_type"],
        )
        # Get payload db_entry
        if (
            not payload_doc_content
            and retrieve_json_payload
            and "payload_doc_id" in db_entry
        ):
            payload_doc_content = await self.get_payload_doc(
                db_entry["payload_doc_id"], db_entry["resource_type"]
            )

        # Get lock data
        locked_data = await self.get_lock_doc(dto)

        meta_doc_content["created_at"] = datetime.fromtimestamp(
            meta_doc_content["created_at"]
        )
        meta_doc_content["updated_at"] = datetime.fromtimestamp(
            meta_doc_content["updated_at"]
        )
        resource_obj = resource_class.model_validate(meta_doc_content)
        resource_base_record = resource_obj.to_record(
            db_entry["subpath"],
            meta_doc_content["shortname"],
            [],
            db_entry["branch_name"],
        )

        if locked_data:
            resource_base_record.attributes["locked"] = locked_data

        # Get attachments
        entry_path = (
            settings.spaces_folder
            / f"{space_name}/{branch_path(db_entry['branch_name'])}/{db_entry['subpath']}/.dm/{meta_doc_content['shortname']}"
        )
        if retrieve_attachments and entry_path.is_dir():
            resource_base_record.attachments = await main_db.get_entry_attachments(
                subpath=f"{db_entry['subpath']}/{meta_doc_content['shortname']}",
                branch_name=db_entry["branch_name"],
                attachments_path=entry_path,
                filter_types=filter_types,
                retrieve_json_payload=retrieve_json_payload,
            )

        if (
            retrieve_json_payload
            and resource_base_record.attributes["payload"]
            and resource_base_record.attributes["payload"].content_type
            == ContentType.json
        ):
            resource_base_record.attributes["payload"].body = payload_doc_content

        if isinstance(resource_base_record, Record):
            return resource_base_record
        else:
            return Record()

    async def tags_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        query.sort_by = "tags"
        query.aggregation_data = RedisAggregate(
            group_by=["@tags"],
            reducers=[RedisReducer(reducer_name="r_count", alias="freq")],
        )
        rows = await self.aggregate(query=query, user_shortname=user_shortname)
        

        return 1, [
            Record(
                resource_type=ResourceType.content,
                shortname="tags_frequency",
                subpath=query.subpath,
                attributes={"result": rows},
            )
        ]

    async def random_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        records: list[Record] = []
        query.aggregation_data = RedisAggregate(
            load=["@__key"],
            group_by=["@resource_type"],
            reducers=[
                RedisReducer(
                    reducer_name="random_sample",
                    alias="id",
                    args=["@__key", query.limit],
                )
            ],
        )
        rows = await self.aggregate(query=query, user_shortname=user_shortname)
        ids = []
        for row in rows:
            ids.extend(row[3])
        docs: list[dict[str, Any]] = await self.list_by_ids(ids)
        total = len(ids)
        for doc in docs:
            if query.retrieve_json_payload and doc.get("payload_doc_id", None):
                doc["payload"]["body"] = await self.get_payload_doc(
                    doc["payload_doc_id"], doc["resource_type"]
                )
            record = Record(
                shortname=doc["shortname"],
                resource_type=doc["resource_type"],
                uuid=doc["uuid"],
                branch_name=doc["branch_name"],
                subpath=doc["subpath"],
                attributes={"payload": doc.get("payload")},
            )
            entry_path = (
                settings.spaces_folder
                / f"{query.space_name}/{branch_path(doc['branch_name'])}/{doc['subpath']}/.dm/{doc['shortname']}"
            )
            if query.retrieve_attachments and entry_path.is_dir():
                record.attachments = await main_db.get_entry_attachments(
                    subpath=f"{doc['subpath']}/{doc['shortname']}",
                    branch_name=doc["branch_name"],
                    attachments_path=entry_path,
                    filter_types=query.filter_types,
                    include_fields=query.include_fields,
                    retrieve_json_payload=query.retrieve_json_payload,
                )
            records.append(record)

        return total, records

    # async def clone(
    #     self,
    #     src_space: str,
    #     dest_space: str,
    #     src_subpath: str,
    #     src_shortname: str,
    #     dest_subpath: str,
    #     dest_shortname: str,
    #     resource_type: ResourceType,
    #     branch_name: str | None = settings.default_branch,
    # ) -> bool:
    #     meta_doc = await self.find_or_fail(EntityDTO(
    #         space_name=src_space,
    #         subpath=src_subpath,
    #         shortname=src_shortname,
    #         schema_shortname="meta",
    #         resource_type=resource_type,
    #         branch_name=branch_name
    #     ))

    #     payload_doc = await self.find_by_id(meta_doc["payload_doc_id"])

    #     return await self.create(
    #         dto=EntityDTO(
    #             space_name=dest_space,
    #             subpath=dest_subpath,
    #             shortname=dest_shortname,
    #             resource_type=meta_doc.get("resource_type", ResourceType.content)
    #         ),
    #         meta=Meta(**meta_doc),
    #         payload=payload_doc
    #     )
