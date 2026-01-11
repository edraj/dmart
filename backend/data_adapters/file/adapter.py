import io
import shutil
from copy import copy
from shutil import copy2 as copy_file
from typing import Type, Any, Tuple
import os
import sys
from sys import modules as sys_modules
from fastapi.logger import logger
from redis.commands.search.field import TextField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from datetime import datetime
import aiofiles
from pathlib import Path
from data_adapters.file.adapter_helpers import serve_query_space, serve_query_search, serve_query_subpath, \
    serve_query_counters, serve_query_tags, serve_query_random, serve_query_history, serve_query_events, \
    serve_query_aggregation, get_record_from_redis_doc
from data_adapters.helpers import trans_magic_words
from models.api import Exception as API_Exception, Error as API_Error
import models.core as core
from utils import regex
from data_adapters.file.custom_validations import get_schema_path
from data_adapters.base_data_adapter import BaseDataAdapter, MetaChild
from models.enums import ContentType, ResourceType, LockAction

from utils.helpers import arr_remove_common, read_jsonl_file, snake_case, camel_case, flatten_list_of_dicts_in_dict, \
    flatten_dict, resolve_schema_references
from utils.internal_error_code import InternalErrorCode
from utils.middleware import get_request_data
from data_adapters.file.redis_services import RedisServices
from utils.password_hashing import hash_password
from utils.plugin_manager import plugin_manager
from utils.regex import FILE_PATTERN, FOLDER_PATTERN, SPACES_PATTERN
from utils.settings import settings
from jsonschema import Draft7Validator
from starlette.datastructures import UploadFile
from pathlib import Path as FSPath
import models.api as api
from fastapi import status
import json
import subprocess


def sort_alteration(attachments_dict, attachments_path):
    for attachment_name, attachments in attachments_dict.items():
        try:
            if attachment_name == ResourceType.alteration:
                attachments_dict[attachment_name] = sorted(
                    attachments, key=lambda d: d.attributes["created_at"]
                )
        except Exception as e:
            logger.error(
                f"Invalid attachment entry:{attachments_path / attachment_name}.\
            Error: {e.args}"
            )


def is_file_check(retrieve_json_payload, resource_obj, resource_record_obj, attachment_entry):
    return (
            retrieve_json_payload
            and resource_obj
            and resource_record_obj
            and resource_obj.payload
            and resource_obj.payload.content_type
            and resource_obj.payload.content_type == ContentType.json
            and Path(
        f"{attachment_entry.path}/{resource_obj.payload.body}"
    ).is_file()
    )


def locator_query_path_sub_folder(locators, query, subpath_iterator, total):
    for one in subpath_iterator:
        # for one in path.glob(entries_glob):
        match = FILE_PATTERN.search(str(one.path))
        if not match or not one.is_file():
            continue

        total += 1
        if len(locators) >= query.limit or total < query.offset:
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

        locators.append(
            core.Locator(
                space_name=query.space_name,
                subpath=query.subpath,
                shortname=shortname,
                type=ResourceType(resource_name),
            )
        )
    return locators, total


def locator_query_sub_folder(locators, query, subfolders_iterator, total):
    for one in subfolders_iterator:
        if not one.is_dir():
            continue

        subfolder_meta = Path(one.path + "/.dm/meta.folder.json")

        match = FOLDER_PATTERN.search(str(subfolder_meta))

        if not match or not subfolder_meta.is_file():
            continue

        total += 1
        if len(locators) >= query.limit or total < query.offset:
            continue

        shortname = match.group(1)
        if query.filter_shortnames and shortname not in query.filter_shortnames:
            continue

        locators.append(
            core.Locator(
                space_name=query.space_name,
                subpath=query.subpath,
                shortname=shortname,
                type=core.ResourceType.folder,
            )
        )

    return locators, total




