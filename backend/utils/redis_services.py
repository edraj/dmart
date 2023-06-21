import asyncio
import re
import json
import sys
from typing import Any
from uuid import UUID
from redis.asyncio import BlockingConnectionPool, Redis
from models.api import SortType
import models.core as core
from models.enums import ResourceType, LockAction
from redis.commands.json.path import Path
from redis.commands.search.field import TextField, NumericField, TagField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from datetime import datetime

# from redis.commands.search.aggregation import AggregateRequest
# from redis.commands.search.reducers import count as count_reducer
from redis.commands.search import Search, aggregation
from redis.commands.search.query import Query
from utils.helpers import branch_path, camel_case, resolve_schema_references
from utils.settings import settings
import models.api as api
from fastapi import status
from redis.exceptions import ResponseError as RedisResponseError
from fastapi.logger import logger




class RedisServices(object):

    POOL = BlockingConnectionPool(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        decode_responses=True,
        max_connections=200
    )

    CUSTOM_INDICES = [
        {
            "space": "management",
            "branch": settings.management_space_branch,
            "subpath": "roles",
            "class": core.Role,
            "exclude_from_index": [
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
            "class": core.Group,
            "exclude_from_index": [
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
            "class": core.User,
            "exclude_from_index": [
                "is_active",
                "description",
                "displayname",
                "payload",
                "password",
                "is_email_verified",
                "is_msisdn_verified",
                "type",
                "force_password_change",
            ],
        },
        {
            "space": "management",
            "branch": settings.management_space_branch,
            "subpath": "permissions",
            "class": core.Permission,
            "exclude_from_index": [
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
        "branch_name",
        "query_policies",
        "subpath",
        "resource_type",
        "meta_doc_id",
        "payload_doc_id",
        "payload_string"
    ]
    redis_indices: dict[str, dict[str, Search]] = {}
    is_pytest = False


    def __await__(self):
        return self.init().__await__()

    async def init(self):
        if not hasattr(self, "client"):
            self.client = await Redis(connection_pool=self.POOL)
            if self.is_pytest:
                try:
                    await self.client.ping()
                except RuntimeError:
                    pass
        return self

    def __del__(self):
        # Close connection when this object is destroyed
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.client.close())
            else:
                loop.run_until_complete(self.client.close())
        except Exception:
            pass

    async def __aenter__(self):
        if not hasattr(self, "client"):
            self.client = await Redis(connection_pool=self.POOL)
            if self.is_pytest:
                try:
                    await self.client.ping()
                except RuntimeError:
                    pass
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.client.close()

    async def create_index(
        self, 
        space_branch_name: str, 
        schema_name: str, 
        redis_schema: tuple, 
        del_docs: bool = True
    ):
        """
        create redis schema index, drop it if exist first
        """
        try:
            await self.redis_indices[space_branch_name][schema_name].dropindex(
                delete_documents=del_docs
            )
        except Exception as e:
            pass
            # logger.error(f"Error at redis_services.create_index: {e}")

        await self.redis_indices[space_branch_name][schema_name].create_index(
            redis_schema,
            definition=IndexDefinition(
                prefix=[
                    f"{space_branch_name}:{schema_name}:",
                    f"{space_branch_name}:{schema_name}/",
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
        if type(property) != dict:
            return redis_schema_definition

        if "type" in property and property["type"] != "object":
            if property["type"] in ["null", "boolean"] or type(property["type"]) != str:
                return redis_schema_definition

            property_name = key_chain.replace(".", "_")
            sortable = True

            if (
                property["type"] == "array"
                and property.get("items", {}).get("type", None) == "object"
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
        self, class_ref: core.Resource, exclude_from_index: list
    ) -> tuple:
        class_types_to_redis_fields_mapper = {
            str: TextField,
            bool: TextField,
            UUID: TextField,
            list: TagField,
            datetime: NumericField,
            set: TagField,
            dict: TextField,
        }

        redis_schema = [
            TextField("$.subpath", no_stem=True, as_name="subpath"),
            TagField("$.subpath", as_name="exact_subpath"),
            TextField(
                "$.resource_type", sortable=True, no_stem=True, as_name="resource_type"
            ),
            TextField(
                "$.branch_name", sortable=True, no_stem=True, as_name="branch_name"
            ),
            TagField("$.query_policies.*", as_name="query_policies"),
            TextField(
                "$.payload_string",
                sortable=False,
                as_name="payload_string",
            ),
        ]
        for field_name, model_field in class_ref.__fields__.items():

            if field_name in exclude_from_index:
                continue

            mapper_key = None
            for field_type in model_field.outer_type_.__mro__:
                if field_type in class_types_to_redis_fields_mapper.keys():
                    mapper_key = field_type
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

        return tuple(redis_schema)

    async def create_custom_indices(self, for_space: str | None = None):
        redis_schemas: dict[str, list] = {}
        for index in self.CUSTOM_INDICES:
            if for_space and index["space"] != for_space:
                continue

            redis_schemas.setdefault(f"{index['space']}:{index['branch']}", [])
            self.redis_indices.setdefault(f"{index['space']}:meta", {})

            generated_schema_fields = self.generate_redis_index_from_class(
                index["class"], index["exclude_from_index"]
            )

            redis_schemas[
                f"{index['space']}:{index['branch']}"
            ] = self.append_unique_index_fields(
                generated_schema_fields,
                redis_schemas[f"{index['space']}:{index['branch']}"],
            )

        for space_branch, redis_schema in redis_schemas.items():
            await self.create_index(
                f"{space_branch}",
                "meta",
                tuple(redis_schema),
            )

    async def create_indices(
        self, 
        for_space: str | None = None, 
        for_schemas: list | None = None,
        for_custom_indices: bool = True,
        del_docs: bool = True
    ):
        """
        Loop over all spaces, and for each one we create: (only if indexing_enabled is true for the space)
        1-index for meta file called space_name:meta
        2-indices for schema files called space_name:schema_shortname
        """
        spaces = await self.get_doc_by_id("spaces")
        for space_name in spaces:
            space_obj = core.Space.parse_raw(spaces[space_name])
            if (
                for_space and for_space != space_name
            ) or not space_obj.indexing_enabled:
                continue

            for branch_name in space_obj.branches:

                # CREATE REDIS INDEX FOR THE META FILES INSIDE THE SPACE
                self.redis_indices[f"{space_name}:{branch_name}"] = {}
                self.redis_indices[f"{space_name}:{branch_name}"][
                    "meta"
                ] = self.client.ft(f"{space_name}:{branch_name}:meta")

                meta_schema = (
                    TextField("$.uuid", no_stem=True, as_name="uuid"),
                    TextField("$.branch_name", no_stem=True, as_name="branch_name"),
                    TextField(
                        "$.shortname", sortable=True, no_stem=True, as_name="shortname"
                    ),
                    TextField(
                        "$.slug", sortable=True, no_stem=True, as_name="slug"
                    ),
                    TextField(
                        "$.subpath", sortable=True, no_stem=True, as_name="subpath"
                    ),
                    TagField("$.subpath", as_name="exact_subpath"),
                    TextField(
                        "$.resource_type",
                        sortable=True,
                        no_stem=True,
                        as_name="resource_type",
                    ),
                    TextField(
                        "$.displayname.en", sortable=True, as_name="displayname_en"
                    ),
                    TextField(
                        "$.displayname.ar", sortable=True, as_name="displayname_ar"
                    ),
                    TextField(
                        "$.displayname.kd", sortable=True, as_name="displayname_kd"
                    ),
                    TextField(
                        "$.description.en", sortable=True, as_name="description_en"
                    ),
                    TextField(
                        "$.description.ar", sortable=True, as_name="description_ar"
                    ),
                    TextField(
                        "$.description.kd", sortable=True, as_name="description_kd"
                    ),
                    TagField("$.is_active", as_name="is_active"),
                    TextField(
                        "$.payload.content_type",
                        no_stem=True,
                        as_name="payload_content_type",
                    ),
                    TextField(
                        "$.payload.schema_shortname",
                        no_stem=True,
                        as_name="schema_shortname",
                    ),
                    NumericField("$.created_at", sortable=True, as_name="created_at"),
                    NumericField("$.updated_at", sortable=True, as_name="updated_at"),
                    TextField("$.latest_version_hash", as_name="latest_version_hash"),
                    TagField("$.tags.*", as_name="tags"),
                    TextField(
                        "$.owner_shortname",
                        sortable=True,
                        no_stem=True,
                        as_name="owner_shortname",
                    ),
                    TagField("$.query_policies.*", as_name="query_policies"),
                    # User fields
                    TextField("$.msisdn", sortable=True, as_name="msisdn"),
                    TextField("$.email", sortable=True, as_name="email"),
                    # Ticket fields
                    TextField("$.state", sortable=True, no_stem=True, as_name="state"),
                    TagField("$.is_open", as_name="is_open"),
                    TextField(
                        "$.workflow_shortname",
                        sortable=True,
                        no_stem=True,
                        as_name="workflow_shortname",
                    ),
                    TextField(
                        "$.collaborators.delivered_by",
                        sortable=True,
                        no_stem=True,
                        as_name="collaborators_delivered_by",
                    ),
                    TextField(
                        "$.collaborators.processed_by",
                        sortable=True,
                        no_stem=True,
                        as_name="collaborators_processed_by",
                    ),
                    TextField(
                        "$.resolution_reason",
                        sortable=True,
                        no_stem=True,
                        as_name="resolution_reason",
                    ),
                    # Notification fields
                    TextField("$.type", sortable=True, no_stem=True, as_name="type"),
                    TagField("$.is_read", as_name="is_read"),
                    TextField(
                        "$.priority", sortable=True, no_stem=True, as_name="priority"
                    ),
                    TextField(
                        "$.reporter.type", sortable=True, as_name="reporter_type"
                    ),
                    TextField(
                        "$.reporter.name", sortable=True, as_name="reporter_name"
                    ),
                    TextField(
                        "$.reporter.channel", sortable=True, as_name="reporter_channel"
                    ),
                    TextField(
                        "$.reporter.distributor",
                        sortable=True,
                        as_name="reporter_distributor",
                    ),
                    TextField(
                        "$.reporter.governorate",
                        sortable=True,
                        as_name="reporter_governorate",
                    ),
                    TextField(
                        "$.payload_string",
                        sortable=False,
                        as_name="payload_string",
                    ),
                )

                await self.create_index(
                    f"{space_name}:{branch_name}", "meta", meta_schema, del_docs
                )

                # CREATE REDIS INDEX FOR EACH SCHEMA DEFINITION INSIDE THE SPACE
                schemas_file_pattern = re.compile(r"(\w*).json")
                schemas_glob = "*.json"
                path = (
                    settings.spaces_folder
                    / space_name
                    / branch_path(branch_name)
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

                    if schema_shortname == "meta_schema":
                        continue

                    # GET SCHEMA PROPERTIES AND
                    # GENERATE REDIS INDEX DEFINITION BY MAPPIN SCHEMA PROPERTIES TO REDIS INDEX FIELDS
                    schema_content = json.loads(schema_path.read_text())
                    schema_content = resolve_schema_references(schema_content)
                    redis_schema_definition = list(meta_schema)
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
                        self.redis_indices[f"{space_name}:{branch_name}"][
                            schema_shortname
                        ] = self.client.ft(
                            f"{space_name}:{branch_name}:{schema_shortname}"
                        )
                        redis_schema_definition.append(
                            TextField(
                                "$.meta_doc_id", no_stem=True, as_name="meta_doc_id"
                            )
                        )

                        await self.create_index(
                            f"{space_name}:{branch_name}",
                            schema_shortname,
                            tuple(redis_schema_definition),
                            del_docs
                        )

        if for_custom_indices:
            await self.create_custom_indices(for_space)

    def append_unique_index_fields(self, new_index: tuple, base_index: list):
        for field in new_index:
            registered_field = False
            for base_field in base_index:
                if (
                    field.redis_args()[0] == base_field.redis_args()[0]
                    and field.redis_args()[2]  # Compare field name
                    == base_field.redis_args()[2]  # Compare AS name
                ):
                    registered_field = True
                    break
            if not registered_field:
                base_index.append(field)

        return base_index

    def generate_doc_id(
        self,
        space_name: str,
        branch_name: str | None,
        schema_shortname: str,
        shortname: str,
        subpath: str,
    ):
        # if subpath[0] == "/":
        #     subpath = subpath[1:]
        # if subpath[-1] == "/":
        #     subpath = subpath[:-1]
        subpath = subpath.strip("/")
        return f"{space_name}:{branch_name}:{schema_shortname}:{subpath}/{shortname}"

    def generate_query_policies(
        self,
        space_name: str,
        subpath: str,
        resource_type: str,
        is_active: bool,
        owner_shortname: str,
        owner_group_shortname: str | None,
    ) -> list:
        subpath_parts = subpath.split("/")
        if subpath[0] == "/":
            subpath_parts[0] = "/"
        else:
            subpath_parts.insert(0, "/")

        query_policies: list = []
        full_subpath = ""
        for subpath_part in subpath_parts:
            full_subpath += subpath_part
            query_policies.append(
                f"{space_name}:{full_subpath}:{resource_type}:{str(is_active).lower()}:{owner_shortname}"
            )
            if owner_group_shortname is None:
                query_policies.append(
                    f"{space_name}:{full_subpath}:{resource_type}:{str(is_active).lower()}"
                )
            else:
                query_policies.append(
                    f"{space_name}:{full_subpath}:{resource_type}:{str(is_active).lower()}:{owner_group_shortname}"
                )

            full_subpath_parts = full_subpath.split("/")
            if len(full_subpath_parts) > 1:
                subpath_with_magic_keyword = (
                    "/".join(full_subpath_parts[:1]) + "/" + settings.all_subpaths_mw
                )
                if len(full_subpath_parts) > 2:
                    subpath_with_magic_keyword += "/" + "/".join(full_subpath_parts[2:])
                query_policies.append(
                    f"{space_name}:{subpath_with_magic_keyword}:{resource_type}:{str(is_active).lower()}"
                )

            if full_subpath == "/":
                full_subpath = ""
            else:
                full_subpath += "/"

        return query_policies

    def prepate_meta_doc(
        self, space_name: str, branch_name: str | None, subpath: str, meta: core.Meta
    ):
        resource_type = meta.__class__.__name__.lower()
        meta_doc_id = self.generate_doc_id(
            space_name, branch_name, "meta", meta.shortname, subpath
        )
        payload_doc_id = None
        if meta.payload and meta.payload.schema_shortname:
            payload_doc_id = self.generate_doc_id(
                space_name,
                branch_name,
                meta.payload.schema_shortname,
                meta.shortname,
                subpath,
            )
        meta_json = json.loads(meta.json(exclude_none=True))
        meta_json["query_policies"] = self.generate_query_policies(
            space_name,
            subpath,
            resource_type,
            meta.is_active,
            meta.owner_shortname,
            meta.owner_group_shortname,
        )
        meta_json["subpath"] = subpath
        meta_json["branch_name"] = branch_name
        meta_json["resource_type"] = resource_type
        meta_json["created_at"] = meta.created_at.timestamp()
        meta_json["updated_at"] = meta.updated_at.timestamp()
        meta_json["payload_doc_id"] = payload_doc_id

        return meta_doc_id, meta_json

    async def save_meta_doc(
        self, space_name: str, branch_name: str | None, subpath: str, meta: core.Meta
    ):
        meta_doc_id, meta_json = self.prepate_meta_doc(
            space_name, branch_name, subpath, meta
        )
        await self.save_doc(meta_doc_id, meta_json)
        return meta_doc_id, meta_json

    def prepare_payload_doc(
        self,
        space_name: str,
        branch_name: str | None,
        subpath: str,
        meta: core.Meta,
        payload: dict,
        resource_type: str = ResourceType.content,
    ):
        if meta.payload is None:
            print(
                f"Missing payload for {space_name}/{branch_name}/{subpath} of type {resource_type}"
            )
            return "", {}
        if meta.payload.body is None:
            print(
                f"Missing body for {space_name}/{branch_name}/{subpath} of type {resource_type}"
            )
            return "", {}
        if not isinstance(meta.payload.body, str):
            print("body should be type of string")
            return "", {}
        payload_shortname = meta.payload.body.split(".")[0]
        meta_doc_id = self.generate_doc_id(
            space_name, branch_name, "meta", payload_shortname, subpath
        )
        docid = self.generate_doc_id(
            space_name,
            branch_name,
            meta.payload.schema_shortname or "",
            payload_shortname,
            subpath,
        )

        payload["query_policies"] = self.generate_query_policies(
            space_name,
            subpath,
            resource_type,
            meta.is_active,
            meta.owner_shortname,
            meta.owner_group_shortname,
        )
        if not payload["query_policies"]:
            print(f"Warning: this entry `{space_name}/{subpath}/{meta.shortname}` can't be accessed")
        payload["subpath"] = subpath
        payload["branch_name"] = branch_name
        payload["resource_type"] = resource_type
        payload["shortname"] = payload_shortname
        payload["meta_doc_id"] = meta_doc_id

        return docid, payload

    async def save_payload_doc(
        self,
        space_name: str,
        branch_name: str | None,
        subpath: str,
        meta: core.Meta,
        payload: dict,
        resource_type: ResourceType = ResourceType.content,
    ):
        docid, payload = self.prepare_payload_doc(
            space_name, branch_name, subpath, meta, payload, resource_type
        )
        if docid == "":
            return
        await self.save_doc(docid, payload)

    async def get_payload_doc(self, doc_id: str, resource_type: ResourceType):
        resource_class = getattr(
            sys.modules["models.core"],
            camel_case(resource_type),
        )
        payload_redis_doc = await self.get_doc_by_id(
            doc_id
        )
        payload_doc_content = {}
        if not payload_redis_doc:
            return payload_doc_content

        not_payload_attr = RedisServices.SYS_ATTRIBUTES + list(
            resource_class.__fields__.keys()
        )
        for key, value in payload_redis_doc.items():
            if key not in not_payload_attr:
                payload_doc_content[key] = value
        return payload_doc_content

    async def save_lock_doc(
        self,
        space_name: str,
        branch_name: str | None,
        subpath: str,
        payload_shortname: str,
        owner_shortname: str,
        ttl: int,
    ):

        lock_doc_id = self.generate_doc_id(
            space_name, branch_name, "lock", payload_shortname, subpath
        )
        lock_data = await self.get_lock_doc(
            space_name, branch_name, subpath, payload_shortname
        )
        if not lock_data:
            payload = {
                "owner_shortname": owner_shortname,
                "lock_time": str(datetime.now().isoformat()),
            }
            result = await self.save_doc(lock_doc_id, payload, nx=True)
            if result is None:
                lock_payload = await self.get_lock_doc(
                    space_name, branch_name, subpath, payload_shortname
                )
                if lock_payload["owner_shortname"] != owner_shortname:
                    raise api.Exception(
                        status_code=status.HTTP_403_FORBIDDEN,
                        error=api.Error(
                            type="lock",
                            code=30,
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
        branch_name: str | None,
        subpath: str,
        payload_shortname: str,
    ):
        lock_doc_id = self.generate_doc_id(
            space_name, branch_name, "lock", payload_shortname, subpath
        )
        return await self.get_doc_by_id(lock_doc_id)

    async def delete_lock_doc(
        self,
        space_name: str,
        branch_name: str | None,
        subpath: str,
        payload_shortname: str,
    ):
        await self.delete_doc(
            space_name, branch_name, "lock", payload_shortname, subpath
        )

    async def is_entry_locked(
        self,
        space_name: str,
        branch_name: str | None,
        subpath: str,
        shortname: str,
        user_shortname: str,
    ):
        lock_payload = await self.get_lock_doc(
            space_name, branch_name, subpath, shortname
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
        await self.client.json().set(doc_id, path, payload, nx=nx)

    async def save_bulk(self, data: list, path: str = Path.root_path()):
        pipe = self.client.pipeline()
        for document in data:
            pipe.json().set(document["doc_id"], path, document["payload"])
        return await pipe.execute()

    async def get_count(self, space_name: str, branch_name: str, schema_shortname: str):
        ft_index = self.client.ft(f"{space_name}:{branch_name}:{schema_shortname}")

        try:
            info = await ft_index.info()
            return info["num_docs"]
        except Exception as e:
            logger.error(f"Error at redis_services.get_count: {e}")
            return 0

        # aggregate_request = AggregateRequest().group_by([], count_reducer().alias("counter"))
        # aggregate = await ft_index.aggregate(aggregate_request)
        # print("\n\n\n aggregate res: ", aggregate.rows, "\n\n")

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
    ):
        # Tries to get the index from the provided space
        try:
            ft_index = self.client.ft(f"{space_name}:{branch_name}:{schema_name}")
            await ft_index.info()
        except Exception as e:
            logger.error(f"Error at redis_services.search: {e}")
            return {"data": [], "total": 0}

        search_query = Query(
            query_string=self.prepare_query_string(
                search,
                filters,
                exact_subpath
            )
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
            search_res = await ft_index.search(query=search_query)
            return {"data": search_res.docs, "total": search_res.total}
        except:
            return {}

    async def aggregate(
        self,
        space_name: str,
        branch_name: str | None,
        search: str,
        filters: dict[str, str | list],
        group_by: dict[str, list],
        max: int,
        exact_subpath: bool = False,
        sort_type: SortType = SortType.ascending,
        sort_by: str | None = None,
        schema_name: str = "meta",
        load: list = []
    ) -> list:
        # Tries to get the index from the provided space
        try:
            ft_index = self.client.ft(f"{space_name}:{branch_name}:{schema_name}")
            await ft_index.info()
        except:
            return []

        
        aggr_request = aggregation.AggregateRequest(
            self.prepare_query_string(
                search,
                filters,
                exact_subpath
            )
        )
        for group_name, reducers in group_by.items():
            aggr_request.group_by(group_name, *reducers)
            

        if sort_by:
            aggr_request.sort_by(
                aggregation.Desc(sort_by) if sort_type == SortType.ascending else aggregation.Asc(sort_by),
                max=max
            )

        if load:
            aggr_request.load(*load)


        try:
            aggr_res = await ft_index.aggregate(aggr_request)
            return aggr_res.rows
        except:
            return []

    def prepare_query_string(
        self,
        search: str,
        filters: dict[str, str | list],
        exact_subpath: bool
    ):
        query_string = search

        redis_escape_chars = str.maketrans(
            {":": r"\:", "/": r"\/", "-": r"\-", " ": r"\ "}
        )
        for item in filters.items():
            if item[0] in ["tags", "query_policies"] and item[1]:
                query_string += (
                    " @"
                    + item[0]
                    + ":{"
                    + "|".join(item[1]).translate(redis_escape_chars)
                    + "}"
                )
            elif item[0] == "created_at" and item[1]:
                query_string += f" @{item[0]}:{item[1]}"
            elif item[0] == "subpath" and exact_subpath:
                search_value = ""
                for subpath in item[1]:
                    # search_value += "|" + subpath.strip("/").translate(redis_escape_chars)
                    # search_value += "|" + f"/{subpath}".replace("//", "/").translate(redis_escape_chars)
                    search_value = subpath

                exact_subpath_value = search_value.strip('|').replace('/', '\\/')
                query_string += f" @exact_subpath:{{{exact_subpath_value}}}"
                # print(query_string)
            elif item[0] == "subpath" and item[1][0] == "/":
                pass
            elif item[1]:
                query_string += " @" + item[0] + ":(" + "|".join(item[1]) + ")"

        return query_string or "*"


    async def get_doc_by_id(self, doc_id: str) -> dict:
        try:
            return await self.client.json().get(name=doc_id)
        except Exception as e:
            logger.warning(f"Error at redis_services.get_doc_by_id: {e}")
            return {}


    async def get_docs_by_ids(self, docs_ids: list[str]) -> list:
        try:
            return await self.client.json().mget(docs_ids, "$")
        except Exception as e:
            logger.warning(f"Error at redis_services.get_docs_by_ids: {e}")
            return []

    async def get_content_by_id(self, doc_id: str) -> Any:
        try:
            return await self.client.get(doc_id)
        except Exception as e:
            logger.warning(f"Error at redis_services.get_content_by_id: {e}")
            return ""

    async def delete_doc(
        self, space_name, branch_name, schema_shortname, shortname, subpath
    ):
        docid = self.generate_doc_id(
            space_name, branch_name, schema_shortname, shortname, subpath
        )
        try:
            await self.client.json().delete(key=docid)
        except Exception as e:
            logger.warning(f"Error at redis_services.delete_doc: {e}")


    async def move_payload_doc(
        self,
        space_name,
        branch_name,
        schema_shortname,
        src_shortname,
        src_subpath,
        dest_shortname,
        dest_subpath,
    ):
        docid = self.generate_doc_id(
            space_name, branch_name, schema_shortname, src_shortname, src_subpath
        )

        try:
            doc_content = await self.get_doc_by_id(docid)
            await self.delete_doc(
                space_name, branch_name, schema_shortname, src_shortname, src_subpath
            )

            new_docid = self.generate_doc_id(
                space_name, branch_name, schema_shortname, dest_shortname, dest_subpath
            )
            await self.save_doc(new_docid, doc_content)

        except Exception as e:
            logger.warning(f"Error at redis_services.move_payload_doc: {e}")

    async def move_meta_doc(
        self, space_name, branch_name, src_shortname, src_subpath, dest_subpath, meta
    ):
        try:
            await self.delete_doc(
                space_name, branch_name, "meta", src_shortname, src_subpath
            )
            await self.save_meta_doc(space_name, branch_name, dest_subpath, meta)
        except Exception as e:
            logger.warning(f"Error at redis_services.move_meta_doc: {e}")


    async def get_keys(self, pattern: str = "*") -> list:
        try:
            return await self.client.keys(pattern)
        except Exception as e:
            logger.warning(f"Error at redis_services.get_keys: {e}")
            return []

    async def del_keys(self, keys: list):
        try:
            return await self.client.delete(*keys)
        except Exception as e:
            logger.warning(f"Error at redis_services.def_keys {keys}: {e}")
            return False


    async def get(self, key):
        return await self.client.get(key)

    async def getdel(self, key):
        return await self.client.getdel(key)

    async def set(self, key, value, ex=None, nx: bool = False):
        return await self.client.set(key, value, ex=ex, nx=nx)

    async def set_ttl(self, key: str, ttl: int):
        return await self.client.expire(key, ttl)

    async def drop_index(self, name: str, delete_docs: bool = False):
        try:
            ft_index = self.client.ft(name)
            await ft_index.dropindex(delete_docs)
            return True
        except :
            return False

    async def list_indices(self):
        return await self.client.ft().execute_command("FT._LIST")
