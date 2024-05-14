from typing import Any
from db.manticore_db import ManticoreDB
from models.api import Query
from models.core import EntityDTO, Meta, Record
from models.enums import ContentType, ResourceType
from repositories.base_repo import BaseRepo
from utils import db as main_db

class ManticoreRepo(BaseRepo):
    
    def __init__(self) -> None:
        super().__init__(ManticoreDB())
    
    async def search(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[dict[str, Any]]]:
        return (0, [])

    async def aggregate(
        self, query: Query, user_shortname: str | None = None
    ) -> list[dict[str, Any]]:
        return []
    
    async def find(self, dto: EntityDTO) -> None | Meta:
        return Meta(shortname="", owner_shortname="")
    
    async def create(
        self, dto: EntityDTO, meta: Meta, payload: dict[str, Any] | None = None
    ) -> None:
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
    
    
    async def update(
        self, dto: EntityDTO, meta: Meta, payload: dict[str, Any] | None = None
    ) -> None:
        db_record = await self.db.find(dto)
        if not db_record:
            return
        print(db_record)
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

        await self.db.replace(meta_doc_id, db_record['meta']['id'], meta_json)

        if payload and db_record['payload']:
            payload_doc_id, payload_json = await self.db.prepare_payload_doc(
                dto,
                meta,
                payload,
            )
            payload_json.update(meta_json)
            
            await self.db.replace(payload_doc_id, db_record['payload']['id'], payload_json)
    
    async def db_doc_to_record(
        self,
        space_name: str,
        db_entry: dict,
        retrieve_json_payload: bool = False,
        retrieve_attachments: bool = False,
        filter_types: list | None = None,
    ) -> Record:
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
        return (0, [])

    