class FileAdapter(BaseDataAdapter):
    async def test_connection(self):
        try:
            async with RedisServices() as redis_services:
                await redis_services.get_doc_by_id("spaces")
        except Exception as e:
            print("[!FATAL]", e)
            sys.exit(127)

    def locators_query(self, query: api.Query) -> tuple[int, list[core.Locator]]:
        locators: list[core.Locator] = []
        total: int = 0
        if query.type != api.QueryType.subpath:
            return total, locators
        path = (
                settings.spaces_folder
                / query.space_name
                / query.subpath
        )

        if query.include_fields is None:
            query.include_fields = []

        # Gel all matching entries
        meta_path = path / ".dm"
        if not meta_path.is_dir():
            return total, locators

        path_iterator = os.scandir(meta_path)
        for entry in path_iterator:
            if not entry.is_dir():
                continue

            subpath_iterator = os.scandir(entry)
            locators, total = locator_query_path_sub_folder(locators, query, subpath_iterator, total)

        # Get all matching sub folders
        subfolders_iterator = os.scandir(path)
        locators, total = locator_query_sub_folder(locators, query, subfolders_iterator, total)

        return total, locators

    def folder_path(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
    ):
        return f"{settings.spaces_folder}/{space_name}/{subpath}/{shortname}"

    async def otp_created_since(self, key: str) -> int | None:
        async with RedisServices() as redis_services:
            ttl = await redis_services.ttl(key)
            print(ttl)
            if not isinstance(ttl, int):
                return None
            return settings.otp_token_ttl - ttl
        
    async def save_otp(
        self,
        key: str,
        otp: str,
    ):
        async with RedisServices() as redis_services:
            await redis_services.set(key, otp, settings.otp_token_ttl)

    async def get_otp(
            self,
            key: str,
    ):
        async with RedisServices() as redis_services:
            return await redis_services.get_content_by_id(key)

    async def delete_otp(self, key: str):
        async with RedisServices() as redis_services:
            await redis_services.del_keys([key])

    def metapath(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[MetaChild],
            schema_shortname: str | None = None,
    ) -> tuple[Path, str]:
        """Construct the full path of the meta file"""
        path = settings.spaces_folder / space_name

        filename = ""
        if subpath[0] == "/":
            subpath = f".{subpath}"
        if issubclass(class_type, core.Folder):
            path = path / subpath / shortname / ".dm"
            filename = f"meta.{class_type.__name__.lower()}.json"
        elif issubclass(class_type, core.Space):
            path = settings.spaces_folder / space_name / ".dm"
            filename = "meta.space.json"
        elif issubclass(class_type, core.Attachment):
            [parent_subpath, parent_name] = subpath.rsplit("/", 1)
            # schema_shortname = "." + schema_shortname if schema_shortname else ""
            attachment_folder = (
                f"{parent_name}/attachments.{class_type.__name__.lower()}"
            )
            path = path / parent_subpath / ".dm" / attachment_folder
            filename = f"meta.{shortname}.json"
        elif issubclass(class_type, core.History):
            [parent_subpath, parent_name] = subpath.rsplit("/", 1)
            path = path / parent_subpath / ".dm" / f"{parent_name}/history"
            filename = f"{shortname}.json"
        else:
            path = path / subpath / ".dm" / shortname
            filename = f"meta.{snake_case(class_type.__name__)}.json"
        return path, filename

    def payload_path(
            self,
            space_name: str,
            subpath: str,
            class_type: Type[MetaChild],
            schema_shortname: str | None = None,
    ) -> Path:
        """Construct the full path of the meta file"""
        path = settings.spaces_folder / space_name

        if subpath[0] == "/":
            subpath = f".{subpath}"
        if issubclass(class_type, core.Attachment):
            [parent_subpath, parent_name] = subpath.rsplit("/", 1)
            schema_shortname = "." + schema_shortname if schema_shortname else ""
            attachment_folder = (
                f"{parent_name}/attachments{schema_shortname}.{class_type.__name__.lower()}"
            )
            path = path / parent_subpath / ".dm" / attachment_folder
        else:
            path = path / subpath
        return path

    async def load_or_none(self,
                           space_name: str,
                           subpath: str,
                           shortname: str,
                           class_type: Type[MetaChild],
                           user_shortname: str | None = None,
                           schema_shortname: str | None = None
                           ) -> MetaChild | None:  # type: ignore
        """Load a Meta Json according to the reuqested Class type"""
        try:
            return await self.load(space_name, subpath, shortname, class_type, user_shortname, schema_shortname)
        except Exception as _:
            return None

    async def query(self, query: api.Query, user_shortname: str | None = None) \
            -> Tuple[int, list[core.Record]]:
        records: list[core.Record] = []
        total: int = 0

        match query.type:
            case api.QueryType.spaces:
                total, records = await serve_query_space(self, query, user_shortname)

            case api.QueryType.search:
                total, records = await serve_query_search(self, query, user_shortname)

            case api.QueryType.subpath:
                total, records = await serve_query_subpath(self, query, user_shortname)

            case api.QueryType.counters:
                total, records = await serve_query_counters(query, user_shortname)

            case api.QueryType.tags:
                total, records = await serve_query_tags(self, query, user_shortname)

            case api.QueryType.random:
                total, records = await serve_query_random(self, query, user_shortname)

            case api.QueryType.history:
                total, records = await serve_query_history(query, user_shortname)

            case api.QueryType.events:
                total, records = await serve_query_events(query, user_shortname)

            case api.QueryType.aggregation:
                total, records = await serve_query_aggregation(self, query, user_shortname)

        if getattr(query, 'join', None):
            try:
                records = await self._apply_client_joins(records, query.join, (user_shortname or "anonymous")) # type: ignore
            except Exception as e:
                print("[!client_join(file)]", e)

        return total, records

    async def _apply_client_joins(self, base_records: list[core.Record], joins: list, user_shortname: str) -> list[core.Record]:
        def parse_join_on(expr: str) -> tuple[str, bool, str, bool]:
            parts = [p.strip() for p in expr.split(':', 1)]
            if len(parts) != 2:
                raise ValueError(f"Invalid join_on expression: {expr}")
            left, right = parts[0], parts[1]
            _l_arr = left.endswith('[]')
            _r_arr = right.endswith('[]')
            if _l_arr:
                left = left[:-2]
            if _r_arr:
                right = right[:-2]
            return left, _l_arr, right, _r_arr

        def get_values_from_record(rec: core.Record, path: str, array_hint: bool) -> list:
            if path in ("shortname", "resource_type", "subpath", "uuid"):
                val = getattr(rec, path, None)
            elif path == "space_name":
                val = rec.attributes.get("space_name") if rec.attributes else None
            else:
                container = rec.attributes or {}
                # lazy import to reuse same helper as SQL
                from data_adapters.helpers import get_nested_value as _get
                val = _get(container, path)

            if val is None:
                return []
            if isinstance(val, list):
                out = []
                for item in val:
                    if isinstance(item, (str, int, float, bool)) or item is None:
                        out.append(item)
                return out
            if array_hint:
                return [val]
            return [val]

        for rec in base_records:
            if rec.attributes is None:
                rec.attributes = {}
            if rec.attributes.get('join') is None:
                rec.attributes['join'] = {}

        import models.api as api
        for join_item in joins:
            join_on = getattr(join_item, 'join_on', None)
            alias = getattr(join_item, 'alias', None)
            q = getattr(join_item, 'query', None)
            if not join_on or not alias or q is None:
                continue

            sub_query = q if isinstance(q, api.Query) else api.Query.model_validate(q)
            import models.api as api
            from utils.settings import settings
            q_raw = q if isinstance(q, dict) else q.model_dump(exclude_defaults=True)
            user_limit = q_raw.get('limit') or q_raw.get('limit_')
            sub_query.limit = settings.max_query_limit

            _total, right_records = await self.query(sub_query, user_shortname)

            l_path, l_arr, r_path, r_arr = parse_join_on(join_on)

            right_index: dict[str, list[core.Record]] = {}
            for rr in right_records:
                r_vals = get_values_from_record(rr, r_path, r_arr)
                for v in r_vals:
                    if v is None:
                        continue
                    right_index.setdefault(str(v), []).append(rr)

            for br in base_records:
                l_vals = get_values_from_record(br, l_path, l_arr)
                matched: list[core.Record] = []
                for v in l_vals:
                    if v is None:
                        continue
                    matched.extend(right_index.get(str(v), []))

                seen = set()
                unique: list[core.Record] = []
                for m in matched:
                    uid = f"{m.subpath}:{m.shortname}:{m.resource_type}"
                    if uid in seen:
                        continue
                    seen.add(uid)
                    unique.append(m)

                if user_limit:
                    unique = unique[:user_limit]

                br.attributes['join'][alias] = unique

        return base_records

    async def load(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[MetaChild],
            user_shortname: str | None = None,
            schema_shortname: str | None = None,
    ) -> MetaChild:
        """Load a Meta Json according to the requested Class type"""
        if subpath == shortname and class_type is core.Folder:
            shortname = ""
        path, filename = self.metapath(
            space_name, subpath, shortname, class_type, schema_shortname
        )
        if not (path / filename).is_file():
            # Remove the folder
            if path.is_dir() and len(os.listdir(path)) == 0:
                shutil.rmtree(path)

            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(
                    type="db",
                    code=InternalErrorCode.OBJECT_NOT_FOUND,
                    message=f"Request object is not available @{space_name}/{subpath}/{shortname} {class_type=} {schema_shortname=}",
                ),
            )

        path /= filename
        content = ""
        try:
            async with aiofiles.open(path, "r") as file:
                content = await file.read()
                return class_type.model_validate_json(content)
        except Exception as e:
            raise Exception(f"Error Invalid Entry At: {path}. Error {e} {content=}")

    async def load_resource_payload(
            self,
            space_name: str,
            subpath: str,
            filename: str,
            class_type: Type[MetaChild],
            schema_shortname: str | None = None,
    ):
        """Load a Meta class payload file"""

        path = self.payload_path(space_name, subpath, class_type, schema_shortname)
        path /= filename

        if not path.is_file():
            return None
        try:
            if class_type == core.Log:
                return {"log_entry_items": read_jsonl_file(path)}

            bytes = path.read_bytes()
            return json.loads(bytes)
        except Exception as _:
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(type="db", code=12, message=f"Request object is not available {path}"),
            )

    async def save(self, space_name: str, subpath: str, meta: core.Meta) -> Any:
        """Save Meta Json to respective file"""
        try:
            path, filename = self.metapath(
                space_name,
                subpath,
                meta.shortname,
                meta.__class__,
                meta.payload.schema_shortname if meta.payload else None,
            )

            if not path.is_dir():
                os.makedirs(path)

            meta_json = meta.model_dump_json(exclude_none=True, warnings="error")
            with open(path / filename, "w") as file:
                file.write(meta_json)
                file.flush()
                os.fsync(file)
            return meta_json
        except Exception as e:
            raise API_Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=API_Error(
                    type="create",
                    code=InternalErrorCode.OBJECT_NOT_SAVED,
                    message=e.__str__(),
                ),
            )

    async def create(self, space_name: str, subpath: str, meta: core.Meta):
        path, filename = self.metapath(
            space_name, subpath, meta.shortname, meta.__class__
        )

        if (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create", code=InternalErrorCode.SHORTNAME_ALREADY_EXIST, message="already exists"),
            )

        if not path.is_dir():
            os.makedirs(path)

        with open(path / filename, "w") as file:
            file.write(meta.model_dump_json(exclude_none=True, warnings="error"))
            file.flush()
            os.fsync(file)

    async def save_payload(self, space_name: str, subpath: str, meta: core.Meta, attachment):
        path, filename = self.metapath(
            space_name, subpath, meta.shortname, meta.__class__
        )
        payload_file_path = self.payload_path(
            space_name, subpath, meta.__class__)
        payload_filename = meta.shortname + Path(attachment.filename).suffix

        if not (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create", code=InternalErrorCode.MISSING_METADATA, message="metadata is missing"),
            )

        content = await attachment.read()
        with open(payload_file_path / payload_filename, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file)

    async def save_payload_from_json(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload_data: dict[str, Any],
    ):
        path, filename = self.metapath(
            space_name,
            subpath,
            meta.shortname,
            meta.__class__,
            meta.payload.schema_shortname if meta.payload else None,
        )
        payload_file_path = self.payload_path(
            space_name,
            subpath,
            meta.__class__,
            meta.payload.schema_shortname if meta.payload else None,
        )

        payload_filename = f"{meta.shortname}.json" if not issubclass(meta.__class__,
                                                                      core.Log) else f"{meta.shortname}.jsonl"

        if not (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create", code=InternalErrorCode.MISSING_METADATA, message="metadata is missing"),
            )

        payload_json = json.dumps(payload_data)
        if issubclass(meta.__class__, core.Log) and (payload_file_path / payload_filename).is_file():
            with open(payload_file_path / payload_filename, "a") as file:
                file.write(f"\n{payload_json}")
                file.flush()
                os.fsync(file)
        else:
            with open(payload_file_path / payload_filename, "w") as file:
                file.write(payload_json)
                file.flush()
                os.fsync(file)

    async def update(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            old_version_flattend: dict,
            new_version_flattend: dict,
            updated_attributes_flattend: list,
            user_shortname: str,
            schema_shortname: str | None = None,
            retrieve_lock_status: bool | None = False,
    ) -> dict:
        """Update the entry, store the difference and return it"""
        path, filename = self.metapath(
            space_name,
            subpath,
            meta.shortname,
            meta.__class__,

            schema_shortname,
        )
        if not (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(type="update", code=InternalErrorCode.OBJECT_NOT_FOUND,
                                message="Request object is not available"),
            )
        if retrieve_lock_status:
            async with RedisServices() as redis_services:
                if await redis_services.is_entry_locked(
                        space_name, subpath, meta.shortname, user_shortname
                ):
                    raise api.Exception(
                        status_code=status.HTTP_403_FORBIDDEN,
                        error=api.Error(
                            type="update", code=InternalErrorCode.LOCKED_ENTRY, message="This entry is locked"),
                    )
                elif await redis_services.get_lock_doc(
                        space_name, subpath, meta.shortname
                ):
                    # if the current can release the lock that means he is the right user
                    await redis_services.delete_lock_doc(
                        space_name, subpath, meta.shortname
                    )
                    await self.store_entry_diff(
                        space_name,
                        "/" + subpath,
                        meta.shortname,
                        user_shortname,
                        {},
                        {"lock_type": LockAction.unlock},
                        ["lock_type"],
                        core.Content,
                    )

        meta.updated_at = datetime.now()
        meta_json = meta.model_dump_json(exclude_none=True, warnings="error")
        with open(path / filename, "w") as file:
            file.write(meta_json)
            file.flush()
            os.fsync(file)

        if issubclass(meta.__class__, core.Log):
            return {}

        history_diff = await self.store_entry_diff(
            space_name,
            subpath,
            meta.shortname,
            user_shortname,
            old_version_flattend,
            new_version_flattend,
            updated_attributes_flattend,
            meta.__class__,
        )

        return history_diff

    async def update_payload(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload_data: dict[str, Any],
            owner_shortname: str,
    ):
        await self.save_payload_from_json(
            space_name,
            subpath,
            meta,
            payload_data,
        )

    async def store_entry_diff(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            owner_shortname: str,
            old_version_flattend: dict,
            new_version_flattend: dict,
            updated_attributes_flattend: list,
            resource_type,
    ) -> dict:
        diff_keys = list(old_version_flattend.keys())
        diff_keys.extend(list(new_version_flattend.keys()))
        history_diff = {}
        for key in set(diff_keys):
            if key in ["updated_at"]:
                continue
            if key in updated_attributes_flattend:
                old = (
                    copy(old_version_flattend[key])
                    if key in old_version_flattend
                    else "null"
                )
                new = (
                    copy(new_version_flattend[key])
                    if key in new_version_flattend
                    else "null"
                )

                if old != new:
                    if isinstance(old, list) and isinstance(new, list):
                        old, new = arr_remove_common(old, new)
                    history_diff[key] = {
                        "old": old,
                        "new": new,
                    }
        if not history_diff:
            return {}

        history_obj = core.History(
            shortname="history",
            owner_shortname=owner_shortname,
            timestamp=datetime.now(),
            request_headers=get_request_data().get('request_headers', {}),
            diff=history_diff,
        )
        history_path = settings.spaces_folder / space_name

        if subpath == "/" and resource_type == core.Space:
            history_path = Path(f"{history_path}/.dm")
        else:
            if issubclass(resource_type, core.Attachment):
                history_path = Path(f"{history_path}/.dm/{subpath}")
            else:
                if subpath == "/":
                    history_path = Path(f"{history_path}/.dm/{shortname}")
                else:
                    history_path = Path(
                        f"{history_path}/{subpath}/.dm/{shortname}")

        if not os.path.exists(history_path):
            os.makedirs(history_path)

        async with aiofiles.open(
                f"{history_path}/history.jsonl",
                "a",
        ) as events_file:
            await events_file.write(f"{history_obj.model_dump_json(exclude_none=True, warnings='error')}\n")

        return history_diff

    async def move(
            self,
            src_space_name: str,
            src_subpath: str,
            src_shortname: str,
            dest_space_name: str,
            dest_subpath: str,
            dest_shortname: str,
            meta: core.Meta,
    ):
        src_path, src_filename = self.metapath(
            src_space_name,
            src_subpath,
            src_shortname,
            meta.__class__,
        )
        dest_path, dest_filename = self.metapath(
            dest_space_name,
            dest_subpath or src_subpath,
            dest_shortname or src_shortname,
            meta.__class__,

        )

        meta_updated = False
        dest_path_without_dm = dest_path
        if dest_shortname:
            meta.shortname = dest_shortname
            meta_updated = True

        if src_path.parts[-1] == ".dm":
            src_path = Path("/".join(src_path.parts[:-1]))

        if dest_path.parts[-1] == ".dm":
            dest_path_without_dm = Path("/".join(dest_path.parts[:-1]))

        if dest_path_without_dm.is_dir() and len(os.listdir(dest_path_without_dm)):
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(
                    type="move",
                    code=InternalErrorCode.NOT_ALLOWED_LOCATION,
                    message="The destination folder is not empty",
                ),
            )

        # Create dest dir if there's a change in the subpath AND the shortname
        # and the subpath shortname folder doesn't exist,
        if (
                src_shortname != dest_shortname
                and src_subpath != dest_subpath
                and not os.path.isdir(dest_path_without_dm)
        ):
            os.makedirs(dest_path_without_dm)

        os.rename(src=src_path, dst=dest_path_without_dm)

        # Move payload file with the meta file
        if (
                meta.payload
                and meta.payload.content_type != ContentType.text
                and isinstance(meta.payload.body, str)
        ):
            src_payload_file_path = (
                    self.payload_path(src_space_name, src_subpath, meta.__class__)
                    / meta.payload.body
            )
            file_extension = Path(meta.payload.body).suffix
            if file_extension.startswith('.'):
                file_extension = file_extension[1:]
            meta.payload.body = meta.shortname + "." + file_extension
            dist_payload_file_path = (
                    self.payload_path(
                        dest_space_name, dest_subpath or src_subpath, meta.__class__
                    )
                    / meta.payload.body
            )
            if src_payload_file_path.is_file():
                os.rename(src=src_payload_file_path, dst=dist_payload_file_path)

        if meta_updated:
            meta_json = meta.model_dump_json(exclude_none=True, warnings="error")
            with open(dest_path / dest_filename, "w") as opened_file:
                opened_file.write(meta_json)
                opened_file.flush()
                os.fsync(opened_file)

        # Delete Src path if empty
        if src_path.parent.is_dir():
            self.delete_empty(src_path)

    def delete_empty(self, path: Path):
        if path.is_dir() and len(os.listdir(path)) == 0:
            os.removedirs(path)

        if path.parent.is_dir() and len(os.listdir(path.parent)) == 0:
            self.delete_empty(path.parent)

    async def clone(
            self,
            src_space: str,
            dest_space: str,
            src_subpath: str,
            src_shortname: str,
            dest_subpath: str,
            dest_shortname: str,
            class_type: Type[MetaChild],
    ):

        meta_obj = await self.load(
            space_name=src_space,
            subpath=src_subpath,
            shortname=src_shortname,
            class_type=class_type,
        )

        src_path, src_filename = self.metapath(
            src_space, src_subpath, src_shortname, class_type
        )
        dest_path, dest_filename = self.metapath(
            dest_space,
            dest_subpath,
            dest_shortname,
            class_type,

        )

        # Create dest dir if not exist
        if not os.path.isdir(dest_path):
            os.makedirs(dest_path)

        copy_file(src=src_path / src_filename, dst=dest_path / dest_filename)

        self.payload_path(src_space, src_subpath, class_type)
        # Move payload file with the meta file
        if (
                meta_obj.payload
                and meta_obj.payload.content_type != ContentType.text
                and isinstance(meta_obj.payload.body, str)
        ):
            src_payload_file_path = (
                    self.payload_path(src_space, src_subpath, class_type)
                    / meta_obj.payload.body
            )
            dist_payload_file_path = (
                    self.payload_path(
                        dest_space, dest_subpath, class_type
                    )
                    / meta_obj.payload.body
            )
            copy_file(src=src_payload_file_path, dst=dist_payload_file_path)

    async def is_entry_exist(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            resource_type: ResourceType,
            schema_shortname: str | None = None,
    ) -> bool:
        """Check if an entry with the given name already exist or not in the given path

        Args:
            space_name (str): The target space name
            subpath (str): The target subpath
            shortname (str): the target shortname
            class_type (MetaChild): The target class of the entry
            schema_shortname (str | None, optional): schema shortname of the entry. Defaults to None.

        Returns:
            bool: True if it's already exist, False otherwise
        """
        if subpath[0] == "/":
            subpath = f".{subpath}"

        payload_file = settings.spaces_folder / space_name / \
                       subpath / f"{shortname}.json"
        if payload_file.is_file():
            return True

        for r_type in ResourceType:
            # Spaces compared with each others only
            if r_type == ResourceType.space and r_type != resource_type:
                continue
            resource_cls = getattr(
                sys.modules["models.core"], camel_case(r_type.value), None
            )
            if not resource_cls:
                continue
            meta_path, meta_file = self.metapath(
                space_name, subpath, shortname, resource_cls, schema_shortname)
            if (meta_path / meta_file).is_file():
                return True

        return False

    async def delete(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            user_shortname: str,
            schema_shortname: str | None = None,
            retrieve_lock_status: bool | None = False,
    ):

        path, filename = self.metapath(
            space_name,
            subpath,
            meta.shortname,
            meta.__class__,

            schema_shortname,
        )
        if not path.is_dir() or not (path / filename).is_file():
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(
                    type="delete", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"),
            )
        if retrieve_lock_status:
            async with RedisServices() as redis_services:
                if await redis_services.is_entry_locked(
                        space_name, subpath, meta.shortname, user_shortname
                ):
                    raise api.Exception(
                        status_code=status.HTTP_403_FORBIDDEN,
                        error=api.Error(
                            type="delete", code=InternalErrorCode.LOCKED_ENTRY, message="This entry is locked"),
                    )
                else:
                    # if the current can release the lock that means he is the right user
                    await redis_services.delete_lock_doc(
                        space_name, subpath, meta.shortname
                    )

        pathname = path / filename
        if pathname.is_file():
            os.remove(pathname)

            # Delete payload file
            if meta.payload and meta.payload.content_type not in ContentType.inline_types():
                payload_file_path = self.payload_path(
                    space_name, subpath, meta.__class__
                ) / str(meta.payload.body)
                if payload_file_path.exists() and payload_file_path.is_file():
                    os.remove(payload_file_path)

        history_path = f"{settings.spaces_folder}/{space_name}" + \
                       f"{subpath}/.dm/{meta.shortname}"

        if (
                path.is_dir()
                and (
                not isinstance(meta, core.Attachment)
                or len(os.listdir(path)) == 0
        )
        ):
            shutil.rmtree(path)
            # in case of folder the path = {folder_name}/.dm
            if isinstance(meta, core.Folder) and path.parent.is_dir():
                shutil.rmtree(path.parent)
            if isinstance(meta, core.Folder) and Path(history_path).is_dir():
                shutil.rmtree(history_path)

    async def lock_handler(self, space_name: str, subpath: str, shortname: str, user_shortname: str,
                           action: LockAction) -> dict | None:
        match action:
            case LockAction.lock:
                async with RedisServices() as redis_services:
                    lock_type = await redis_services.save_lock_doc(
                        space_name,
                        subpath,
                        shortname,
                        user_shortname,
                        settings.lock_period,
                    )
                    return {lock_type: lock_type}
            case LockAction.fetch:
                async with RedisServices() as redis_services:
                    lock_payload = await redis_services.get_lock_doc(
                        space_name, subpath, shortname
                    )
                    return dict(lock_payload)
            case LockAction.unlock:
                async with RedisServices() as redis_services:
                    await redis_services.delete_lock_doc(
                        space_name, subpath, shortname
                    )
        return None

    async def fetch_space(self, space_name: str) -> core.Space | None:
        spaces = await self.get_spaces()
        if space_name not in spaces:
            return None
        return core.Space.model_validate_json(spaces[space_name])

    async def get_entry_attachments(
            self,
            subpath: str,
            attachments_path: Path,
            filter_types: list | None = None,
            include_fields: list | None = None,
            filter_shortnames: list | None = None,
            retrieve_json_payload: bool = False,
    ) -> dict:
        if not attachments_path.is_dir():
            return {}
        try:
            attachments_iterator = os.scandir(attachments_path)
            attachments_dict: dict[ResourceType, list] = {}
            for attachment_entry in attachments_iterator:
                # TODO: Filter types on the parent attachment type folder layer
                if not attachment_entry.is_dir():
                    continue

                attachments_files = os.scandir(attachment_entry)
                for attachments_file in attachments_files:
                    match = regex.ATTACHMENT_PATTERN.search(str(attachments_file.path))
                    if not match or not attachments_file.is_file():
                        continue

                    attach_shortname = match.group(2)
                    attach_resource_name = match.group(1).lower()
                    if filter_shortnames and attach_shortname not in filter_shortnames:
                        continue

                    if filter_types and ResourceType(attach_resource_name) not in filter_types:
                        continue

                    resource_class = getattr(
                        sys.modules["models.core"], camel_case(attach_resource_name)
                    )
                    resource_obj = None
                    async with aiofiles.open(attachments_file, "r") as meta_file:
                        try:
                            resource_obj = resource_class.model_validate_json(await meta_file.read())
                        except Exception as e:
                            raise Exception(
                                f"Bad attachment ... {attachments_file=}"
                            ) from e

                    resource_record_obj = resource_obj.to_record(
                        subpath, attach_shortname, include_fields
                    )
                    if is_file_check(retrieve_json_payload, resource_obj, resource_record_obj, attachment_entry):
                        async with aiofiles.open(
                                f"{attachment_entry.path}/{resource_obj.payload.body}", "r"
                        ) as payload_file_content:
                            resource_record_obj.attributes["payload"].body = json.loads(
                                await payload_file_content.read()
                            )

                    if attach_resource_name in attachments_dict:
                        attachments_dict[ResourceType(attach_resource_name)].append(
                            resource_record_obj)
                    else:
                        attachments_dict[ResourceType(attach_resource_name)] = [resource_record_obj]
                attachments_files.close()
            attachments_iterator.close()

            # SORT ALTERATION ATTACHMENTS BY ALTERATION.CREATED_AT
            sort_alteration(attachments_dict, attachments_path)

            return attachments_dict
        except Exception as e:
            print(e)
            return {}

    async def get_spaces(self) -> dict:
        async with RedisServices() as redis_services:
            value = await redis_services.get_doc_by_id("spaces")
            if isinstance(value, dict):
                return value
            return {}

    async def validate_uniqueness(
            self, space_name: str, record: core.Record, action: str = api.RequestType.create, user_shortname=None
    ) -> bool:
        """
        Get list of unique fields from entry's folder meta data
        ensure that each sub-list in the list is unique across all entries
        """
        folder_meta_path = (
                settings.spaces_folder
                / space_name
                / f"{record.subpath[1:] if record.subpath[0] == '/' else record.subpath}.json"
        )

        if not folder_meta_path.is_file():
            return True

        async with aiofiles.open(folder_meta_path, "r") as file:
            content = await file.read()
        folder_meta = json.loads(content)

        if not isinstance(folder_meta.get("unique_fields", None), list):
            return True

        entry_dict_flattened: dict[Any, Any] = flatten_list_of_dicts_in_dict(
            flatten_dict(record.attributes)
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
                if (
                        base_unique_key.endswith("_unescaped")
                ):
                    redis_search_str += (
                            " @"
                            + base_unique_key
                            + ":{"
                            + entry_dict_flattened[unique_key]
                            .translate(redis_escape_chars)
                            .replace("\\\\", "\\")
                            + "}"
                    )
                elif (
                        base_unique_key.endswith("_replace_specials") or unique_key.endswith('email')
                ):
                    redis_search_str += (
                            " @"
                            + redis_column
                            + ":"
                            + entry_dict_flattened[unique_key]
                            .translate(redis_replace_chars)
                            .replace("\\\\", "\\")
                    )

                elif (
                        isinstance(entry_dict_flattened[unique_key], list)
                ):
                    redis_search_str += (
                            " @"
                            + redis_column
                            + ":{"
                            + "|".join([
                        item.translate(redis_escape_chars).replace("\\\\", "\\") for item in
                        entry_dict_flattened[unique_key]
                    ])
                            + "}"
                    )
                elif isinstance(entry_dict_flattened[unique_key], (str, bool)):  # booleans are indexed as TextField
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

            subpath = record.subpath
            if subpath[0] == "/":
                subpath = subpath[1:]

            redis_search_str += f" @subpath:{subpath}"

            if action == api.RequestType.update:
                redis_search_str += f" (-@shortname:{record.shortname})"

            schema_name = record.attributes.get("payload", {}).get("schema_shortname", None)

            for index in RedisServices.CUSTOM_INDICES:
                if space_name == index["space"] and index["subpath"] == subpath:
                    schema_name = "meta"
                    break

            if not schema_name:
                continue

            async with RedisServices() as redis_services:
                redis_search_res = await redis_services.search(
                    space_name=space_name,
                    search=redis_search_str,
                    limit=1,
                    offset=0,
                    filters={},
                    schema_name=schema_name,
                )

            if redis_search_res and redis_search_res["total"] > 0:
                raise API_Exception(
                    status.HTTP_400_BAD_REQUEST,
                    API_Error(
                        type="request",
                        code=InternalErrorCode.DATA_SHOULD_BE_UNIQUE,
                        message=f"Entry should have unique values on the following fields: {', '.join(composite_unique_keys)}",
                    ),
                )
        return True

    async def validate_payload_with_schema(
            self,
            payload_data: UploadFile | dict,
            space_name: str,
            schema_shortname: str,
    ):
        if not isinstance(payload_data, (dict, UploadFile)):
            raise API_Exception(
                status.HTTP_400_BAD_REQUEST,
                API_Error(
                    type="request",
                    code=InternalErrorCode.INVALID_DATA,
                    message="Invalid payload.body",
                ),
            )

        schema_path = get_schema_path(
            space_name=space_name,
            schema_shortname=f"{schema_shortname}.json",
        )

        schema = json.loads(FSPath(schema_path).read_text())

        if not isinstance(payload_data, dict):
            data = json.load(payload_data.file)
            payload_data.file.seek(0)
        else:
            data = payload_data

        Draft7Validator(schema).validate(data)  # type: ignore

    async def get_failed_password_attempt_count(self, user_shortname: str) -> int:
        async with RedisServices() as redis_services:
            failed_login_attempts_count = 0
            raw_failed_login_attempts_count = await redis_services.get(f"users:failed_login_attempts/{user_shortname}")
            if raw_failed_login_attempts_count:
                failed_login_attempts_count = int(raw_failed_login_attempts_count)
            return failed_login_attempts_count

    async def clear_failed_password_attempts(self, user_shortname: str):
        async with RedisServices() as redis_services:
            return await redis_services.del_keys([f"users:failed_login_attempts/{user_shortname}"])

    async def set_failed_password_attempt_count(self, user_shortname: str, attempt_count: int):
        async with RedisServices() as redis_services:
            return await redis_services.set(f"users:failed_login_attempts/{user_shortname}", attempt_count)

    async def get_invitation(self, invitation_token: str):
        async with RedisServices() as redis_services:
            # FIXME invitation_token = await redis_services.getdel_key(
            token = await redis_services.get_key(
                f"users:login:invitation:{invitation_token}"
            )

        if not token:
            raise Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(
                    type="jwtauth", code=InternalErrorCode.INVALID_INVITATION, message="Invalid invitation"),
            )

        return token

    async def delete_invitation(self, invitation_token: str) -> bool:
        async with RedisServices() as redis_services:
            try:
                await redis_services.delete(f"users:login:invitation:{invitation_token}")
                return True
            except Exception as e:
                logger.error(f"Error deleting invitation token {e}")
                return False

    async def get_url_shortner(self, token_uuid: str) -> str | None:
        async with RedisServices() as redis_services:
            return await redis_services.get_key(f"short/{token_uuid}")

    async def get_latest_history(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
    ) -> Any | None:
        history_path = settings.spaces_folder / space_name

        if subpath == "/" or subpath == "":
             path1 = history_path / ".dm" / "history.jsonl"
             path2 = history_path / ".dm" / shortname / "history.jsonl"
             
             if path2.is_file():
                 path = path2
             elif path1.is_file():
                 path = path1
             else:
                 return None
        else:
            path1 = history_path / subpath / ".dm" / shortname / "history.jsonl"
            path2 = history_path / ".dm" / subpath / "history.jsonl"
            
            if path1.is_file():
                path = path1
            elif path2.is_file():
                path = path2
            else:
                return None

        try:
            r1 = subprocess.Popen(
                ["tail", "-n", "1", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            r2, _ = r1.communicate()
            if r2:
                return json.loads(r2.decode().strip())
        except Exception:
            pass
        return None

    async def get_entry_by_criteria(self, criteria: dict, table: Any = None) -> core.Record | None:
        async with RedisServices() as redis_services:
            _search_query = ""
            for k, v in criteria.items():
                _search_query += f"@{k}:({v.replace('@', '?')}) "
            r_search = await redis_services.search(
                space_name=settings.management_space,
                search=_search_query,
                filters={"subpath": [table]},
                limit=1,
                offset=0,
            )
        if not r_search["data"]:
            return None

        records = []
        for data in r_search["data"]:
            records.append(
                json.loads(data)
            )
        return records[0] if len(records) > 0 else None

    async def get_media_attachment(self, space_name: str, subpath: str, shortname: str) -> io.BytesIO | None:
        pass

    async def get_user_session(self, user_shortname: str, token: str) -> Tuple[int, str | None]:
        async with RedisServices() as redis:
            return 1, await redis.get_key(
                f"user_session:{user_shortname}"
            )

    async def remove_user_session(self, user_shortname: str) -> bool:
        async with RedisServices() as redis:
            return bool(
                await redis.del_keys([f"user_session:{user_shortname}"])
            )

    async def set_invitation(self, invitation_token: str, invitation_value):
        async with RedisServices() as redis_services:
            await redis_services.set_key(
                f"users:login:invitation:{invitation_token}",
                invitation_value
            )

    async def set_user_session(self, user_shortname: str, token: str) -> bool:
        async with RedisServices() as redis:
            if settings.max_sessions_per_user == 1:
                if await redis.get_key(
                        f"user_session:{user_shortname}"
                ):
                    await redis.del_keys([f"user_session:{user_shortname}"])

            return bool(await redis.set_key(
                key=f"user_session:{user_shortname}",
                value=hash_password(token),
                ex=settings.session_inactivity_ttl,
            ))

    async def set_url_shortner(self, token_uuid: str, url: str):
        async with RedisServices() as redis_services:
            await redis_services.set_key(
                f"short/{token_uuid}",
                url,
                ex=settings.url_shorter_expires,
                nx=False,
            )

    async def delete_url_shortner(self, token_uuid: str) -> bool:
        async with RedisServices() as redis_services:
            return bool(
                await redis_services.del_keys([f"short/{token_uuid}"])
            )


    async def delete_url_shortner_by_token(self, invitation_token: str) -> bool:
        #TODO: implement this method
        return True


    async def get_schema(self, space_name: str, schema_shortname: str, owner_shortname: str) -> dict:
        schema_path = (
                self.payload_path(space_name, "schema", core.Schema)
                / f"{schema_shortname}.json"
        )
        with open(schema_path) as schema_file:
            schema_content = json.load(schema_file)

        return resolve_schema_references(schema_content)

    async def check_uniqueness(self, unique_fields, search_str, redis_escape_chars) -> dict:
        async with RedisServices() as redis_man:
            for key, value in unique_fields.items():
                if not value:
                    continue

                value = value.translate(redis_escape_chars).replace("\\\\", "\\")
                if key == "email_unescaped":
                    value = f"{{{value}}}"

                redis_search_res = await redis_man.search(
                    space_name=settings.management_space,
                    search=search_str + f" @{key}:{value}",
                    limit=0,
                    offset=0,
                    filters={},
                )

                if redis_search_res and redis_search_res["total"] > 0:
                    return {"unique": False, "field": key}

        return {"unique": True}

    async def get_role_permissions(self, role: core.Role) -> list[core.Permission]:
        permissions_options = "|".join(role.permissions)
        async with RedisServices() as redis_services:
            permissions_search = await redis_services.search(
                space_name=settings.management_space,
                search=f"@shortname:{permissions_options}",
                filters={"subpath": ["permissions"]},
                limit=10000,
                offset=0,
            )
        if not permissions_search:
            return []

        role_permissions: list[core.Permission] = []

        for permission_doc in permissions_search["data"]:
            permission_doc = json.loads(permission_doc)
            if permission_doc['resource_type'] == 'permission':
                permission = core.Permission.model_validate(permission_doc)
                role_permissions.append(permission)

        return role_permissions

    async def get_user_roles(self, user_shortname: str) -> dict[str, core.Role]:
        user_meta: core.User = await self.load_user_meta(user_shortname)
        user_associated_roles = user_meta.roles
        user_associated_roles.append("logged_in")
        async with RedisServices() as redis_services:
            roles_search = await redis_services.search(
                space_name=settings.management_space,
                search="@shortname:(" + "|".join(user_associated_roles) + ")",
                filters={"subpath": ["roles"]},
                limit=10000,
                offset=0,
            )

        user_roles_from_groups = await self.get_user_roles_from_groups(user_meta)
        if not roles_search and not user_roles_from_groups:
            return {}

        user_roles: dict[str, core.Role] = {}

        all_user_roles_from_redis = []
        for redis_document in roles_search["data"]:
            all_user_roles_from_redis.append(redis_document)

        all_user_roles_from_redis.extend(user_roles_from_groups)
        for role_json in all_user_roles_from_redis:
            role = core.Role.model_validate(json.loads(role_json))
            user_roles[role.shortname] = role

        return user_roles

    async def load_user_meta(self, user_shortname: str) -> Any:
        async with RedisServices() as redis_services:
            user_meta_doc_id = redis_services.generate_doc_id(
                space_name=settings.management_space,
                schema_shortname="meta",
                subpath="users",
                shortname=user_shortname,
            )
            value: dict = await redis_services.get_doc_by_id(user_meta_doc_id)

            if not value:
                user = await self.load(
                    space_name=settings.management_space,
                    shortname=user_shortname,
                    subpath="users",
                    class_type=core.User,
                    user_shortname=user_shortname,
                )
                await redis_services.save_meta_doc(
                    settings.management_space,
                    "users",
                    user,
                )
            else:
                user = core.User.model_validate(value)
            return user

    async def generate_user_permissions(self, user_shortname: str) -> dict:
        try:
            user_permissions: dict = {}

            user_roles = await self.get_user_roles(user_shortname)
            for _, role in user_roles.items():
                role_permissions = await self.get_role_permissions(role)
                permission_world_record = await self.load_or_none(
                    settings.management_space,
                    'permissions',
                    "world",
                    core.Permission
                )
                if permission_world_record:
                    role_permissions.append(permission_world_record)

                for permission in role_permissions:
                    for space_name, permission_subpaths in permission.subpaths.items():
                        for permission_subpath in permission_subpaths:
                            permission_subpath = trans_magic_words(permission_subpath, user_shortname)
                            for permission_resource_types in permission.resource_types:
                                actions = set(permission.actions)
                                conditions = set(permission.conditions)
                                if (
                                        f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                        in user_permissions
                                ):
                                    old_perm = user_permissions[
                                        f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                    ]

                                    if isinstance(actions, list):
                                        actions = set(actions)
                                    actions |= set(old_perm["allowed_actions"])

                                    if isinstance(conditions, list):
                                        conditions = set(conditions)
                                    conditions |= set(old_perm["conditions"])

                                user_permissions[
                                    f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                ] = {
                                    "allowed_actions": list(actions),
                                    "conditions": list(conditions),
                                    "restricted_fields": permission.restricted_fields,
                                    "allowed_fields_values": permission.allowed_fields_values
                                }
            async with RedisServices() as redis_services:
                await redis_services.save_doc(
                    f"users_permissions_{user_shortname}", user_permissions
                )
            return user_permissions
        except Exception as e:
            logger.error(f"Error generating user permissions: {e}")
            raise api.Exception(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                error=api.Error(
                    type="system",
                    code=InternalErrorCode.UNPROCESSABLE_ENTITY,
                    message=str(e),
                ),
            )

    async def get_user_permissions(self, user_shortname: str) -> dict:
        async with RedisServices() as redis_services:
            user_permissions: dict = await redis_services.get_doc_by_id(
                f"users_permissions_{user_shortname}"
            )

            if not user_permissions:
                return await self.generate_user_permissions(user_shortname)

            return user_permissions

    async def get_user_by_criteria(self, key: str, value: str) -> str | None:
        async with RedisServices() as redis_services:
            user_search = await redis_services.search(
                space_name=settings.management_space,
                search=f"@{key}:({value.replace('@', '?')})",
                filters={"subpath": ["users"]},
                limit=10000,
                offset=0,
            )
        if not user_search["data"]:
            return None

        data = json.loads(user_search["data"][0])
        if data.get("shortname") and isinstance(data["shortname"], str):
            return data["shortname"]
        else:
            return None

    async def get_payload_from_event(self, event) -> dict:
        mypayload = await self.load_resource_payload(
            event.space_name,
            event.subpath,
            event.payload.body,
            getattr(sys_modules["models.core"], camel_case(event.resource_type)),
        )
        return mypayload if mypayload else {}

    async def get_user_roles_from_groups(self, user_meta: core.User) -> list:
        if not user_meta.groups:
            return []

        async with RedisServices() as redis_services:
            groups_search = await redis_services.search(
                space_name=settings.management_space,
                search="@shortname:(" + "|".join(user_meta.groups) + ")",
                filters={"subpath": ["groups"]},
                limit=10000,
                offset=0,
            )
            if not groups_search:
                return []

            roles = []
            for group in groups_search["data"]:
                group_json = json.loads(group)
                for role_shortname in group_json["roles"]:
                    role = await redis_services.get_doc_by_id(
                        redis_services.generate_doc_id(
                            space_name=settings.management_space,
                            schema_shortname="meta",
                            shortname=role_shortname,
                            subpath="roles"
                        )
                    )
                    if role:
                        roles.append(role)

        return roles

    async def drop_index(self, space_name):
        async with RedisServices() as redis_services:
            x = await redis_services.list_indices()
            if x:
                indices: list[str] = x
                for index in indices:
                    if index.startswith(f"{space_name}:"):
                        await redis_services.drop_index(index, True)

    async def initialize_spaces(self) -> None:
        if not settings.spaces_folder.is_dir():
            raise NotADirectoryError(
                f"{settings.spaces_folder} directory does not exist!"
            )

        spaces: dict[str, str] = {}
        for one in settings.spaces_folder.glob("*/.dm/meta.space.json"):
            match = SPACES_PATTERN.search(str(one))
            if not match:
                continue
            space_name = match.group(1)

            space_obj = core.Space.model_validate_json(one.read_text())
            spaces[space_name] = space_obj.model_dump_json()

        async with RedisServices() as redis_services:
            await redis_services.save_doc("spaces", spaces)

    async def create_user_premission_index(self) -> None:
        async with RedisServices() as redis_services:
            try:
                # Check if index already exist
                await redis_services.ft("user_permission").info()
            except Exception:
                await redis_services.ft("user_permission").create_index(
                    fields=[TextField("name")],  # type: ignore
                    definition=IndexDefinition(
                        prefix=["users_permissions"],
                        index_type=IndexType.JSON,
                    )
                )

    async def store_modules_to_redis(self, roles, groups, permissions) -> None:
        modules = [
            {"subpath": "roles", "value": roles},
            {"subpath": "groups", "value": groups},
            {"subpath": "permissions", "value": permissions},
        ]
        async with RedisServices() as redis_services:
            for module in modules:
                for _, object in module['value'].items():
                    await redis_services.save_meta_doc(
                        space_name=settings.management_space,
                        subpath=module['subpath'],
                        meta=object,
                    )

    async def delete_user_permissions_map_in_redis(self) -> None:
        async with RedisServices() as redis_services:
            search_query = Query("*").no_content()
            redis_res = await redis_services.ft("user_permission").search(search_query)  # type: ignore
            if redis_res and isinstance(redis_res, dict) and "results" in redis_res:
                results = redis_res["results"]
                keys = [doc["id"] for doc in results]
                if len(keys) > 0:
                    await redis_services.del_keys(keys)

    async def internal_save_model(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload: dict | None = None
    ):
        await self.save(
            space_name=space_name,
            subpath=subpath,
            meta=meta,
        )

        async with RedisServices() as redis:
            await redis.save_meta_doc(
                space_name,
                subpath,
                meta,
            )

            if payload:
                await self.save_payload_from_json(
                    space_name=space_name,
                    subpath=subpath,
                    meta=meta,
                    payload_data=payload,
                )
                payload.update(json.loads(meta.model_dump_json(exclude_none=True, warnings="error")))
                await redis.save_payload_doc(
                    space_name,
                    subpath,
                    meta,
                    payload,
                    ResourceType(snake_case(type(meta).__name__))
                )

    async def internal_sys_update_model(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            updates: dict,
            sync_redis: bool = True,
            payload_dict: dict[str, Any] = {},
    ):
        meta.updated_at = datetime.now()
        meta_updated = False
        payload_updated = False

        if not payload_dict:
            try:
                body = str(meta.payload.body) if meta and meta.payload else ""
                mydict = await self.load_resource_payload(
                    space_name, subpath, body, core.Content
                )
                payload_dict = mydict if mydict else {}
            except Exception:
                pass

        restricted_fields = [
            "uuid",
            "shortname",
            "created_at",
            "updated_at",
            "owner_shortname",
            "payload",
        ]
        old_version_flattend = {**meta.model_dump()}
        for key, value in updates.items():
            if key in restricted_fields:
                continue

            if key in meta.model_fields.keys():
                meta_updated = True
                meta.__setattr__(key, value)
            elif payload_dict:
                payload_dict[key] = value
                payload_updated = True

        if meta_updated:
            await self.update(
                space_name,
                subpath,
                meta,
                old_version_flattend,
                {**meta.model_dump()},
                list(updates.keys()),
                meta.shortname
            )
        if payload_updated and meta.payload and meta.payload.schema_shortname:
            await self.validate_payload_with_schema(
                payload_dict, space_name, meta.payload.schema_shortname
            )
            await self.save_payload_from_json(
                space_name, subpath, meta, payload_dict
            )

        if not sync_redis:
            return

        async with RedisServices() as redis_services:
            await redis_services.save_meta_doc(space_name, subpath, meta)
            if payload_updated:
                payload_dict.update(json.loads(meta.model_dump_json(exclude_none=True, warnings="error")))
                await redis_services.save_payload_doc(
                    space_name,
                    subpath,
                    meta,
                    payload_dict,
                    ResourceType(snake_case(type(meta).__name__)),
                )


    async def get_entry_by_var(
            self,
            key: str,
            val: str,
            logged_in_user,
            retrieve_json_payload: bool = False,
            retrieve_attachments: bool = False,
            retrieve_lock_status: bool = False,
    ) -> core.Record | None:
        spaces = await self.get_spaces()
        entry_doc = None
        entry_space = None
        async with RedisServices() as redis_services:
            for space_name, space in spaces.items():
                space = json.loads(space)
                if not space['indexing_enabled']:
                    continue
                search_res = await redis_services.search(
                    space_name=space_name,
                    search=f"@{key}:{val}*",
                    limit=1,
                    offset=0,
                    filters={},
                )
                if search_res["total"] > 0:
                    entry_doc = json.loads(search_res["data"][0])
                    entry_space = space_name
                    break

        if not entry_doc or not entry_space:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="media", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"
                ),
            )

        from utils.access_control import access_control
        if not await access_control.check_access(
                user_shortname=logged_in_user,
                space_name=entry_space,
                subpath=entry_doc["subpath"],
                resource_type=entry_doc["resource_type"],
                action_type=core.ActionType.view,
                resource_is_active=entry_doc["is_active"],
                resource_owner_shortname=entry_doc.get("owner_shortname"),
                resource_owner_group=entry_doc.get("owner_group_shortname"),
                entry_shortname=entry_doc.get("shortname")
        ):
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(
                    type="request",
                    code=InternalErrorCode.NOT_ALLOWED,
                    message="You don't have permission to this action [12]",
                ),
            )

        await plugin_manager.before_action(
            core.Event(
                space_name=entry_space,
                subpath=entry_doc["subpath"],
                shortname=entry_doc["shortname"],
                action_type=core.ActionType.view,
                resource_type=entry_doc["resource_type"],
                user_shortname=logged_in_user,
            )
        )

        resource_base_record = await get_record_from_redis_doc(
            self,
            space_name=entry_space,
            doc=entry_doc,
            retrieve_json_payload=retrieve_json_payload,
            retrieve_attachments=retrieve_attachments,
            validate_schema=True,
            retrieve_lock_status=retrieve_lock_status,
        )

        await plugin_manager.after_action(
            core.Event(
                space_name=entry_space,
                subpath=entry_doc["subpath"],
                shortname=entry_doc["shortname"],
                action_type=core.ActionType.view,
                resource_type=entry_doc["resource_type"],
                user_shortname=logged_in_user,
            )
        )

        return resource_base_record

    async def delete_space(self, space_name, record, owner_shortname):
        os.system(f"rm -r {settings.spaces_folder}/{space_name}")

    async def get_last_updated_entry(
            self,
            space_name: str,
            schema_names: list,
            retrieve_json_payload: bool,
            logged_in_user: str,
    ):
        pass

    async def get_group_users(self, group_name: str):
        async with RedisServices() as redis_services:
            users_docs = await redis_services.search(
                space_name=settings.management_space,
                schema_name="meta",
                filters={"subpath": ["users"]},
                limit=10000,
                offset=0,
                search=f"@groups:{{{group_name}}}",
            )

        if users_docs:
            return users_docs["data"]

        return []

    async def is_user_verified(self, user_shortname: str | None, identifier: str | None) -> bool:
        async with RedisServices() as redis_services:
            user: dict = await redis_services.get_doc_by_id(f"management:meta:users/{user_shortname}")
            if user:
                if identifier == "msisdn":
                    return bool(user.get("is_msisdn_verified", True))
                if identifier == "email":
                    return bool(user.get("is_email_verified", True))
            return False
