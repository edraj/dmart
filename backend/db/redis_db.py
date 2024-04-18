import json
from re import A
from typing import Any

from fastapi.logger import logger

from db.base_db import BaseDB
from models.core import EntityDTO, Meta
from models.enums import LockAction, ResourceType, SortType
from utils.redis_services import RedisServices
from utils.settings import settings
from redis.commands.search.indexDefinition import IndexDefinition
from redis.commands.search.query import Query as RedisQuery


class RedisDB(BaseDB):

    async def search(
        self,
        space_name: str,
        search: str,
        filters: dict[str, str | list | None],
        limit: int,
        offset: int,
        exact_subpath: bool = False,
        sort_type: SortType = SortType.ascending,
        branch_name: str | None = None,
        sort_by: str | None = None,
        highlight_fields: list[str] | None = None,
        schema_name: str = "meta",
        return_fields: list = [],
    ) -> tuple[int, list[dict[str, Any]]]:
        async with RedisServices() as redis:
            res = await redis.search(
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
            return res[0], [json.loads(item) for item in res[1]]
        
    async def aggregate(
        self,
        space_name: str,
        search: str,
        filters: dict[str, str | list | None],
        group_by: list[str],
        reducers: list[Any],
        max: int = 10,
        branch_name: str = settings.default_branch,
        exact_subpath: bool = False,
        sort_type: SortType = SortType.ascending,
        sort_by: str | None = None,
        schema_name: str = "meta",
        load: list = [],
    ) -> list[Any]:
        async with RedisServices() as redis:
            res = await redis.aggregate(
            space_name,
            search,
            filters,
            group_by,
            reducers,
            max,
            branch_name,
            exact_subpath,
            sort_type,
            sort_by,
            schema_name,
            load,
            )
        return res

    async def free_search(
        self, index_name: str, search_str: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        try:
            async with RedisServices() as redis:
                ft_index = redis.ft(index_name)
                search_query = RedisQuery(query_string=search_str)
                search_query.paging(offset, limit)
                res = await ft_index.search(search_query)

                res_data: list[dict[str, Any]] = []
                if res and isinstance(res, dict) and "results" in res:
                    res_data = [
                        json.loads(item["extra_attributes"]["$"])
                        for item in res["results"]
                        if "extra_attributes" in item
                    ]

                return res_data

        except Exception as e:
            logger.error(f"Error at RedisDB.free_search: {e.args}")
            return []

    async def get_count(self, space_name: str, schema_shortname: str, branch_name: str = settings.default_branch) -> int:
        try:
            async with RedisServices() as redis:
                return await redis.get_count(space_name, branch_name, schema_shortname)

        except Exception as e:
            logger.error(f"Error at RedisDB.entity_doc_id: {e.args}")
            return 0
        
    async def entity_doc_id(self, entity: EntityDTO) -> str:
        if not entity.schema_shortname:
            raise Exception("schema_shortname is required to generate the doc_id")

        try:
            async with RedisServices() as redis:
                return redis.generate_doc_id(
                    space_name=entity.space_name,
                    subpath=entity.subpath,
                    branch_name=entity.branch_name,
                    schema_shortname=entity.schema_shortname,
                    shortname=entity.shortname,
                )

        except Exception as e:
            logger.error(f"Error at RedisDB.entity_doc_id: {e.args}")
            return ""

    async def find(self, entity: EntityDTO) -> None | dict[str, Any]:
        async with RedisServices() as redis:
            return await redis.get_doc_by_id(
                redis.generate_doc_id(
                    space_name=entity.space_name,
                    branch_name=entity.branch_name,
                    schema_shortname=entity.schema_shortname,
                    subpath=entity.subpath,
                    shortname=entity.shortname,
                )
            )

    async def find_key(self, key: str) -> str | None:
        try:
            async with RedisServices() as redis:
                return await redis.get_key(key)

        except Exception as e:
            logger.error(f"Error at RedisDB.find_key: {e.args}")
            return None

    async def set_key(self, key: str, value: str, ex=None, nx: bool = False) -> bool:
        try:
            async with RedisServices() as redis:
                return bool(await redis.set_key(key, value, ex, nx))

        except Exception as e:
            logger.error(f"Error at RedisDB.set_key: {e.args}")
            return False

    async def delete_keys(self, keys: list[str]) -> bool:
        try:
            async with RedisServices() as redis:
                return bool(await redis.del_keys(keys))

        except Exception as e:
            logger.error(f"Error at RedisDB.delete_key: {e.args}")
            return False

    async def find_by_id(self, id: str) -> dict[str, Any]:
        async with RedisServices() as redis:
            return await redis.get_doc_by_id(id)
        
    async def list_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        async with RedisServices() as redis:
            return await redis.get_docs_by_ids(ids)

    async def find_payload_data_by_id(
        self, id: str, resource_type: ResourceType
    ) -> dict[str, Any]:
        async with RedisServices() as redis:
            return await redis.get_payload_doc(id, resource_type)

    async def prepare_meta_doc(
        self, space_name: str, branch_name: str | None, subpath: str, meta: Meta
    ) -> tuple[str, dict[str, Any]]:
        async with RedisServices() as redis:
            return redis.prepate_meta_doc(space_name, branch_name, subpath, meta)

    async def prepare_payload_doc(
        self,
        entity: EntityDTO,
        meta: Meta,
        payload: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        async with RedisServices() as redis:
            return redis.prepare_payload_doc(
                entity.space_name, 
                entity.branch_name, 
                entity.subpath, 
                meta, 
                payload, 
                entity.resource_type
            )


    async def save_at_id(self, id: str, doc: dict[str, Any] = {}) -> bool:
        try:
            async with RedisServices() as redis:
                await redis.save_doc(id, doc)
            return True
        except Exception as e:
            logger.error(f"Error at RedisDB.save_at_id: {e.args}")
            return False

    async def delete_doc_by_id(self, id: str) -> bool:
        try:
            async with RedisServices() as redis:
                redis.json().delete(key=id)
            return True
        except Exception as e:
            logger.error(f"Error at RedisDB.delete_doc_by_id: {e.args}")
            return False

    async def delete(self, entity: EntityDTO) -> bool:
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

    async def list_indexes(self) -> set[str]:
        try:
            async with RedisServices() as redis:
                return await redis.list_indices()
        except Exception as e:
            logger.error(f"Error at RedisDB.is_index_exist: {e.args}")
            return set()

    async def drop_index(self, name: str, delete_docs: bool) -> bool:
        try:
            async with RedisServices() as redis:
                await redis.drop_index(name, delete_docs)

            return True
        except Exception as e:
            logger.error(f"Error at RedisDB.drop_index: {e.args}")
            return False

    async def create_index(self, name: str, fields: list[Any], **kwargs) -> bool:

        if "definition" not in kwargs or not isinstance(
            kwargs["definition"], IndexDefinition
        ):
            return False

        try:
            async with RedisServices() as redis:
                await redis.create_index_direct(
                    name, tuple(fields), kwargs["definition"]
                )

            return True
        except Exception as e:
            logger.error(f"Error at RedisDB.create_index: {e.args}")
            return False

    async def create_application_indexes(
        self,
        for_space: str | None = None,
        for_schemas: list | None = None,
        for_custom_indices: bool = True,
        del_docs: bool = True,
    ) -> None:
        try:
            async with RedisServices() as redis:
                await redis.create_indices(
                    for_space=for_space,
                    for_schemas=for_schemas,
                    for_custom_indices=for_custom_indices,
                    del_docs=del_docs,
                )

        except Exception as e:
            logger.error(f"Error at RedisDB.create_application_indexes: {e.args}")

    
    async def save_lock_doc(
        self, entity: EntityDTO, owner_shortname: str, ttl: int = settings.lock_period
    ) -> LockAction | None:
        try:
            async with RedisServices() as redis:
                return await redis.save_lock_doc(
                    space_name=entity.space_name,
                    branch_name=entity.branch_name,
                    subpath=entity.subpath,
                    payload_shortname=entity.shortname,
                    owner_shortname=owner_shortname,
                    ttl=ttl,
                )

        except Exception as e:
            logger.error(f"Error at RedisDB.save_lock_doc: {e.args}")
            return None

    async def get_lock_doc(self, entity: EntityDTO) -> dict[str, Any]:
        try:
            async with RedisServices() as redis:
                return await redis.get_lock_doc(
                    space_name=entity.space_name,
                    branch_name=entity.branch_name,
                    subpath=entity.subpath,
                    payload_shortname=entity.shortname,
                )

        except Exception as e:
            logger.error(f"Error at RedisDB.get_lock_doc: {e.args}")
            return {}
    
    async def is_locked_by_other_user(
        self, entity: EntityDTO
    ) -> bool:
        try:
            async with RedisServices() as redis:
                lock_payload = await redis.get_lock_doc(
                    entity.space_name, 
                    entity.branch_name, 
                    entity.subpath, 
                    entity.shortname
                )
                if lock_payload:
                    if entity.user_shortname:
                        return lock_payload["owner_shortname"] != entity.user_shortname
                    else:
                        return True
                return False

        except Exception as e:
            logger.error(f"Error at RedisDB.is_entry_locked: {e.args}")
            return False
    
    async def delete_lock_doc(self, entity: EntityDTO) -> None:
        try:
            async with RedisServices() as redis:
                return await redis.delete_lock_doc(
                    space_name=entity.space_name,
                    branch_name=entity.branch_name,
                    subpath=entity.subpath,
                    payload_shortname=entity.shortname,
                )

        except Exception as e:
            logger.error(f"Error at RedisDB.delete_lock_doc: {e.args}")
            return None
