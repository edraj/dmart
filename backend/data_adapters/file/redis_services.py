import re
import json
import sys
from typing import Any, Awaitable
from redis.asyncio import Redis
from redis.asyncio.connection import BlockingConnectionPool
from models.api import RedisReducer, SortType
import models.core as core
from models.enums import ActionType, RedisReducerName, ResourceType, LockAction
from redis.commands.json.path import Path
from redis.commands.search.field import TextField, NumericField, TagField, Field
from redis.commands.search.index_definition import IndexDefinition, IndexType
from datetime import datetime

from redis.commands.search import Search, aggregation
from redis.commands.search.query import Query
from utils.helpers import camel_case, resolve_schema_references
from utils.internal_error_code import InternalErrorCode
from utils.query_policies_helper import generate_query_policies
from utils.settings import settings
import models.api as api
from fastapi import status
from fastapi.logger import logger
import redis


class RedisServices(Redis):
    META_SCHEMA : list[Field] = [
        TextField("$.uuid", no_stem=True, as_name="uuid"), # type: ignore
        TextField("$.shortname", sortable=True, no_stem=True, as_name="shortname"), # type: ignore
        TextField("$.slug", sortable=True, no_stem=True, as_name="slug"), # type: ignore
        TextField("$.subpath", sortable=True, no_stem=True, as_name="subpath"), # type: ignore
        TagField("$.subpath", as_name="exact_subpath"), # type: ignore
        TextField(
            "$.resource_type",
            sortable=True,
            no_stem=True,
            as_name="resource_type",
        ), # type: ignore
        TextField("$.displayname.en", sortable=True, as_name="displayname_en"), # type: ignore
        TextField("$.displayname.ar", sortable=True, as_name="displayname_ar"), # type: ignore
        TextField("$.displayname.ku", sortable=True, as_name="displayname_kd"), # type: ignore
        TextField("$.description.en", sortable=True, as_name="description_en"), # type: ignore
        TextField("$.description.ar", sortable=True, as_name="description_ar"), # type: ignore
        TextField("$.description.ku", sortable=True, as_name="description_kd"), # type: ignore
        TagField("$.is_active", as_name="is_active"), # type: ignore
        TextField(
            "$.payload.content_type",
            no_stem=True,
            as_name="payload_content_type",
        ), # type: ignore
        TextField(
            "$.payload.schema_shortname",
            no_stem=True,
            as_name="schema_shortname",
        ), # type: ignore
        NumericField("$.created_at", sortable=True, as_name="created_at"), # type: ignore
        NumericField("$.updated_at", sortable=True, as_name="updated_at"), # type: ignore
        TagField("$.view_acl.*", as_name="view_acl"), # type: ignore
        TagField("$.tags.*", as_name="tags"), # type: ignore
        TextField(
            "$.owner_shortname",
            sortable=True,
            no_stem=True,
            as_name="owner_shortname",
        ), # type: ignore
        TagField("$.query_policies.*", as_name="query_policies"), # type: ignore
        # User fields
        TextField("$.msisdn", sortable=True, as_name="msisdn"), # type: ignore
        TextField("$.email", sortable=True, as_name="email"), # type: ignore
        TagField("$.email", as_name="email_unescaped"), # type: ignore
        # Ticket fields
        TextField("$.state", sortable=True, no_stem=True, as_name="state"), # type: ignore
        TagField("$.is_open", as_name="is_open"), # type: ignore
        TextField(
            "$.workflow_shortname",
            sortable=True,
            no_stem=True,
            as_name="workflow_shortname",
        ), # type: ignore
        TextField(
            "$.collaborators.delivered_by",
            sortable=True,
            no_stem=True,
            as_name="collaborators_delivered_by",
        ), # type: ignore
        TextField(
            "$.collaborators.processed_by",
            sortable=True,
            no_stem=True,
            as_name="collaborators_processed_by",
        ), # type: ignore
        TextField(
            "$.resolution_reason",
            sortable=True,
            no_stem=True,
            as_name="resolution_reason",
        ), # type: ignore
        # Notification fields
        TextField("$.type", sortable=True, no_stem=True, as_name="type"), # type: ignore
        TagField("$.is_read", as_name="is_read"), # type: ignore
        TextField("$.priority", sortable=True, no_stem=True, as_name="priority"), # type: ignore
        TextField("$.reporter.type", sortable=True, as_name="reporter_type"), # type: ignore
        TextField("$.reporter.name", sortable=True, as_name="reporter_name"), # type: ignore
        TextField("$.reporter.channel", sortable=True, as_name="reporter_channel"), # type: ignore
        TextField(
            "$.reporter.distributor",
            sortable=True,
            as_name="reporter_distributor",
        ), # type: ignore
        TextField(
            "$.reporter.governorate",
            sortable=True,
            as_name="reporter_governorate",
        ), # type: ignore
        TextField(
            "$.reporter.msisdn",
            sortable=True,
            as_name="reporter_msisdn",
        ), # type: ignore
        TextField(
            "$.payload_string",
            sortable=False,
            as_name="payload_string",
        ),  # type: ignore
    ]  # type: ignore

    CUSTOM_CLASSES: list[type[core.Meta]] = [
        core.Role,
        core.Group,
        core.User,
        core.Permission,
    ]

    CUSTOM_INDICES = [
        {
            "space": "management",
            "subpath": "roles",
            "class": core.Role,
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
            "subpath": "groups",
            "class": core.Group,
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
            "subpath": "users",
            "class": core.User,
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
            "subpath": "permissions",
            "class": core.Permission,
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

    SYS_ATTRIBUTES = [
        "payload_string",
        "query_policies",
        "subpath",
        "resource_type",
        "meta_doc_id",
        "payload_doc_id",
        "payload_string",
        "view_acl",
    ]
    redis_indices: dict[str, dict[str, Search]] = {}
    POOL: BlockingConnectionPool = BlockingConnectionPool(
                            timeout=10,
                            host=settings.redis_host,
                            port=settings.redis_port,
                            password=settings.redis_password,
                            protocol=3,
                            max_connections=settings.redis_pool_max_connections,
                            decode_responses=True)
    
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(RedisServices, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        try:
            super().__init__(connection_pool=RedisServices.POOL)
        except redis.exceptions.ConnectionError as e:  # type: ignore
            print("[!FATAL]", e)
            sys.exit(127)

    async def close_pool(self):
        # print('{"Disconnecting connection pool":"initated"}')
        await self.aclose()
        await RedisServices.POOL.aclose()
        await RedisServices.POOL.disconnect(True)

    async def create_index(
        self,
        space_name: str,
        schema_name: str,
        redis_schema: list[Field],
        del_docs: bool = True,
    ):
        """
        create redis schema index, drop it if exist first
        """
        try:
            await self.redis_indices[space_name][schema_name].dropindex(
                delete_documents=del_docs
            )
        except Exception as _:
            pass
            # logger.error(f"Error at redis_services.create_index: {e}")

        await self.redis_indices[space_name][schema_name].create_index(
            redis_schema,
            definition=IndexDefinition(
                prefix=[
                    f"{space_name}:{schema_name}:",
                    f"{space_name}:{schema_name}/",
                ],
                index_type=IndexType.JSON,
            ),
        )
        # print(f"Created new index named {space_name}:{schema_name}\n")

    def get_redis_index_fields(self, key_chain, property, redis_schema_definition):
        """
        takes a key and a value of a schema definition, and returns the redis schema index
        """
        REDIS_SCHEMA_DATA_TYPES_MAPPER = {
            "string": TextField,
            "boolean": TagField,
            "integer": NumericField,
            "number": NumericField,
            "array": TagField,
        }
        if not isinstance(property, dict) or key_chain.endswith("."):
            return redis_schema_definition

        if "type" in property and property["type"] != "object":
            if property["type"] == "null" or not isinstance(
                property["type"], str
            ):
                return redis_schema_definition

            property_name = key_chain.replace(".", "_")
            sortable = True

            if (
                property["type"] == "array"
                and property.get("items", {}).get("type", None) == "object"
                and "items" in property
                and "properties" in property["items"]
            ):
                for property_key, property_value in property["items"][
                    "properties"
                ].items():
                    if property_value["type"] != "string":
                        continue
                    redis_schema_definition.append(
                        TagField(
                            f"$.{key_chain}.*.{property_key}",
                            as_name=f"{key_chain}_{property_key}",
                        )
                    )
                return redis_schema_definition

            if property["type"] == "array":
                key_chain += ".*"
                sortable = False

            redis_schema_definition.append(
                REDIS_SCHEMA_DATA_TYPES_MAPPER[property["type"]](
                    f"$.{key_chain}", sortable=sortable, as_name=property_name
                )
            )
            return redis_schema_definition

        if "oneOf" in property:
            for item in property["oneOf"]:
                redis_schema_definition = self.get_redis_index_fields(
                    key_chain, item, redis_schema_definition
                )
            return redis_schema_definition

        if "properties" not in property:
            return redis_schema_definition

        for property_key, property_value in property["properties"].items():
            redis_schema_definition = self.get_redis_index_fields(
                f"{key_chain}.{property_key}", property_value, redis_schema_definition
            )

        return redis_schema_definition

    def generate_redis_index_from_class(
        self, class_ref: type[core.Meta], exclude_from_index: list
    ) -> list[Field]:
        class_types_to_redis_fields_mapper = {
            "str": TextField,
            "bool": TextField,
            "UUID": TextField,
            "list": TagField,
            "datetime": NumericField,
            "set": TagField,
            "dict": TextField,
        }

        redis_schema : list[Field] = []
        for field_name, model_field in class_ref.model_fields.items():
            if field_name in exclude_from_index:
                continue

            mapper_key = None
            for allowed_type in list(class_types_to_redis_fields_mapper.keys()):
                if str(model_field.annotation).startswith(allowed_type):
                    mapper_key = allowed_type
                    break
            if not mapper_key:
                continue

            redis_index_column_type = class_types_to_redis_fields_mapper[mapper_key]

            redis_key = (
                f"$.{field_name}"
                if redis_index_column_type != TagField
                else f"$.{field_name}.*"
            )
            redis_schema.append(redis_index_column_type(redis_key, as_name=field_name))

        return redis_schema

    async def create_custom_indices(self, for_space: str | None = None):
        redis_schemas: dict[str, list] = {}
        for i, index in enumerate(self.CUSTOM_INDICES):
            if (
                for_space
                and index["space"] != for_space
                or not isinstance(index["exclude_from_index"], list)
            ):
                continue

            exclude_from_index: list = index["exclude_from_index"]

            redis_schemas.setdefault(f"{index['space']}", [])
            self.redis_indices.setdefault(
                f"{index['space']}:meta", {}
            )

            generated_schema_fields : list[Field] = self.generate_redis_index_from_class(
                self.CUSTOM_CLASSES[i], exclude_from_index
            )

            redis_schemas[f"{index['space']}"] = (
                self.append_unique_index_fields(
                    generated_schema_fields,
                    redis_schemas[f"{index['space']}"],
                )
            )

        for space_name, redis_schema in redis_schemas.items():
            redis_schema = self.append_unique_index_fields(
                redis_schema,
                self.META_SCHEMA,
            )
            await self.create_index(
                f"{space_name}",
                "meta",
                redis_schema,
            )

    async def create_indices(
        self,
        for_space: str | None = None,
        for_schemas: list | None = None,
        for_custom_indices: bool = True,
        del_docs: bool = True,
    ):
        """
        Loop over all spaces, and for each one we create: (only if indexing_enabled is true for the space)
        1-index for meta file called space_name:meta
        2-indices for schema files called space_name:schema_shortname
        """
        spaces = await self.get_doc_by_id("spaces")
        for space_name in spaces:
            space_obj = core.Space.model_validate_json(spaces[space_name])
            if (
                for_space and for_space != space_name
            ) or not space_obj.indexing_enabled:
                continue

            # CREATE REDIS INDEX FOR THE META FILES INSIDE THE SPACE
            self.redis_indices[f"{space_name}"] = {}
            self.redis_indices[f"{space_name}"]["meta"] = self.ft(
                f"{space_name}:meta"
            )

            await self.create_index(
                f"{space_name}", "meta", self.META_SCHEMA, del_docs
            )

            # CREATE REDIS INDEX FOR EACH SCHEMA DEFINITION INSIDE THE SPACE
            schemas_file_pattern = re.compile(r"(\w*).json")
            schemas_glob = "*.json"
            path = (
                settings.spaces_folder
                / space_name
                / "schema"
            )

            for schema_path in path.glob(schemas_glob):
                # GET SCHEMA SHORTNAME
                match = schemas_file_pattern.search(str(schema_path))
                if not match or not schema_path.is_file():
                    continue
                schema_shortname = match.group(1)

                if for_schemas and schema_shortname not in for_schemas:
                    continue

                if schema_shortname in ["meta_schema", "meta"]:
                    continue

                # GET SCHEMA PROPERTIES AND
                # GENERATE REDIS INDEX DEFINITION BY MAPPIN SCHEMA PROPERTIES TO REDIS INDEX FIELDS
                schema_content = json.loads(schema_path.read_text())
                schema_content = resolve_schema_references(schema_content)
                redis_schema_definition : list[Field] = self.META_SCHEMA
                if "properties" in schema_content:
                    for key, property in schema_content["properties"].items():
                        generated_schema_fields = self.get_redis_index_fields(
                            key, property, []
                        )
                        redis_schema_definition = self.append_unique_index_fields(
                            generated_schema_fields, redis_schema_definition
                        )

                elif "oneOf" in schema_content:
                    for item in schema_content["oneOf"]:
                        for key, property in item["properties"].items():
                            generated_schema_fields = self.get_redis_index_fields(
                                key, property, []
                            )
                            redis_schema_definition = (
                                self.append_unique_index_fields(
                                    generated_schema_fields, redis_schema_definition
                                )
                            )

                if redis_schema_definition:
                    self.redis_indices[f"{space_name}"][
                        schema_shortname
                    ] = self.ft(f"{space_name}:{schema_shortname}")
                    field_names = [f.as_name for f in redis_schema_definition]
                    if "meta_doc_id" not in field_names:
                        redis_schema_definition.append(TextField("$.meta_doc_id", no_stem=True, as_name="meta_doc_id")) # type: ignore

                    await self.create_index(
                        f"{space_name}",
                        schema_shortname,
                        redis_schema_definition,
                        del_docs,
                    )

        if for_custom_indices:
            await self.create_custom_indices(for_space)

    def append_unique_index_fields(self, new_index: list[Field], base_index: list[Field]):
        base_index_clone = base_index.copy()
        for field in new_index:
            registered_field = False
            for base_field in base_index_clone:
                if (
                    field.redis_args()[2]  # Compare field name
                    == base_field.redis_args()[2]  # Compare AS name
                ):
                    registered_field = True
                    break
            if not registered_field:
                base_index_clone.append(field)

        return base_index_clone

    def generate_doc_id(
        self,
        space_name: str,
        schema_shortname: str,
        shortname: str,
        subpath: str,
    ):
        # if subpath[0] == "/":
        #     subpath = subpath[1:]
        # if subpath[-1] == "/":
        #     subpath = subpath[:-1]
        subpath = subpath.strip("/")
        return f"{space_name}:{schema_shortname}:{subpath}/{shortname}"

    def prepare_meta_doc(
        self, space_name: str, subpath: str, meta: core.Meta
    ):
        resource_type = ResourceType(meta.__class__.__name__.lower())
        meta_doc_id = self.generate_doc_id(
            space_name, "meta", meta.shortname, subpath
        )
        payload_doc_id = None
        if meta.payload and meta.payload.schema_shortname:
            payload_doc_id = self.generate_doc_id(
                space_name,
                meta.payload.schema_shortname,
                meta.shortname,
                subpath,
            )
        meta.model_rebuild()
        meta_json = json.loads(meta.model_dump_json(serialize_as_any=False, exclude_none=True,warnings="error"))
        meta_json["query_policies"] = generate_query_policies(
            space_name,
            subpath,
            resource_type,
            meta.is_active,
            meta.owner_shortname,
            meta.owner_group_shortname,
            meta.shortname,
        )
        meta_json["view_acl"] = self.generate_view_acl(meta_json.get("acl"))
        meta_json["subpath"] = subpath
        meta_json["resource_type"] = resource_type
        meta_json["created_at"] = meta.created_at.timestamp()
        meta_json["updated_at"] = meta.updated_at.timestamp()
        meta_json["payload_doc_id"] = payload_doc_id

        return meta_doc_id, meta_json
    
    def generate_view_acl(self, acl: list[dict[str, Any]] | None) -> list[str] | None:
        if not acl:
            return None
        
        view_acl: list[str] = []
        
        for access in acl:
            if ActionType.view in access.get("allowed_actions", []) or ActionType.query in access.get("allowed_actions", []):
                view_acl.append(access["user_shortname"])
                
        return view_acl

    async def save_meta_doc(
        self, space_name: str, subpath: str, meta: core.Meta
    ):
        meta_doc_id, meta_json = self.prepare_meta_doc(
            space_name, subpath, meta
        )
        await self.save_doc(meta_doc_id, meta_json)
        return meta_doc_id, meta_json

    def prepare_payload_doc(
        self,
        space_name: str,
        subpath: str,
        meta: core.Meta,
        payload: dict,
        resource_type: ResourceType = ResourceType.content,
    ):
        if meta.payload is None:
            print(
                f"Missing payload for {space_name}/{subpath} of type {resource_type}"
            )
            return "", {}
        if meta.payload.body is None:
            print(
                f"Missing body for {space_name}/{subpath} of type {resource_type}"
            )
            return "", {}
        if not isinstance(meta.payload.body, str):
            print("body should be type of string")
            return "", {}
        payload_shortname = meta.payload.body.split(".")[0]
        meta_doc_id = self.generate_doc_id(
            space_name, "meta", payload_shortname, subpath
        )
        docid = self.generate_doc_id(
            space_name,
            meta.payload.schema_shortname or "",
            payload_shortname,
            subpath,
        )

        payload["query_policies"] = generate_query_policies(
            space_name,
            subpath,
            resource_type,
            meta.is_active,
            meta.owner_shortname,
            meta.owner_group_shortname,
            meta.shortname,
        )
        if not payload["query_policies"]:
            print(
                f"Warning: this entry `{space_name}/{subpath}/{meta.shortname}` can't be accessed"
            )
        payload["subpath"] = subpath
        payload["resource_type"] = resource_type
        payload["shortname"] = payload_shortname
        payload["meta_doc_id"] = meta_doc_id

        return docid, payload

    async def save_payload_doc(
        self,
        space_name: str,
        subpath: str,
        meta: core.Meta,
        payload: dict,
        resource_type: ResourceType = ResourceType.content,
    ):
        docid, payload = self.prepare_payload_doc(
            space_name, subpath, meta, payload, resource_type
        )
        if docid == "":
            return
        await self.save_doc(docid, payload)

    async def get_payload_doc(self, doc_id: str, resource_type: ResourceType):
        resource_class = getattr(
            sys.modules["models.core"],
            camel_case(resource_type),
        )
        payload_redis_doc = await self.get_doc_by_id(doc_id)
        payload_doc_content: dict = {}
        if not payload_redis_doc:
            return payload_doc_content

        not_payload_attr = RedisServices.SYS_ATTRIBUTES + list(
            resource_class.model_fields.keys()
        )
        for key, value in payload_redis_doc.items():
            if key not in not_payload_attr:
                payload_doc_content[key] = value
        return payload_doc_content

    async def save_lock_doc(
        self,
        space_name: str,
        subpath: str,
        payload_shortname: str,
        owner_shortname: str,
        ttl: int,
    ) -> LockAction:
        lock_doc_id = self.generate_doc_id(
            space_name, "lock", payload_shortname, subpath
        )
        lock_data = await self.get_lock_doc(
            space_name, subpath, payload_shortname
        )
        if not lock_data:
            payload = {
                "owner_shortname": owner_shortname,
                "lock_time": str(datetime.now().isoformat()),
            }
            result = await self.save_doc(lock_doc_id, payload, nx=True)
            if result is None:
                lock_payload = await self.get_lock_doc(
                    space_name, subpath, payload_shortname
                )
                if lock_payload["owner_shortname"] != owner_shortname:
                    raise api.Exception(
                        status_code=status.HTTP_403_FORBIDDEN,
                        error=api.Error(
                            type="lock",
                            code=InternalErrorCode.LOCKED_ENTRY,
                            message=f"Entry is already locked by {lock_payload['owner_shortname']}",
                        ),
                    )
            lock_type = LockAction.lock
        else:
            lock_type = LockAction.extend
        await self.set_ttl(lock_doc_id, ttl)
        return lock_type

    async def get_lock_doc(
        self,
        space_name: str,
        subpath: str,
        payload_shortname: str,
    ):
        lock_doc_id = self.generate_doc_id(
            space_name, "lock", payload_shortname, subpath
        )
        return await self.get_doc_by_id(lock_doc_id)

    async def delete_lock_doc(
        self,
        space_name: str,
        subpath: str,
        payload_shortname: str,
    ):
        await self.delete_doc(
            space_name, "lock", payload_shortname, subpath
        )

    async def is_entry_locked(
        self,
        space_name: str,
        subpath: str,
        shortname: str,
        user_shortname: str,
    ):
        lock_payload = await self.get_lock_doc(
            space_name, subpath, shortname
        )
        if lock_payload:
            if user_shortname:
                return lock_payload["owner_shortname"] != user_shortname
            else:
                return True
        return False

    async def save_doc(
        self, doc_id: str, payload: dict, path: str = Path.root_path(), nx: bool = False
    ):
        x = self.json().set(doc_id, path, payload, nx=nx)
        if x and isinstance(x, Awaitable):
            await x

    async def save_bulk(self, data: list, path: str = Path.root_path()):
        pipe = self.pipeline()
        for document in data:
            pipe.json().set(document["doc_id"], path, document["payload"])
        return await pipe.execute()

    async def get_count(self, space_name: str, schema_shortname: str):
        ft_index = self.ft(f"{space_name}:{schema_shortname}")

        try:
            info = await ft_index.info()
            return info["num_docs"]  # type: ignore
        except Exception as e:
            logger.error(f"Error at redis_services.get_count: {e}")
            return 0

        # aggregate_request = AggregateRequest().group_by([], count_reducer().alias("counter"))
        # aggregate = await ft_index.aggregate(aggregate_request)
        # print("\n\n\n aggregate res: ", aggregate.rows, "\n\n")

    async def search(
        self,
        space_name: str,
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
    ):
        # Tries to get the index from the provided space
        try:
            ft_index = self.ft(f"{space_name}:{schema_name}")
            await ft_index.info()
        except Exception as e:
            logger.error(
                f"Error accessing index: {space_name}:{schema_name}, at redis_services.search: {e}"
            )
            return {"data": [], "total": 0}

        search_query = Query(
            query_string=self.prepare_query_string(search, filters, exact_subpath)
        )

        if highlight_fields:
            search_query.highlight(highlight_fields, ["", ""])

        if sort_by:
            search_query.sort_by(sort_by, sort_type == SortType.ascending)

        if return_fields:
            search_query.return_fields(*return_fields)

        search_query.paging(offset, limit)

        try:
            # print(f"ARGS {search_query.get_args()} O {search_query.query_string()}")
            search_res = await ft_index.search(query=search_query) # type: ignore
            if (
                isinstance(search_res, dict)
                and "results" in search_res
                and "total_results" in search_res
            ):

                return {
                    "data": [
                        one["extra_attributes"]["$"]
                        for one in search_res["results"]
                        if "extra_attributes" in one
                    ],
                    "total": search_res["total_results"],
                }
            else:
                return {}
        except Exception:
            return {}

    async def aggregate(
        self,
        space_name: str,
        search: str,
        filters: dict[str, str | list],
        group_by: list[str],
        reducers: list[RedisReducer],
        max: int = 10,
        exact_subpath: bool = False,
        sort_type: SortType = SortType.ascending,
        sort_by: str | None = None,
        schema_name: str = "meta",
        load: list = [],
    ) -> list:
        # Tries to get the index from the provided space
        try:
            ft_index = self.ft(f"{space_name}:{schema_name}")
            await ft_index.info()
        except Exception:
            return []

        aggr_request = aggregation.AggregateRequest(
            self.prepare_query_string(search, filters, exact_subpath)
        )
        if group_by:
            reducers_functions = [
                RedisReducerName.mapper(reducer.reducer_name)(*reducer.args).alias(
                    reducer.alias
                )
                for reducer in reducers
            ]
            aggr_request.group_by(group_by, *reducers_functions)

        if sort_by:
            aggr_request.sort_by(
                [# type: ignore
                    str(
                        aggregation.Desc(f"@{sort_by}")
                        if sort_type == SortType.ascending
                        else aggregation.Asc(f"@{sort_by}")
                    )
                ],
                max=max,
            )

        if load:
            aggr_request.load(*load)

        try:
            aggr_res = await ft_index.aggregate(aggr_request)  # type: ignore
            if aggr_res.get("results") and isinstance(aggr_res["results"], list):  # type: ignore
                return aggr_res["results"]  # type: ignore
        except Exception:
            pass
        return []

    def prepare_query_string(
        self, search: str, filters: dict[str, str | list], exact_subpath: bool
    ):
        query_string = search

        redis_escape_chars = str.maketrans(
            {":": r"\:", "/": r"\/", "-": r"\-", " ": r"\ "}
        )
        if filters.get("query_policies", None) == []:
            filters["query_policies"] = ["__NONE__"]
            
        for item in filters.items():
            if item[0] == "tags" and item[1]:
                query_string += (
                    " @"
                    + item[0]
                    + ":{"
                    + "|".join(item[1]).translate(redis_escape_chars)
                    + "}"
                )
            elif item[0] == "query_policies" and item[1] is not None:
                query_string += (
                    f" ((@{item[0]}:{{" + "|".join(item[1]).translate(redis_escape_chars) + "})"
                )
                if filters.get("user_shortname", None) is not None:
                    query_string += (
                        f" | (@view_acl:{{{filters['user_shortname']}}}) )"
                    )
                else:
                    query_string += ")"
            elif item[0] == "created_at" and item[1]:
                query_string += f" @{item[0]}:{item[1]}"
            elif item[0] == "subpath" and exact_subpath:
                search_value = ""
                for subpath in item[1]:  # Handle existence/absence of `/`
                    search_value += "|" + subpath.strip("/")
                    search_value += "|" + f"/{subpath}".replace("//", "/")

                exact_subpath_value = search_value.strip("|").translate(
                    redis_escape_chars
                )
                query_string += f" @exact_subpath:{{{exact_subpath_value}}}"
            elif item[0] == "subpath" and item[1][0] == "/":
                pass
            elif item[1] and item[0] != "user_shortname":
                query_string += " @" + item[0] + ":(" + "|".join(item[1]) + ")"

        return query_string or "*"

    async def get_doc_by_id(self, doc_id: str) -> Any:
        try:
            x = self.json().get(name=doc_id)
            if x and isinstance(x, Awaitable):
                value = await x
                if isinstance(value, dict):
                    return value
                if isinstance(value, str):
                    return json.loads(value)
                else:
                   raise Exception(f"Not json dict at id: {doc_id}. data: {value=}")
            else:
                raise Exception(f"Not awaitable {x=}")
        except Exception as e:
            logger.warning(f"Error at redis_services.get_doc_by_id: {doc_id=} {e}")
        return {}

    async def get_docs_by_ids(self, docs_ids: list[str]) -> list:
        try:
            x = self.json().mget(docs_ids, "$")
            if x and isinstance(x, Awaitable):
                value = await x
                if isinstance(value, list):
                    return value
        except Exception as e:
            logger.warning(f"Error at redis_services.get_docs_by_ids: {e}")
        return []

    async def get_content_by_id(self, doc_id: str) -> Any:
        try:
            return await self.get(doc_id)
        except Exception as e:
            logger.warning(f"Error at redis_services.get_content_by_id: {e}")
            return ""

    async def delete_doc(
        self, space_name, schema_shortname, shortname, subpath
    ):
        docid = self.generate_doc_id(
            space_name, schema_shortname, shortname, subpath
        )
        try:
            x = self.json().delete(key=docid)
            if x and isinstance(x, Awaitable):
                await x
        except Exception as e:
            logger.warning(f"Error at redis_services.delete_doc: {e}")

    async def move_payload_doc(
        self,
        space_name,
        schema_shortname,
        src_shortname,
        src_subpath,
        dest_shortname,
        dest_subpath,
    ):
        docid = self.generate_doc_id(
            space_name, schema_shortname, src_shortname, src_subpath
        )

        try:
            doc_content = await self.get_doc_by_id(docid)
            await self.delete_doc(
                space_name, schema_shortname, src_shortname, src_subpath
            )

            new_docid = self.generate_doc_id(
                space_name, schema_shortname, dest_shortname, dest_subpath
            )
            await self.save_doc(new_docid, doc_content)

        except Exception as e:
            logger.warning(f"Error at redis_services.move_payload_doc: {e}")

    async def move_meta_doc(
        self, space_name, src_shortname, src_subpath, dest_subpath, meta
    ):
        try:
            await self.delete_doc(
                space_name, "meta", src_shortname, src_subpath
            )
            await self.save_meta_doc(space_name, dest_subpath, meta)
        except Exception as e:
            logger.warning(f"Error at redis_services.move_meta_doc: {e}")

    async def get_keys(self, pattern: str = "*") -> list:
        try:
            value = await self.keys(pattern)
            if isinstance(value, list):
                return value
        except Exception as e:
            logger.warning(f"Error at redis_services.get_keys: {e}")
        return []

    async def del_keys(self, keys: list):
        try:
            return await self.delete(*keys)
        except Exception as e:
            logger.warning(f"Error at redis_services.del_keys {keys}: {e}")
            return False

    async def get_key(self, key) -> str | None:
        value = await self.get(key)
        if isinstance(value, str):
            return value
        else:
            return None

    async def getdel_key(self, key) -> str | None:
        value = await self.getdel(key)
        if isinstance(value, str):
            return value
        else:
            return None

    async def set_key(self, key, value, ex=None, nx: bool = False):
        return await self.set(key, value, ex=ex, nx=nx)

    async def set_ttl(self, key: str, ttl: int):
        return await self.expire(key, ttl)

    async def drop_index(self, name: str, delete_docs: bool = False):
        try:
            ft_index = self.ft(name)
            await ft_index.dropindex(delete_docs)
            return True
        except Exception:
            return False

    async def list_indices(self):
        x = self.ft().execute_command("FT._LIST")
        if x and isinstance(x, Awaitable):
            return await x
        
    
    
    async def get_all_document_ids(self, index: str, search_str: str = "*") -> list[str]:        
        # Initialize the list to hold document IDs
        document_ids = []
        
        # Fetch all document IDs
        ft_index = self.ft(index)
        total_docs = int((await ft_index.info())['num_docs'])  # type: ignore
        
        batch_size = 10000  # You can adjust the batch size based on your needs
        
        for offset in range(0, total_docs, batch_size):
            query = Query(search_str).paging(offset, batch_size)
            results = ft_index.search(query)  # type: ignore
            if results and isinstance(results, Awaitable):
                results = await results
            
            if 'results' not in results or not isinstance(results['results'], list):  # type: ignore
                break
            document_ids.extend([doc['id'] for doc in results['results']]) #type: ignore
        
        return document_ids
