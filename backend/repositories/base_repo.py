from abc import ABC, abstractmethod
from datetime import datetime
import json
import os
from pathlib import Path
import random
import string
import subprocess
import sys
from typing import Any
from uuid import uuid4

import aiofiles
from fastapi.encoders import jsonable_encoder

from db.base_db import BaseDB
from models.api import Query, Exception as api_exception, Error as api_error
from models.core import (
    EntityDTO,
    Folder,
    Group,
    Meta,
    Permission,
    Role,
    Space,
    User,
    Record,
)
from models.enums import (
    ContentType,
    Language,
    LockAction,
    ActionType,
    QueryType,
    RequestType,
    ResourceType,
    SortType,
)
from utils.custom_validations import validate_payload_with_schema
from utils.helpers import (
    alter_dict_keys,
    branch_path,
    camel_case,
    flatten_dict,
    flatten_list_of_dicts_in_dict,
    str_to_datetime,
)
from utils.internal_error_code import InternalErrorCode
from utils.settings import settings
from fastapi import status
from utils import regex
import utils.db as main_db
from utils.access_control import access_control
from models.api import Exception as API_Exception, Error as API_Error
from fastapi.logger import logger


class BaseRepo(ABC):
    SYS_ATTRIBUTES: list[str] = [
        "payload_string",
        "branch_name",
        "query_policies",
        "subpath",
        "resource_type",
        "meta_doc_id",
        "payload_doc_id",
        "payload_string",
        "view_acl",
    ]
    SYS_INDEXES: list[dict[str, Any]] = [
        {
            "space": "management",
            "branch": settings.management_space_branch,
            "subpath": "roles",
            "class": Role,
            "exclude_from_index": [
                "relationships",
                "acl",
                "is_active",
                "description",
                "displayname",
                "payload",
            ],
        },
        {
            "space": "management",
            "branch": settings.management_space_branch,
            "subpath": "groups",
            "class": Group,
            "exclude_from_index": [
                "relationships",
                "acl",
                "is_active",
                "description",
                "displayname",
                "payload",
            ],
        },
        {
            "space": "management",
            "branch": settings.management_space_branch,
            "subpath": "users",
            "class": User,
            "exclude_from_index": [
                "relationships",
                "acl",
                "is_active",
                "description",
                "displayname",
                "payload",
                "password",
                "is_email_verified",
                "is_msisdn_verified",
                "type",
                "force_password_change",
                "social_avatar_url",
            ],
        },
        {
            "space": "management",
            "branch": settings.management_space_branch,
            "subpath": "permissions",
            "class": Permission,
            "exclude_from_index": [
                "relationships",
                "acl",
                "is_active",
                "description",
                "displayname",
                "payload",
                "subpaths",
                "resource_types",
                "actions",
                "conditions",
                "restricted_fields",
                "allowed_fields_values",
            ],
        },
    ]

    def __init__(self, db: BaseDB) -> None:
        self.db: BaseDB = db

    # ================================================================================
    # Core CRUD Functions
    # ================================================================================
    @abstractmethod
    async def search(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[dict[str, Any]]]:
        pass

    @abstractmethod
    async def aggregate(
        self, query: Query, user_shortname: str | None = None
    ) -> list[dict[str, Any]]:
        pass

    async def get_count(
        self,
        space_name: str,
        schema_shortname: str,
        branch_name: str = settings.default_branch,
    ) -> int:
        return await self.db.get_count(space_name, schema_shortname, branch_name)

    async def free_search(
        self, index_name: str, search_str: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        return await self.db.free_search(index_name, search_str, limit, offset)

    async def entity_doc_id(self, entity: EntityDTO) -> str:
        return await self.db.entity_doc_id(entity)

    @abstractmethod
    async def find(self, entity: EntityDTO) -> None | Meta:
        pass

    async def find_or_fail(self, entity: EntityDTO) -> Meta:
        item = await self.find(entity)

        if not item:
            raise api_exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api_error(
                    type="delete",
                    code=InternalErrorCode.OBJECT_NOT_FOUND,
                    message="Request object is not available",
                ),
            )

        return item

    async def find_by_id(self, id: str) -> dict[str, Any]:
        return await self.db.find_by_id(id)

    async def list_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        return await self.db.list_by_ids(ids)

    async def find_payload_data_by_id(
        self, id: str, resource_type: ResourceType
    ) -> dict[str, Any]:
        return await self.db.find_payload_data_by_id(id, resource_type)

    async def set_key(self, key: str, value: str, ex=None, nx: bool = False) -> bool:
        return await self.db.set_key(key, value, ex, nx)

    async def delete_keys(self, keys: list[str]) -> bool:
        return await self.db.delete_keys(keys)

    async def find_key(self, key: str) -> str | None:
        return await self.db.find_key(key)

    @abstractmethod
    async def create(
        self, entity: EntityDTO, meta: Meta, payload: dict[str, Any] | None = None
    ) -> None:
        pass

    @abstractmethod
    async def generate_payload_string(
        self,
        entity: EntityDTO,
        payload: dict[str, Any],
    ) -> str:
        pass

    async def save_at_id(self, id: str, doc: dict[str, Any] = {}) -> bool:
        return await self.db.save_at_id(id, doc)

    @abstractmethod
    async def update(
        self, entity: EntityDTO, meta: Meta, payload: dict[str, Any] | None = None
    ) -> None:
        pass

    async def delete(self, entity: EntityDTO) -> bool:
        return await self.db.delete(entity)

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
        return await self.db.move(
            space_name,
            src_subpath,
            src_shortname,
            dest_subpath,
            dest_shortname,
            meta,
            branch_name,
        )

    # @abstractmethod
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
    #     pass

    # ================================== END =========================================

    # ================================================================================
    # Locking Functions
    # ================================================================================
    async def save_lock_doc(
        self, entity: EntityDTO, owner_shortname: str, ttl: int = settings.lock_period
    ) -> LockAction | None:
        return await self.db.save_lock_doc(entity, owner_shortname, ttl)

    async def get_lock_doc(self, entity: EntityDTO) -> dict[str, Any]:
        return await self.db.get_lock_doc(entity)

    async def delete_lock_doc(self, entity: EntityDTO) -> None:
        return await self.db.delete_lock_doc(entity)

    async def is_locked_by_other_user(self, entity: EntityDTO) -> bool:
        return await self.db.is_locked_by_other_user(entity)

    async def validate_and_release_lock(self, entity: EntityDTO) -> bool:
        if await self.is_locked_by_other_user(entity):
            return False

        await self.delete_lock_doc(entity)

        return True

    # ================================== END =========================================

    # ================================================================================
    # Indexing Functions
    # ================================================================================
    async def is_index_exist(self, name: str) -> bool:
        return name in (await self.db.list_indexes())

    async def list_indexes(self):
        return await self.db.list_indexes()

    async def drop_index(self, name: str, delete_docs: bool) -> bool:
        return await self.db.drop_index(name, delete_docs)

    async def create_index(self, name: str, fields: list[Any], **kwargs) -> bool:
        return await self.db.create_index(name, fields, **kwargs)

    async def create_application_indexes(
        self,
        for_space: str | None = None,
        for_schemas: list | None = None,
        for_custom_indices: bool = True,
        del_docs: bool = True,
    ) -> None:
        await self.db.create_application_indexes(
            for_space, for_schemas, for_custom_indices, del_docs
        )

    async def create_index_if_not_exist(
        self, name: str, fields: list[Any], **kwargs
    ) -> bool:
        if await self.is_index_exist(name):
            return True

        return await self.create_index(name, fields, **kwargs)

    async def create_index_drop_existing(
        self, name: str, fields: list[Any], **kwargs
    ) -> bool:
        if await self.is_index_exist(name):
            await self.drop_index(name, kwargs.get("delete_docs", True))

        return await self.create_index(name, fields, **kwargs)

    # ================================== END =========================================

    # ================================================================================
    # Custom Functions
    # ================================================================================
    async def get_payload_doc(
        self, doc_id: str, resource_type: ResourceType
    ) -> dict[str, Any]:
        doc: dict[str, Any] = await self.find_by_id(doc_id)

        resource_class = getattr(
            sys.modules["models.core"],
            camel_case(resource_type),
        )

        not_payload_attr = self.SYS_ATTRIBUTES + list(
            resource_class.model_fields.keys()
        )

        filtered_doc: dict[str, Any] = {}
        for key, value in doc.items():
            if key not in not_payload_attr:
                filtered_doc[key] = value
        return filtered_doc

    @abstractmethod
    async def db_doc_to_record(
        self,
        space_name: str,
        db_entry: dict,
        retrieve_json_payload: bool = False,
        retrieve_attachments: bool = False,
        filter_types: list | None = None,
    ) -> Record:
        pass

    # ================================== END =========================================

    # ================================================================================
    # Query Functions
    # ================================================================================

    async def query_handler(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        # Try to get the query function from the repo
        query_method = getattr(self, f"{query.type}_query", None)
        if not query_method:
            # Try to get the query function from the main db
            query_method = getattr(main_db, f"{query.type}_query", None)

        if not query_method:
            return 0, []

        return await query_method(query, user_shortname) #type: ignore

    async def spaces_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        records: list[Record] = []
        spaces = await self.find_by_id("spaces")
        for space_json in spaces.values():
            space = Space.model_validate_json(space_json)
            records.append(
                space.to_record(
                    query.subpath,
                    space.shortname,
                    query.include_fields if query.include_fields else [],
                    query.branch_name,
                )
            )
        if not query.sort_by:
            query.sort_by = "ordinal"
        if records:
            record_fields = list(records[0].model_fields.keys())
            records = sorted(
                records,
                key=lambda d: (
                    d.__getattribute__(query.sort_by)
                    if query.sort_by in record_fields
                    else (
                        d.attributes[query.sort_by]
                        if query.sort_by in d.attributes
                        and d.attributes[query.sort_by] is not None
                        else 1
                    )
                ),
                reverse=(query.sort_type == SortType.descending),
            )
        return len(records), records

    async def search_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        """Doesn't validate the data according to the schema definition"""
        records: list[Record] = []

        total, search_res = await self.search(query, user_shortname)

        if len(query.filter_schema_names) > 1:
            if query.sort_by:
                search_res = sorted(
                    search_res,
                    key=lambda d: (
                        d[query.sort_by]
                        if query.sort_by in d
                        else (
                            d.get("payload", {})[query.sort_by]
                            if query.sort_by in d.get("payload", {})
                            else ""
                        )
                    ),
                    reverse=(query.sort_type == SortType.descending),
                )
            search_res = search_res[query.offset : (query.limit + query.offset)]

        for redis_doc_dict in search_res:
            resource_record: Record = await self.db_doc_to_record(
                space_name=query.space_name,
                db_entry=redis_doc_dict,
                retrieve_json_payload=query.retrieve_json_payload,
                retrieve_attachments=query.retrieve_attachments,
                filter_types=query.filter_types,
            )
            if query.highlight_fields:
                for key, value in query.highlight_fields.items():
                    resource_record.attributes[value] = getattr(
                        redis_doc_dict, key, None
                    )

            resource_record.attributes = alter_dict_keys(
                jsonable_encoder(resource_record.attributes, exclude_none=True),
                query.include_fields,
                query.exclude_fields,
            )

            records.append(resource_record)

        return total, records

    async def counters_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        if not await access_control.check_access(
            entity=EntityDTO(
                space_name=query.space_name,
                subpath=query.subpath,
                user_shortname=user_shortname,
                resource_type=ResourceType.content,
                shortname="",
            ),
            action_type=ActionType.query,
        ):
            return 0, []

        total: int = 0

        for schema_name in query.filter_schema_names:
            redis_res = await self.get_count(
                space_name=query.space_name,
                branch_name=query.branch_name,
                schema_shortname=schema_name,
            )
            total += int(redis_res)

        return total, []

    @abstractmethod
    async def tags_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        pass

    @abstractmethod
    async def random_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        pass

    async def history_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        records: list[Record] = []
        total: int = 0
        if not await access_control.check_access(
            entity=EntityDTO(
                space_name=query.space_name,
                subpath=query.subpath,
                resource_type=ResourceType.history,
                user_shortname=user_shortname,
                shortname="",
            ),
            action_type=ActionType.query,
        ):
            return total, records

        if not query.filter_shortnames:
            return total, records

        path = Path(
            f"{settings.spaces_folder}/{query.space_name}/{branch_path(query.branch_name)}"
            f"{query.subpath}/.dm/{query.filter_shortnames[0]}/history.jsonl"
        )

        if not path.is_file():
            return total, records

        cmd = f"tail -n +{query.offset} {path} | head -n {query.limit} | tac"
        result = list(
            filter(
                None,
                subprocess.run(
                    [cmd], capture_output=True, text=True, shell=True
                ).stdout.split("\n"),
            )
        )
        total = int(
            subprocess.run(
                [f"wc -l < {path}"],
                capture_output=True,
                text=True,
                shell=True,
            ).stdout,
            10,
        )
        for line in result:
            action_obj = json.loads(line)

            records.append(
                Record(
                    resource_type=ResourceType.history,
                    shortname=query.filter_shortnames[0],
                    subpath=query.subpath,
                    attributes=action_obj,
                    branch_name=query.branch_name,
                ),
            )
        return total, records

    async def events_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        records: list[Record] = []
        total: int = 0

        path = Path(
            f"{settings.spaces_folder}/{query.space_name}/{branch_path(query.branch_name)}/.dm/events.jsonl"
        )
        if not path.is_file():
            return total, records

        result = []
        if query.search:
            p = subprocess.Popen(
                ["grep", f'"{query.search}"', path], stdout=subprocess.PIPE
            )
            p = subprocess.Popen(
                ["tail", "-n", f"{query.limit + query.offset}"],
                stdin=p.stdout,
                stdout=subprocess.PIPE,
            )
            p = subprocess.Popen(["tac"], stdin=p.stdout, stdout=subprocess.PIPE)
            if query.offset > 0:
                p = subprocess.Popen(
                    ["sed", f"1,{query.offset}d"],
                    stdin=p.stdout,
                    stdout=subprocess.PIPE,
                )
            r, _ = p.communicate()
            result = list(filter(None, r.decode("utf-8").split("\n")))
        else:
            cmd = f"(tail -n {query.limit + query.offset} {path}; echo) | tac"
            if query.offset > 0:
                cmd += f" | sed '1,{query.offset}d'"
            result = list(
                filter(
                    None,
                    subprocess.run(
                        [cmd], capture_output=True, text=True, shell=True
                    ).stdout.split("\n"),
                )
            )

        if query.search:
            p1 = subprocess.Popen(
                ["grep", f'"{query.search}"', path], stdout=subprocess.PIPE
            )
            p2 = subprocess.Popen(["wc", "-l"], stdin=p1.stdout, stdout=subprocess.PIPE)
            r, _ = p2.communicate()
            total = int(
                r.decode(),
                10,
            )
        else:
            total = int(
                subprocess.run(
                    [f"wc -l < {path}"],
                    capture_output=True,
                    text=True,
                    shell=True,
                ).stdout,
                10,
            )
        for line in result:
            action_obj = json.loads(line)

            if (
                query.from_date
                and str_to_datetime(action_obj["timestamp"]) < query.from_date
            ):
                continue

            if (
                query.to_date
                and str_to_datetime(action_obj["timestamp"]) > query.to_date
            ):
                break

            if not await access_control.check_access(
                entity=EntityDTO(
                    space_name=query.space_name,
                    subpath=action_obj.get("resource", {}).get("subpath", "/"),
                    resource_type=action_obj["resource"]["type"],
                    shortname=action_obj["resource"]["shortname"],
                    user_shortname=user_shortname,
                ),
                action_type=ActionType(action_obj["request"]),
            ):
                continue

            records.append(
                Record(
                    resource_type=action_obj["resource"]["type"],
                    shortname=action_obj["resource"]["shortname"],
                    subpath=action_obj["resource"]["subpath"],
                    attributes=action_obj,
                ),
            )
        return total, records

    async def aggregation_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        records: list[Record] = []
        rows = await self.aggregate(query=query, user_shortname=user_shortname)
        total: int = len(rows)
        for idx, row in enumerate(rows):
            record = Record(
                resource_type=ResourceType.content,
                shortname=str(idx + 1),
                subpath=query.subpath,
                attributes=row["extra_attributes"],
            )
            records.append(record)
        return total, records

    async def subpath_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        records: list[Record] = []
        total: int = 0

        subpath = query.subpath
        if subpath[0] == "/":
            subpath = "." + subpath
        path = (
            settings.spaces_folder
            / query.space_name
            / branch_path(query.branch_name)
            / subpath
        )

        if query.include_fields is None:
            query.include_fields = []

        # Gel all matching entries
        # entries_glob = ".dm/*/meta.*.json"

        meta_path = path / ".dm"
        if meta_path.is_dir():
            path_iterator = os.scandir(meta_path)
            for entry in path_iterator:
                if not entry.is_dir():
                    continue

                subpath_iterator = os.scandir(entry)
                for one in subpath_iterator:
                    # for one in path.glob(entries_glob):
                    match = regex.FILE_PATTERN.search(str(one.path))
                    if not match or not one.is_file():
                        continue

                    shortname = match.group(1)
                    resource_name = match.group(2).lower()
                    if (
                        query.filter_types
                        and ResourceType(resource_name) not in query.filter_types
                    ):
                        continue

                    if (
                        query.filter_shortnames
                        and shortname not in query.filter_shortnames
                    ):
                        continue

                    resource_class = getattr(
                        sys.modules["models.core"], camel_case(resource_name)
                    )

                    async with aiofiles.open(one, "r") as meta_file:
                        resource_obj = resource_class.model_validate_json(
                            await meta_file.read()
                        )

                    if query.filter_tags and (
                        not resource_obj.tags
                        or not any(
                            item in resource_obj.tags for item in query.filter_tags
                        )
                    ):
                        continue

                    entity = EntityDTO(
                        space_name=query.space_name,
                        subpath=query.subpath,
                        shortname=shortname,
                        resource_type=ResourceType(resource_name),
                        user_shortname=user_shortname,
                        schema_shortname=resource_obj.payload.schema_shortname
                        or None,
                    )
                    # apply check access
                    if not await access_control.check_access(
                        entity=entity,
                        meta=resource_obj,
                        action_type=ActionType.view,
                    ):
                        continue

                    total += 1
                    if len(records) >= query.limit or total < query.offset:
                        continue

                    resource_base_record = resource_obj.to_record(
                        query.subpath,
                        shortname,
                        query.include_fields,
                        query.branch_name,
                    )
                    if resource_base_record:
                        locked_data = await self.get_lock_doc(entity)
                        if locked_data:
                            resource_base_record.attributes["locked"] = locked_data

                    if (
                        query.retrieve_json_payload
                        and resource_obj.payload
                        and resource_obj.payload.content_type
                        and resource_obj.payload.content_type == ContentType.json
                        and (path / resource_obj.payload.body).is_file()
                    ):
                        async with aiofiles.open(
                            path / resource_obj.payload.body, "r"
                        ) as payload_file_content:
                            resource_base_record.attributes["payload"].body = (
                                json.loads(await payload_file_content.read())
                            )

                    if (
                        resource_obj.payload
                        and resource_obj.payload.schema_shortname
                    ):
                        try:
                            payload_body = resource_base_record.attributes[
                                "payload"
                            ].body
                            if not payload_body or isinstance(payload_body, str):
                                async with aiofiles.open(
                                    path / resource_obj.payload.body, "r"
                                ) as payload_file_content:
                                    payload_body = json.loads(
                                        await payload_file_content.read()
                                    )

                            if query.validate_schema:
                                await validate_payload_with_schema(
                                    payload_data=payload_body,
                                    space_name=query.space_name,
                                    branch_name=query.branch_name,
                                    schema_shortname=resource_obj.payload.schema_shortname,
                                )
                        except Exception:
                            continue

                    if query.retrieve_attachments:
                        resource_base_record.attachments = (
                            await main_db.get_entry_attachments(
                                subpath=f"{query.subpath}/{shortname}",
                                branch_name=query.branch_name,
                                attachments_path=(meta_path / shortname),
                                filter_types=query.filter_types,
                                include_fields=query.include_fields,
                                retrieve_json_payload=query.retrieve_json_payload,
                            )
                        )
                    records.append(resource_base_record)

                subpath_iterator.close()
            if path_iterator:
                path_iterator.close()

        # Get all matching sub folders
        # apply check access

        if meta_path.is_dir():
            subfolders_iterator = os.scandir(path)
            for one in subfolders_iterator:
                if not one.is_dir():
                    continue

                subfolder_meta = Path(one.path + "/.dm/meta.folder.json")

                match = regex.FOLDER_PATTERN.search(str(subfolder_meta))

                if not match or not subfolder_meta.is_file():
                    continue

                shortname = match.group(1)
                entity = EntityDTO(
                    space_name=query.space_name,
                    subpath=f"{query.subpath}/{shortname}",
                    resource_type=ResourceType.folder,
                    shortname=shortname,
                    user_shortname=user_shortname,
                )
                if not await access_control.check_access(
                    entity=entity,
                    action_type=ActionType.query,
                ):
                    continue
                if query.filter_shortnames and shortname not in query.filter_shortnames:
                    continue
                total += 1
                if len(records) >= query.limit or total < query.offset:
                    continue

                try:
                    folder_obj = Folder.model_validate_json(subfolder_meta.read_text())
                except Exception as e:
                    logger.error(f"Invalid folder meta file at {one.path}. Error: {e}")
                    continue
                
                folder_record = folder_obj.to_record(
                    query.subpath,
                    shortname,
                    query.include_fields,
                    query.branch_name,
                )
                if (
                    query.retrieve_json_payload
                    and folder_obj.payload
                    and folder_obj.payload.content_type
                    and folder_obj.payload.content_type == ContentType.json
                    and isinstance(folder_obj.payload.body, str)
                    and (path / folder_obj.payload.body).is_file()
                ):
                    async with aiofiles.open(
                        path / folder_obj.payload.body, "r"
                    ) as payload_file_content:
                        folder_record.attributes["payload"].body = json.loads(
                            await payload_file_content.read()
                        )
                        if os.path.exists(meta_path / shortname):
                            folder_record.attachments = await main_db.get_entry_attachments(
                                subpath=f"{query.subpath if query.subpath != '/' else ''}/{shortname}",
                                branch_name=query.branch_name,
                                attachments_path=(meta_path / shortname),
                                filter_types=query.filter_types,
                                include_fields=query.include_fields,
                                retrieve_json_payload=query.retrieve_json_payload,
                            )
                records.append(folder_record)

            if subfolders_iterator:
                subfolders_iterator.close()

        if query.sort_by:
            sort_reverse: bool = (
                query.sort_type is not None
                and query.sort_type == SortType.descending
            )
            if query.sort_by in Record.model_fields:
                records = sorted(
                    records,
                    key=lambda record: record.__getattribute__(str(query.sort_by)),
                    reverse=sort_reverse,
                )
            else:
                records = sorted(
                    records,
                    key=lambda record: record.attributes[str(query.sort_by)],
                    reverse=sort_reverse,
                )
        return total, records

    # ================================== END =========================================

    # ================================================================================
    # Custom Functions
    # ================================================================================
    async def validate_uniqueness(
        self,
        entity: EntityDTO,
        input_data: dict[str, Any],
        action: str = RequestType.create,
    ):
        """
        Get list of unique fields from entry's folder meta data
        ensure that each sub-list in the unique_fields list is unique across all entries
        """
        folder_meta_path = (
            settings.spaces_folder
            / entity.space_name
            / branch_path(entity.branch_name)
            / f"{entity.subpath[1:] if entity.subpath[0] == '/' else entity.subpath}.json"
        )

        if not folder_meta_path.is_file():
            return True

        async with aiofiles.open(folder_meta_path, "r") as file:
            content = await file.read()
        folder_meta = json.loads(content)

        if not isinstance(folder_meta.get("unique_fields", None), list):
            return True

        entry_dict_flattened: dict[Any, Any] = flatten_list_of_dicts_in_dict(
            flatten_dict(input_data)
        )
        redis_escape_chars = str.maketrans(
            {".": r"\.", "@": r"\@", ":": r"\:", "/": r"\/", "-": r"\-", " ": r"\ "}
        )
        redis_replace_chars: dict[int, str] = str.maketrans(
            {".": r".", "@": r".", ":": r"\:", "/": r"\/", "-": r"\-", " ": r"\ "}
        )
        # Go over each composite unique array of fields and make sure there's no entry with those values
        for composite_unique_keys in folder_meta["unique_fields"]:
            redis_search_str = ""
            for unique_key in composite_unique_keys:
                base_unique_key = unique_key
                if unique_key.endswith("_unescaped"):
                    unique_key = unique_key.replace("_unescaped", "")
                if unique_key.endswith("_replace_specials"):
                    unique_key = unique_key.replace("_replace_specials", "")
                if not entry_dict_flattened.get(unique_key, None):
                    continue

                redis_column = unique_key.split("payload.body.")[-1].replace(".", "_")

                # construct redis search string
                if base_unique_key.endswith("_unescaped"):
                    redis_search_str += (
                        " @"
                        + base_unique_key
                        + ":{"
                        + entry_dict_flattened[unique_key]
                        .translate(redis_escape_chars)
                        .replace("\\\\", "\\")
                        + "}"
                    )
                elif base_unique_key.endswith(
                    "_replace_specials"
                ) or unique_key.endswith("email"):
                    redis_search_str += (
                        " @"
                        + redis_column
                        + ":"
                        + entry_dict_flattened[unique_key]
                        .translate(redis_replace_chars)
                        .replace("\\\\", "\\")
                    )

                elif isinstance(entry_dict_flattened[unique_key], list):
                    redis_search_str += (
                        " @"
                        + redis_column
                        + ":{"
                        + "|".join(
                            [
                                item.translate(redis_escape_chars).replace("\\\\", "\\")
                                for item in entry_dict_flattened[unique_key]
                            ]
                        )
                        + "}"
                    )
                elif isinstance(
                    entry_dict_flattened[unique_key], (str, bool)
                ):  # booleans are indexed as TextField
                    redis_search_str += (
                        " @"
                        + redis_column
                        + ":"
                        + entry_dict_flattened[unique_key]
                        .translate(redis_escape_chars)
                        .replace("\\\\", "\\")
                    )

                elif isinstance(entry_dict_flattened[unique_key], int):
                    redis_search_str += (
                        " @"
                        + redis_column
                        + f":[{entry_dict_flattened[unique_key]} {entry_dict_flattened[unique_key]}]"
                    )

                else:
                    continue

            if not redis_search_str:
                continue

            subpath = entity.subpath
            if subpath[0] == "/":
                subpath = subpath[1:]

            # redis_search_str += f" @subpath:{subpath}"

            if action == RequestType.update:
                redis_search_str += f" (-@shortname:{entity.shortname})"

            schema_name = input_data.get("payload", {}).get("schema_shortname", None)

            for index in self.SYS_INDEXES:
                if entity.space_name == index["space"] and index["subpath"] == subpath:
                    schema_name = "meta"
                    break

            if not schema_name:
                continue

            search_res = await self.search(
                Query(
                    type=QueryType.search,
                    space_name=entity.space_name,
                    branch_name=entity.branch_name,
                    search=redis_search_str,
                    subpath=subpath,
                    filter_schema_name=[schema_name],
                    limit=1,
                )
            )

            if search_res and search_res[0] > 0:
                raise API_Exception(
                    status.HTTP_400_BAD_REQUEST,
                    API_Error(
                        type="request",
                        code=InternalErrorCode.DATA_SHOULD_BE_UNIQUE,
                        message=f"Entry should have unique values on the following fields: {', '.join(composite_unique_keys)}",
                    ),
                )

    async def internal_sys_update_model(
        self,
        entity: EntityDTO,
        meta: Meta,
        updates: dict,
        sync_operational_db: bool = True,
        payload_dict: dict = {},
    ) -> None:
        """
        *To be used by the system only, not APIs*
        """

        meta.updated_at = datetime.now()
        meta_updated = False
        payload_updated = False

        if not payload_dict:
            payload_dict = await main_db.load_resource_payload(entity)

        restricted_fields = [
            "uuid",
            "shortname",
            "created_at",
            "updated_at",
            "owner_shortname",
            "payload",
        ]
        for key, value in updates.items():
            if key in restricted_fields:
                continue

            if key in meta.model_fields.keys():
                meta_updated = True
                meta.__setattr__(key, value)
            elif payload_dict:
                payload_dict[key] = value
                payload_updated = True

        if payload_updated and meta.payload and meta.payload.schema_shortname:
            await validate_payload_with_schema(
                payload_dict, entity.space_name, meta.payload.schema_shortname
            )

        if meta_updated:
            await main_db.save(entity, meta, payload_dict)

        if sync_operational_db:
            await self.update(entity, meta, payload_dict)

    async def internal_save_model(
        self, entity: EntityDTO, meta: Meta, payload: dict[str, Any] | None = None
    ):
        """
        *To be used by the system only, not APIs*
        """
        await main_db.save(entity, meta, payload)

        await self.create(entity, meta, payload)

    async def get_entry_by_var(
        self,
        key: str,
        val: str,
        user_shortname: str,
        retrieve_json_payload: bool = False,
        retrieve_attachments: bool = False,
    ):
        spaces = await self.find_by_id("spaces")
        entry_doc = None
        entry_space = None
        entry_branch = None
        for space_name, space in spaces.items():
            space = json.loads(space)
            for branch in space["branches"]:
                search_res: tuple[int, list[dict[str, Any]]] = await self.db.search(
                    space_name=space_name,
                    branch_name=branch,
                    search=f"@{key}:{val}*",
                    limit=1,
                    offset=0,
                    filters={},
                )
                if search_res[0] > 0 and len(search_res[1]) > 0:
                    entry_doc = search_res[1][0]
                    entry_branch = branch
                    break
            if entry_doc:
                entry_space = space_name
                break

        if not entry_doc or not entry_space or not entry_branch:
            return None

        if not await access_control.check_access(
            entity=EntityDTO(
                space_name=entry_space,
                subpath=entry_doc["subpath"],
                resource_type=entry_doc["resource_type"],
                shortname=entry_doc.get("shortname"),
                user_shortname=user_shortname,
            ),
            action_type=ActionType.view,
        ):
            return None

        resource_base_record: Record = await self.db_doc_to_record(
            space_name=entry_space,
            db_entry=entry_doc,
            retrieve_json_payload=retrieve_json_payload,
            retrieve_attachments=retrieve_attachments,
        )

        return resource_base_record

    async def store_user_invitation_token(self, user: User, channel: str) -> str | None:
        """Generate and Store an invitation token

        Returns:
            invitation link or None if the user is not eligible
        """
        invitation_value = None
        if channel == "SMS" and user.msisdn:
            invitation_value = f"{user.shortname}:{channel}:{user.msisdn}"
        elif channel == "EMAIL" and user.email:
            invitation_value = f"{user.shortname}:{channel}:{user.email}"

        if not invitation_value:
            return None

        invitation_token = "".join(
            random.choices(string.ascii_letters + string.digits, k=50)
        )

        await self.set_key(
            f"users:login:invitation:{invitation_token}",
            invitation_value,
            settings.jwt_access_expires,
        )

        return (
            User.invitation_url_template()
            .replace("{url}", settings.invitation_link)
            .replace("{token}", invitation_token)
            .replace("{lang}", Language.code(user.language))
            .replace("{user_type}", user.type)
        )

    async def url_shortener(self, url: str) -> str:
        token_uuid = str(uuid4())[:8]
        await self.set_key(
            f"short/{token_uuid}",
            url,
            ex=60 * 60 * 48,
            nx=False,
        )

        return f"{settings.public_app_url}/managed/s/{token_uuid}"
