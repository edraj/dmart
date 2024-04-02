
from datetime import datetime
from typing import Any, Type

from fastapi.logger import logger

from db.base_db import BaseDB
from models.api import Query
from models.core import EntityDTO, Meta, MetaChild, Record
from models.enums import ContentType, ResourceType, SortType
from utils.redis_services import RedisServices
from utils.settings import settings
from utils import repository


class RedisDB(BaseDB):
    
    async def search(
        self,
        space_name: str,
        branch_name: str | None,
        search: str,
        filters: dict[str, str | list],
        limit: int,
        offset: int,
        exact_subpath: bool = False,
        sort_type: SortType = SortType.ascending,
        sort_by: str | None = None,
        highlight_fields: list[str] | None = None,
        schema_name: str = "meta",
        return_fields: list = [],
    ) -> dict[str, Any]:
        async with RedisServices() as redis:
            return await redis.search(
                space_name,
                branch_name,
                search,
                filters,
                limit,
                offset,
                exact_subpath,
                sort_type,
                sort_by,
                highlight_fields,
                schema_name,
                return_fields,
            )

    async def find(self, entity: EntityDTO) -> None | dict[str, Any]:
        if not entity.schema_shortname:
            return None
        
        async with RedisServices() as redis:
            return await redis.get_doc_by_id(
                redis.generate_doc_id(
                    space_name=entity.space_name,
                    branch_name=entity.branch_name,
                    schema_shortname=entity.schema_shortname,
                    subpath=entity.subpath,
                    shortname=entity.shortname
                )
            )

    
    async def find_by_id(self, id: str) -> dict[str, Any]:
        async with RedisServices() as redis:
            return await redis.get_doc_by_id(id)

    async def create(self, entity: EntityDTO, meta: Meta, payload: dict[str, Any] = {}) -> bool:
        try:
            async with RedisServices() as redis:
                meta_doc_id, meta_json = redis.prepate_meta_doc(
                    entity.space_name, entity.branch_name, entity.subpath, meta
                )
                meta_json["payload_string"] = await repository.generate_payload_string(
                    space_name=entity.space_name,
                    subpath=meta_json["subpath"],
                    shortname=meta_json["shortname"],
                    branch_name=entity.branch_name,
                    payload=payload,
                )
                await redis.save_doc(meta_doc_id, meta_json)
                if payload:
                    payload.update(meta_json)
                    await redis.save_payload_doc(
                        entity.space_name,
                        entity.branch_name,
                        entity.subpath,
                        meta,
                        payload,
                        entity.resource_type if entity.resource_type else ResourceType.content,
                    )
            return True
        except Exception as e:
            logger.error(f"Error at RedisDB.create: {e.args}")
            return False
        
    async def save_at_id(self, id: str, doc: dict[str, Any] = {}) -> bool:
        try:
            async with RedisServices() as redis:
                await redis.save_doc(id, doc)
            return True
        except Exception as e:
            logger.error(f"Error at RedisDB.save_at_id: {e.args}")
            return False

    async def update(self, entity: EntityDTO, meta: Meta, payload: dict[str, Any] = {}) -> bool:
        # Redis will overwrite the existing documents
        return await self.create(entity, meta, payload)

    async def delete(self, entity: EntityDTO, meta: Meta) -> bool:
        try:
            async with RedisServices() as redis:
                doc_id = redis.generate_doc_id(
                    entity.space_name,
                    entity.branch_name,
                    "meta",
                    entity.shortname,
                    entity.subpath,
                )
                meta_doc = await redis.get_doc_by_id(doc_id)
                # Delete the meta doc
                await redis.delete_doc(
                    entity.space_name,
                    entity.branch_name,
                    "meta",
                    entity.shortname,
                    entity.subpath,
                )
                # Delete the payload doc
                await redis.delete_doc(
                    entity.space_name,
                    entity.branch_name,
                    (
                        meta_doc.get("payload", {}).get("schema_shortname", "meta")
                        if meta_doc
                        else "meta"
                    ),
                    entity.shortname,
                    entity.subpath,
                )
                return True
        except Exception as e:
            logger.error(f"Error at RedisDB.delete: {e.args}")
            return False

    async def move(
        self,
        space_name: str,
        src_subpath: str,
        src_shortname: str,
        dest_subpath: str | None,
        dest_shortname: str | None,
        meta: Meta,
        branch_name: str | None = settings.default_branch,
    ) -> bool:
        try:
            async with RedisServices() as redis:
                await redis.move_meta_doc(
                    space_name,
                    branch_name,
                    src_shortname,
                    src_subpath,
                    dest_subpath,
                    meta,
                )
                if meta.payload and meta.payload.schema_shortname:
                    await redis.move_payload_doc(
                        space_name,
                        branch_name,
                        meta.payload.schema_shortname,
                        src_shortname,
                        src_subpath,
                        meta.shortname,
                        dest_subpath,
                    )
                return True
        except Exception as e:
            logger.error(f"Error at RedisDB.move: {e.args}")
            return False

    async def clone(
        self,
        src_space: str,
        dest_space: str,
        src_subpath: str,
        src_shortname: str,
        dest_subpath: str,
        dest_shortname: str,
        class_type: Type[MetaChild],
        branch_name: str | None = settings.default_branch,
    ) -> bool:
        meta_doc = await self.find_or_fail(EntityDTO(
            space_name=src_space,
            subpath=src_subpath,
            shortname=src_shortname,
            schema_shortname="meta"
        ))
        
        payload_doc = await self.find_by_id(meta_doc["payload_doc_id"])
        
        return await self.create(
            entity=EntityDTO(
                space_name=dest_space,
                subpath=dest_subpath,
                shortname=dest_shortname,
                resource_type=meta_doc.get("resource_type", ResourceType.content)
            ),
            meta=Meta(**meta_doc),
            payload=payload_doc
        )
        