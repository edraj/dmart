from copy import copy
import datetime
import json
import re
from typing import Any

import api
from fastapi import FastAPI, status
from backend.utils.internal_error_code import InternalErrorCode
from db.base_db import BaseDB
import manticoresearch
from fastapi.logger import logger
from models.core import EntityDTO, Meta, Space
from models.enums import LockAction, ResourceType, SortType
from utils.helpers import delete_none, resolve_schema_references
from utils.settings import settings
from manticoresearch.model.bulk_response import BulkResponse

class ManticoreDB(BaseDB):
    config = manticoresearch.Configuration(
        host=f"{settings.operational_db_host}:{settings.operational_db_port}",
        username=settings.operational_db_user,
        password=settings.operational_db_password,
    )
    client = manticoresearch.ApiClient(config)
    indexApi = manticoresearch.IndexApi(client)
    searchApi = manticoresearch.SearchApi(client)
    utilsApi = manticoresearch.UtilsApi(client)

    META_SCHEMA = {
        "document_id": "string",
        "uuid": "string",
        "shortname": "string",
        "slug": "string",
        "subpath": "string",
        "exact_subpath": "string",
        "resource_type": "string",
        "displayname": "json",
        # "displayname_ar": "string",
        # "displayname_kd": "string",
        "description": "json",
        # "description_ar": "string",
        # "description_kd": "string",
        "is_active": "bool",
        "payload_content_type": "string",
        "schema_shortname": "string",
        "created_at": "timestamp",
        "updated_at": "timestamp",
        "view_acl": "text",
        "tags": "json",
        "query_policies": "json",
        "owner_shortname": "string",
        # User fields
        "msisdn": "string",
        "email": "string",
        # Ticket fields
        "state": "string",
        "is_open": "bool",
        "workflow_shortname": "string",
        "collaborators": "json",
        # "collaborators_delivered_by": "string",
        # "collaborators_processed_by": "string",
        "resolution_reason": "string",
        # Notification fields
        "type": "string",
        "is_read": "string",
        "priority": "string",
        "reporter": "json",
        # "reporter_type": "string",
        # "reporter_name": "string",
        # "reporter_channel": "string",
        # "reporter_distributor": "string",
        # "reporter_governorate": "string",
        # "reporter_msisdn": "string",
        "payload_string": "string",
        "document_data": "json",
    }

    SCHEMA_DATA_TYPES_MAPPER = {
        "string": "string",
        "boolean": "bool",
        "integer": "int",
        "number": "int",
        "array": "text",
        "text": "text",
    }

    def mc_command(self, command: str) -> dict[str, Any] | None:
        try:
            result = self.utilsApi.sql(command)
            if(
                not isinstance(result, list) or 
                len(result) == 0 or 
                not isinstance(result[0], dict)
            ):
                return None
            
            if result[0]['error'] != '':
                raise Exception(result[0]['error'])
            
            return result[0]
        except Exception as e:
            logger.error(f"Error at ManticoreDB.mc_command: {e}")
            return None
            
    
    async def create_key_value_pairs_index(self):
        if self.is_index_exist("key_value_pairs"):
            return
        
        await self.create_index(
            "key_value_pairs",
            {
                "key": "string",
                "value": "string"
            }
        )
        
    def is_index_exist(self, name: str)-> bool:
        res = self.mc_command(f"show tables like '{name}'")
        if res is not None and res['total'] > 0:
            return True
        
        return False

    async def create_index(self, name: str, fields: dict[str, str], **kwargs) -> bool:
        name = name.replace(":", "__")
        if self.is_index_exist(name):
            await self.drop_index(name, False)
        
        try:
            sql_str = f"CREATE TABLE {name}("
            for name, value in fields.items():
                sql_str += f"{name} {value},"
            
            sql_str = sql_str.strip(",")
            sql_str += ")"
            return bool(self.mc_command(sql_str))
        except Exception as e:
            logger.error(f"Error at ManticoreDB.create_index: {e.args}")
            return False
            
    def get_index_fields_from_json_schema_property(
        self, 
        key_chain: str, 
        property: Any, 
        db_schema_definition: dict[str, str]
    ) -> dict[str, str]:
        """
        takes a property of the json schema definition, and returns the db schema index
        """
        # pp(key_chain, property, db_schema_definition)
        if not isinstance(property, dict) or key_chain.endswith("_"):
            return db_schema_definition

        if "type" in property and property["type"] != "object":
            if property["type"] in ["null", "boolean"] or not isinstance(
                property["type"], str
            ):
                return db_schema_definition

            # property_name = key_chain.replace(".", "_")
            # sortable = True

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
                    db_schema_definition[f"{key_chain}_{property_key}"] = "text"
                return db_schema_definition

            # if property["type"] == "array":
            #     key_chain += ".*"

            db_schema_definition[key_chain] = self.SCHEMA_DATA_TYPES_MAPPER[property['type']]
            return db_schema_definition

        if "oneOf" in property:
            for item in property["oneOf"]:
                db_schema_definition = self.get_index_fields_from_json_schema_property(
                    key_chain, item, db_schema_definition
                )
            return db_schema_definition

        if "properties" not in property:
            return db_schema_definition

        for property_key, property_value in property["properties"].items():
            db_schema_definition = self.get_index_fields_from_json_schema_property(
                f"{key_chain}_{property_key}", property_value, db_schema_definition
            )

        return db_schema_definition

    async def create_application_indexes(
        self, 
        for_space: str | None = None, 
        for_schemas: list | None = None, 
        for_custom_indices: bool = True, 
        del_docs: bool = True
    ) -> None:
        
        spaces = await self.find_by_id("spaces")
        branch_name = 'master'
        
        folder_rendering_schema = None
        
        await self.create_custom_indices()
        for space_name in spaces:
            if (
                for_space and for_space != space_name
            ):
                continue

            await self.create_index(
                f"{space_name}:{branch_name}:meta", self.META_SCHEMA
            )

            # CREATE DB INDEX FOR EACH SCHEMA DEFINITION INSIDE THE SPACE
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
                # GENERATE DB INDEX DEFINITION BY MAPPING SCHEMA PROPERTIES TO DB INDEX FIELDS
                schema_content = json.loads(schema_path.read_text())
                schema_content = resolve_schema_references(schema_content)
                db_schema_definition: dict[str, str] = copy(self.META_SCHEMA)
                if "properties" in schema_content:
                    for key, property in schema_content["properties"].items():
                        generated_schema_fields = self.get_index_fields_from_json_schema_property(
                            key, property, {}
                        )
                        db_schema_definition.update(generated_schema_fields)

                elif "oneOf" in schema_content:
                    for item in schema_content["oneOf"]:
                        for key, property in item["properties"].items():
                            generated_schema_fields = self.get_index_fields_from_json_schema_property(
                                key, property, {}
                            )
                            db_schema_definition.update(generated_schema_fields)

                if db_schema_definition:
                    db_schema_definition["meta_doc_id"] = "string"
                    
                    if schema_shortname == "folder_rendering":
                        folder_rendering_schema = db_schema_definition

                    await self.create_index(
                        f"{space_name}:{branch_name}:{schema_shortname}",
                        db_schema_definition
                    )

        if folder_rendering_schema is None:
            return
        
        for space_name in spaces:
            if (
                for_space and for_space != space_name
            ):
                continue

            await self.create_index(
                f"{space_name}:{branch_name}:folder_rendering", folder_rendering_schema
            )

    
    def generate_db_index_from_class(
        self, class_ref: type[Meta], exclude_from_index: list
    ) -> dict[str, str]:
        class_types_to_db_column_type_map = {
            "str": "string",
            "bool": "bool",
            "UUID": "string",
            "list": "json",
            "datetime": "timestamp",
            "set": "json",
            "dict": "json",
        }

        db_schema: dict[str, str] = {}
        for field_name, model_field in class_ref.model_fields.items():
            if field_name in exclude_from_index:
                continue

            mapper_key = None
            for allowed_type in list(class_types_to_db_column_type_map.keys()):
                if str(model_field.annotation).startswith(allowed_type):
                    mapper_key = allowed_type
                    break
            if not mapper_key:
                continue
            db_schema[field_name] = class_types_to_db_column_type_map[mapper_key]

        return db_schema

    async def create_custom_indices(self, for_space: str | None = None) -> None:
        # redis_schemas: dict[str, list] = {}
        # branch_name = 'master'
        for i, index in enumerate(self.SYS_INDEXES):
            if (
                for_space
                and index["space"] != for_space
                or not isinstance(index["exclude_from_index"], list)
            ):
                continue

            # exclude_from_index: list = index["exclude_from_index"]

#
            # redis_schemas.setdefault(f"{index['space']}:{index['branch']}", [])
            # self.redis_indices.setdefault(
            #     f"{index['space']}:{index['branch']}:meta", {}
            # )

            generated_schema_fields = self.generate_db_index_from_class(
                index["class"], index["exclude_from_index"]
            )

            self.META_SCHEMA.update(generated_schema_fields)

            # await self.create_index(f"{index['space']}:{branch_name}:meta", generated_schema_fields)

            # redis_schemas[f"{index['space']}:{index['branch']}"] = (
            #     self.append_unique_index_fields(
            #         generated_schema_fields,
            #         redis_schemas[f"{index['space']}:{index['branch']}"],
            #     )
            # )

        # for space_branch, redis_schema in redis_schemas.items():
        #     redis_schema = self.append_unique_index_fields(
        #         tuple(redis_schema),
        #         list(self.META_SCHEMA),
        #     )
        #     await self.create_index(
        #         f"{space_branch}",
        #         "meta",
        #         tuple(redis_schema),
        #     )
    
    async def flush_all(self) -> None:
        tables: dict[str, Any] | None = self.mc_command('SHOW TABLES') 
        if tables is None:
            return
        
        for table in tables.get('data', []):
            await self.drop_index(table['Index'], True)
                    
    async def list_indexes(self) -> set[str]:
        tables = self.mc_command('SHOW TABLES') 
        if tables is None:
            return set()
        
        return set([item['Index'] for item in tables['data']])


    async def drop_index(self, name: str, delete_docs: bool) -> bool:
        return bool(self.mc_command(f"DROP TABLE {name}"))
        
    
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
        return_fields: list = []
    ) -> tuple[int, list[dict[str, Any]]]:
        sql_str = "SELECT "
        sql_str += "*" if len(return_fields) == 0 else ",".join(return_fields)

        if len(highlight_fields) != 0:
            sql_str += ", HIGHLIGHT({}, %s)" % ",".join(highlight_fields)

        sql_str += f" FROM {space_name}__{branch_name}__{schema_name}"

        if search:
            sql_str += f" WHERE {search}"

        where_filters = []
        if len(filters.keys()) != 0:
            sql_str += " AND " if search else " WHERE "
            for key, value in filters.items():
                if isinstance(value, list):
                    where_filters.append(f"{key} IN ({', '.join(map(str, value))})")
                elif isinstance(value, str):
                    where_filters.append(f"{key}='{value}'")
                else:
                    where_filters.append(f"{key}={value}")

            sql_str += " AND ".join(where_filters)

        if sort_by:
            sql_str += f" ORDER BY {sort_by} {'asc' if sort_type == SortType.ascending else 'desc'}"

        sql_str += f" LIMIT {limit} OFFSET {offset}"

        result = self.mc_command(sql_str)

        return result["total"], result["data"]

    async def aggregate(
        self,
        space_name: str,
        filters: dict[str, str | list | None],
        group_by: list[str],
        reducers: list[Any],
        search: str | None = None,
        limit: int = 10,
        branch_name: str = settings.default_branch,
        exact_subpath: bool = False,
        sort_type: SortType = SortType.ascending,
        sort_by: str | None = None,
        schema_name: str = "meta",
        load: list = [],
    ) -> list[Any]:
        sql_str = "SELECT "
        if len(reducers) == 0:
            sql_str += "*"
        else:
            for reducer_index in range(len(reducers)):
                for operation, fields in reducers[reducer_index].items():
                    sql_str += f'{operation}({",".join(fields)})'
                    if reducer_index < len(reducers) - 1:
                        sql_str += ", "

        sql_str += f" FROM {space_name}__{branch_name}__{schema_name}"

        if search:
            sql_str += f" WHERE {search})"

        where_clauses = []
        for key, value in filters.items():
            sql_str += " AND " if "WHERE" in sql_str else "WHERE"
            if isinstance(value, list):
                where_clauses.append(f"{key} IN ({', '.join(map(str, value))})")
            if isinstance(value, str):
                where_clauses.append(f"{key}='{value}'")
            elif value is not None:
                where_clauses.append(f"{key} = '{value}'")

        sql_str += " AND ".join(where_clauses)

        sql_str += " GROUP BY "
        group_by = ", ".join(group_by)
        sql_str += group_by

        if sort_by:
            sql_str += f" ORDER BY {sort_by} {sort_type}"

        sql_str += f" LIMIT {limit}"

        result = self.mc_command(sql_str)

        return result["data"]

    async def get_count(
        self,
        space_name: str,
        schema_shortname: str,
        branch_name: str = settings.default_branch,
    ) -> int:
        result = self.mc_command(
            f"SELECT COUNT(*) as c FROM {space_name}__{branch_name}__{schema_shortname}"
        )
        return result["data"][0]["c"]

    async def free_search(
        self, index_name: str, search_str: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        sql_str = f"SELECT * FROM {index_name}"
        if search_str:
            sql_str += f" WHERE {search_str}"
        sql_str += f" LIMIT {limit} OFFSET {offset}"

        result = self.mc_command(sql_str)
        return result["data"]

    async def dto_doc_id(self, dto: EntityDTO) -> str:
        if dto.schema_shortname == "meta_schema":
            return f"{dto.space_name}__{dto.branch_name}__meta"
        return f"{dto.space_name}__{dto.branch_name}__{dto.schema_shortname}"

    async def find_key(self, key: str) -> str | None:
        res = self.mc_command(f"select * from key_value_pairs where key = '{key}' limit 1")
        if res is None or res['total'] == 0:
            return None
        
        return res['data'][0]['value']
    
    async def set_key(self, key: str, value: str, ex=None, nx: bool = False) -> bool:
        await self.create_key_value_pairs_index()
        
        statement = {
            "index": "key_value_pairs",
            "doc": {
                "key": key, "value": value
            }
        }
        find_res = self.mc_command(f"select * from key_value_pairs where key = '{key}' limit 1")
        if find_res is None or find_res['total'] == 0:
            res = self.indexApi.insert(statement)
        else:
            statement["id"] = find_res['data'][0]['id']
            res = self.indexApi.replace(statement)
            
        
        return bool(res)
    
    def get_index_name_from_dto(self, dto: EntityDTO) -> str:
        return f"{dto.space_name}__{dto.branch_name}__{dto.schema_shortname}"
    
    def get_meta_index_name_from_dto(self, dto: EntityDTO) -> str:
        return f"{dto.space_name}__{dto.branch_name}__meta"
    
    
    async def find(self, dto: EntityDTO) -> None | dict[str, Any]:
        
        
        meta_index_name = self.get_meta_index_name_from_dto(dto)
        sql_str = f"SELECT * FROM {meta_index_name}"
        sql_str += f" WHERE shortname='{dto.shortname}' AND resource_type='{dto.resource_type}'"

        result = self.mc_command(sql_str)
        if not result:
            return None
        record_data = {'meta': {}, 'payload': {}}
        record_data['meta'] = result["data"][0] if result["total"] > 0 else {}
        
        payload_index_name = self.get_index_name_from_dto(dto)
        sql_str = f"SELECT * FROM {payload_index_name}"
        sql_str += f" WHERE shortname='{dto.shortname}' AND resource_type='{dto.resource_type}'"
        result = self.mc_command(sql_str)
        if not result:
            return record_data
        record_data['payload'] = result["data"][0] if result["total"] > 0 else {}
        
        return record_data

    def get_index_name_from_doc_id(self, doc_id: str) -> str:
        if ":" not in doc_id:
            return "key_value_pairs"
        
        doc_id_parts = doc_id.split(":")
        
        if len(doc_id_parts) < 3:
            raise Exception(f"Invalid document id, {doc_id}")
        
        schema_name = doc_id_parts[2]
        if schema_name == "meta_schema":
            schema_name = "meta"
        return f"{doc_id_parts[0]}__{doc_id_parts[1]}__{schema_name}"

    async def find_by_id(self, id: str) -> dict[str, Any]:
        try:
            index_name: str = self.get_index_name_from_doc_id(id)
            identifier = "document_id"
            if index_name == "key_value_pairs":
                identifier = "key"
            find_res = self.mc_command(
                f"select * from {index_name} where {identifier} = '{id}' limit 1"
            )

            if not find_res or find_res["total"] == 0 or len(find_res["data"]) == 0:
                return {}

            if isinstance(find_res["data"][0]["value"], dict):
                return find_res["data"][0]["value"]
            elif isinstance(find_res["data"][0]["value"], str):
                return json.loads(find_res["data"][0]["value"])
            else:
                raise Exception(f"Invalid data type {type(find_res['data'][0])}")
        except Exception as e:
            logger.error(f"Error at ManticoreDB.find_by_id: {e.args}")
            return {}
    
    async def list_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        return []
    

    async def find_payload_data_by_id(
        self, id: str, resource_type: ResourceType
    ) -> dict[str, Any]:
        return {}
    
    async def replace(self, document_id: str, db_id: int, doc: dict[str, Any]) -> bool:
        try:
            index = self.get_index_name_from_doc_id(document_id)
            res = self.indexApi.replace({
                "index": index,
                "id": db_id,
                "doc": doc
            })
            return bool(res)
        except Exception as e:
            logger.error(f"Error at ManticoreDB.replace: {e}")
            return False

    async def save_at_id(self, id: str, doc: dict[str, Any] = {}) -> bool:
        if ":" not in id:
            await self.set_key(id, json.dumps(doc))
            
        try:
            doc['document_id'] = id
            index = self.get_index_name_from_doc_id(id)
            self.indexApi.insert({
                "index": index,
                "doc": doc
            })
            return True
        except Exception as e:
            logger.error(f"Error at ManticoreDB.save_at_id: {e}")
            return False

    async def save_bulk(self, index: str, docs: list[dict[str, Any]]) -> int:
        if len(docs) == 0:
            return 0
        try:

            docs = [{"insert": {"index": index, "doc": doc}} for doc in docs]
            
            res: BulkResponse = self.indexApi.bulk('\n'.join(map(json.dumps,docs))) # type: ignore
            
            if res.errors is not False:
                raise Exception(res.errors)
            
            if not isinstance(res.items, list) or not isinstance(res.items[0], dict):
                raise Exception("Invalid response " + str(res.items))
            
            
            return res.items[0]['bulk']['created']
        except Exception as e:
            logger.error(f"Error at ManticoreDB.save_bulk. {index = }. {len(docs)}. {docs[0] = }: {e}")
            return 0

    async def prepare_meta_doc(
        self, space_name: str, branch_name: str | None, subpath: str, meta: Meta
    ) -> tuple[str, dict[str, Any]]:
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
        meta_json: dict[str, Any] = json.loads(meta.model_dump_json(exclude_none=True))
        meta_json["query_policies"] = self.generate_query_policies(
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
        meta_json["branch_name"] = branch_name
        meta_json["resource_type"] = resource_type
        meta_json["created_at"] = meta.created_at.timestamp()
        meta_json["updated_at"] = meta.updated_at.timestamp()
        meta_json["payload_doc_id"] = payload_doc_id
        
        meta_json = self.filter_unindexed_attributes(meta_json, meta_doc_id)
        
        # Encode list to json string
        meta_json = {key: json.dumps(value) if isinstance(value, list) else value for key, value in meta_json.items()}

        return meta_doc_id, meta_json

    def filter_unindexed_attributes(self, doc: dict[str, Any], id: str) -> dict[str, Any]:
        # pp(before_filter__doc=doc, id=id)
        filtered_doc = {
            'document_data': doc,
        }

        index_name = self.get_index_name_from_doc_id(id)
        res = self.mc_command(f"describe {index_name}")
        if not res:
            return filtered_doc
        
        index_schema = res['data']
        index_fields = {field['Field'] for field in index_schema}
        # pp(index_schema=index_schema)
        filtered_doc = {field: doc[field] for field in doc if field in index_fields}
        # pp(after_filter__doc=doc, id=id)
        return delete_none(filtered_doc)

    async def prepare_payload_doc(
        self,
        dto: EntityDTO,
        meta: Meta,
        payload: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        if meta.payload is None:
            raise Exception(
                f"Missing payload for {dto.space_name}/{dto.branch_name}/{dto.subpath} of type {dto.resource_type}"
            )
        if meta.payload.body is None:
            raise Exception(
                f"Missing body for {dto.space_name}/{dto.branch_name}/{dto.subpath} of type {dto.resource_type}"
            )
        if not isinstance(meta.payload.body, str):
            raise Exception("body should be type of string")
        payload_shortname = meta.payload.body.split(".")[0]
        meta_doc_id = self.generate_doc_id(
            dto.space_name, dto.branch_name, "meta", payload_shortname, dto.subpath
        )
        docid: str = self.generate_doc_id(
            dto.space_name,
            dto.branch_name,
            meta.payload.schema_shortname or "",
            payload_shortname,
            dto.subpath,
        )

        payload["query_policies"] = self.generate_query_policies(
            dto.space_name,
            dto.subpath,
            dto.resource_type or ResourceType.content,
            meta.is_active,
            meta.owner_shortname,
            meta.owner_group_shortname,
            meta.shortname,
        )
        if not payload["query_policies"]:
            print(
                f"Warning: this entry `{dto.space_name}/{dto.subpath}/{meta.shortname}` can't be accessed"
            )
        payload["subpath"] = dto.subpath
        payload["branch_name"] = dto.branch_name
        payload["resource_type"] = dto.resource_type
        payload["shortname"] = payload_shortname
        payload["meta_doc_id"] = meta_doc_id

        payload = self.filter_unindexed_attributes(payload, docid)

        # Encode list to json string
        payload = {
            key: json.dumps(value) if isinstance(value, list) else value
            for key, value in payload.items()
        }

        return docid, payload

    async def delete(self, dto: EntityDTO) -> bool:
        id = self.generate_doc_id(dto)
        idx_name = self.get_index_name_from_doc_id(id)
        command = f"DELETE FROM key_value_pairs WHERE key = '{id}');"
        try:
            self.utilsApi.sql(command)
        except Exception as e:
            logger.error(f"Error at ManticoreDB.delete: {e.args}")
            return False 
        return True

    async def delete_keys(self, keys: list[str]) -> bool: # return error !
        for key in range(list):
            try:
                sql_str = "delete from key_value_pairs where key = '{key}'" 
                self.utilsApi.sql(sql_str)
            except:
                return False
        return True
 

    async def delete_doc_by_id(self, id: str) -> bool:
        command = f"DELETE FROM key_value_pairs WHERE id = {id}"
        try:
            self.utilsApi.sql(command)
        except Exception as e:
            logger.error(f"Error at ManticoreDB.delete_doc_by_id: {e.args}")
            return False 
        return True

    async def delete_lock_doc(self, dto: EntityDTO) -> None:

        docid = self.generate_doc_id(
            dto.space_name, dto.branch_name, "lock", dto.shortname, dto.subpath
        )

        try:
            await self.delete(key=docid)
        except Exception as e:
            logger.warning(f"Error at ManticoreDb.delete_doc: {e}")


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
        src_meta_doc_id = self.generate_doc_id(
            space_name, branch_name, "meta", src_shortname, src_subpath
        )

        dest_shortname = dest_shortname or src_shortname
        dest_subpath = dest_subpath or src_subpath
        
        dest_meta_doc_id = self.generate_doc_id(
            space_name, branch_name, "meta", dest_shortname, dest_subpath
        )
        
        # Move meta document
        meta_doc = await self.find_by_id(src_meta_doc_id)
        if not meta_doc:
            return False
        meta_doc["subpath"] = dest_subpath
        meta_doc["shortname"] = dest_shortname
        meta_doc["branch_name"] = branch_name
        await self.save_at_id(dest_meta_doc_id, meta_doc)
        await self.delete_doc_by_id(src_meta_doc_id)
        
        # Move payload document
        if meta.payload and meta.payload.schema_shortname:
            src_payload_doc_id = self.generate_doc_id(
                space_name, branch_name, meta.payload.schema_shortname, src_shortname, src_subpath
            )
            dest_payload_doc_id = self.generate_doc_id(
                space_name, branch_name, meta.payload.schema_shortname, dest_shortname, dest_subpath
            )
            payload_doc = await self.find_by_id(src_payload_doc_id)
            if not payload_doc:
                return False
            payload_doc["subpath"] = dest_subpath
            payload_doc["shortname"] = dest_shortname
            payload_doc["branch_name"] = branch_name
            await self.save_at_id(dest_payload_doc_id, payload_doc)
            await self.delete_doc_by_id(src_payload_doc_id)
        
        return True

 
    async def save_lock_doc(
        self, dto: EntityDTO, owner_shortname: str, ttl: int = settings.lock_period
    ) -> LockAction | None:
        lock_doc_id = self.generate_doc_id(
            dto.space_name, dto.branch_name, "lock", dto.payload_shortname, dto.subpath
        )
        lock_data = await self.get_lock_doc(
            dto.space_name, dto.branch_name, dto.subpath, dto.payload_shortname
        )
        if not lock_data:
            payload = {
                "owner_shortname": owner_shortname,
                "lock_time": str(datetime.now().isoformat()),
            }

            # alternaticr
            result = await self.save_at_id(lock_doc_id, payload, nx=True)
            if result is None:
                lock_payload = await self.get_lock_doc(
                    dto.space_name, dto.branch_name, dto.subpath, dto.payload_shortname
                )
                if lock_payload["owner_shortname"] != owner_shortname:
                    raise api.Exception(
                        status_code=FastAPI.HTTP_403_FORBIDDEN,
                        error=FastAPI.Error(
                            type="lock",
                            code=InternalErrorCode.LOCKED_ENTRY,
                            message=f"Entry is already locked by {lock_payload['owner_shortname']}",
                        ),
                    )
            lock_type = LockAction.lock
        else:
            lock_type = LockAction.extend
        return lock_type


    async def get_lock_doc(
        self,
        space_name: str,
        branch_name: str | None,
        subpath: str,
        payload_shortname: str,
    ) -> dict[str, Any]:
        lock_doc_id = self.generate_doc_id(
            space_name, branch_name, "lock", payload_shortname, subpath
        )
        return await self.get_doc_by_id(lock_doc_id)


    async def is_locked_by_other_user(
        self, dto: EntityDTO
    ) -> bool:
        try:
            lock_payload = await self.get_lock_doc(
                dto.space_name, 
                dto.branch_name, 
                dto.subpath, 
                dto.shortname
            )
            if lock_payload:
                if dto.user_shortname:
                    return bool(lock_payload["owner_shortname"] != dto.user_shortname)
                else:
                    return True
            return False

        except Exception as e:
            logger.error(f"Error at BaseDB.is_locked_by_other: {e.args}")
            return False
 

    async def delete_lock_doc(self, dto: EntityDTO) -> None:

        docid = self.generate_doc_id(
            dto.space_name, dto.branch_name, "lock", dto.shortname, dto.subpath
        )

        try:
            await self.delete(key=docid)
        except Exception as e:
            logger.warning(f"Error at ManticoreDB.delete_lock_doc: {e}")


 