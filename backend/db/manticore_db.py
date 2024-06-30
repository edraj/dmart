from copy import copy
from datetime import datetime
import json
import re
from typing import Any
from db.base_db import BaseDB
import manticoresearch # type: ignore
from fastapi.logger import logger
from models.core import EntityDTO, Meta
from models.enums import LockAction, ResourceType, SortType
from utils.helpers import delete_empty_strings, delete_none, resolve_schema_references
from utils.settings import settings
from manticoresearch.model.bulk_response import BulkResponse  # type: ignore
import models.api as api
from fastapi import status


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
        "branch_name": "string",
        "exact_subpath": "string",
        "resource_type": "string",
        "displayname": "json",
        # "displayname_ar": "string",
        # "displayname_kd": "string",
        "description": "json",
        # "description_ar": "string",
        # "description_kd": "string",
        "is_active": "bool",
        "payload": "json",
        "payload_content_type": "string",
        "schema_shortname": "string",
        "created_at": "timestamp",
        "updated_at": "timestamp",
        "acl": "text",
        "view_acl": "text",
        "tags": "text",
        "query_policies": "text",
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
        "payload_doc_id": "string",
        "meta_doc_id": "string",
        "values_string": "text",
        "payload_string": "string",
        # "document_data": "text",
    }

    SCHEMA_DATA_TYPES_MAPPER = {
        "string": "string",
        "boolean": "bool",
        "integer": "int",
        "number": "float",
        "array": "text",
        "text": "text",
        "object": "json",
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
            logger.error(f"Error at ManticoreDB.mc_command: {command}. Error: {e}")
            return None
            
    
    async def create_key_value_pairs_index(self):
        if self.is_index_exist("key_value_pairs"):
            return
        
        await self.create_index(
            "key_value_pairs",
            {
                "key": "string",
                "value": "string",
                "ex": "int",
                "created_at": "timestamp"
            }, del_docs=True
        )
        
    def is_index_exist(self, name: str)-> bool:
        res = self.mc_command(f"show tables like '{name}'")
        if res is not None and res['total'] > 0:
            return True
        
        return False

    async def create_index(self, name: str, fields: dict[str, str], **kwargs) -> bool:
        name = name.replace(":", "__")
        if ("del_docs" in kwargs and kwargs["del_docs"] is True) and self.is_index_exist(name):
            await self.drop_index(name, False)
        
        try:
            sql_str = f"CREATE TABLE if not exists  {name}("
            for key, value in fields.items():
                sql_str += f"{key} {value},"
            
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
        if not isinstance(property, dict) or key_chain.endswith("_"):
            return db_schema_definition

        if "type" in property:
            if property["type"] == "null" or not isinstance(
                property["type"], str
            ):
                return db_schema_definition

            # property_name = key_chain.replace(".", "_")
            # sortable = True

            # INDEX ARRAY OF OBJECTS AS A JSON COLUMN
            # if (
            #     property["type"] == "array"
            #     and property.get("items", {}).get("type", None) == "object"
            #     and "properties" in property["items"]
            # ):
            #     for property_key, property_value in property["items"][
            #         "properties"
            #     ].items():
            #         if property_value["type"] != "string":
            #             continue
            #         db_schema_definition[f"{key_chain}_{property_key}"] = "text"
            #     return db_schema_definition

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
                f"{space_name}:{branch_name}:meta", self.META_SCHEMA, del_docs=del_docs
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
                        db_schema_definition,
                        del_docs=del_docs
                    )

        if folder_rendering_schema is None:
            return
        
        for space_name in spaces:
            if (
                for_space and for_space != space_name
            ):
                continue

            await self.create_index(
                f"{space_name}:{branch_name}:folder_rendering", folder_rendering_schema, del_docs=del_docs
            )

    
    def generate_db_index_from_class(
        self, class_ref: type[Meta], exclude_from_index: list
    ) -> dict[str, str]:
        class_types_to_db_column_type_map = {
            "dict": "json",
            "list": "text",
            "enum": "string",
            "set": "text",
            "str": "string",
            "bool": "bool",
            "UUID": "string",
            "datetime": "timestamp",
        }

        db_schema: dict[str, str] = {}
        for field_name, model_field in class_ref.model_fields.items():
            # Index everything, create a column for all the attributes
            # if field_name in exclude_from_index:
            #     continue

            mapper_key = None
            
            for allowed_type in list(class_types_to_db_column_type_map.keys()):
                if allowed_type in str(model_field.annotation):
                    mapper_key = allowed_type
                    break

            if not mapper_key:
                continue
            
            db_schema[field_name] = class_types_to_db_column_type_map[mapper_key]

        return db_schema

    async def create_custom_indices(self, for_space: str | None = None) -> None:
        # redis_schemas: dict[str, list] = {}
        # branch_name = 'master'
        await self.create_lock_indexes()
        for i, index in enumerate(self.SYS_INDEXES):
            if (
                for_space
                and index["space"] != for_space
            ):
                continue

            # exclude_from_index: list = index["exclude_from_index"]

            # redis_schemas.setdefault(f"{index['space']}:{index['branch']}", [])
            # self.redis_indices.setdefault(
            #     f"{index['space']}:{index['branch']}:meta", {}
            # )

            generated_schema_fields = self.generate_db_index_from_class(
                index["class"], index["exclude_from_index"]
            )

            self.META_SCHEMA.update(generated_schema_fields)
    
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
        
    def redis_search_str_to_manticore_search_str(self, search: str, filters: dict[str, str | list | None]) -> tuple[str, dict[str, str | list[Any] | None]]:
        """
        Converts a Redis search string to a Manticore search string.
        """
        
        meta_fields = set(self.META_SCHEMA.keys())
        
        
        keys_locations = []
        for idx, char in enumerate(search):
            if char == "@" and (idx == 0 or search[idx-1] != '\\'):
                keys_locations.append(idx)
        
        for keys_idx, key in enumerate(keys_locations):
            idx = search.index(":", key)
            key_name = search[key+1:idx]
            if key_name not in meta_fields:
                continue
            value_end = len(search) - 1
            if keys_idx + 1 < len(keys_locations):
                value_end = keys_locations[keys_idx+1] - 1
            value_substr = search[idx+1:value_end]
            filters.setdefault(key_name, [])
            # print(key_name, filters[key_name], type(filters[key_name]))
            if isinstance(filters[key_name], str):
                filters[key_name] = [filters[key_name]]
            elif isinstance(filters[key_name], list):
                filters[key_name].extend(value_substr.replace("{", "").replace("}", "").split(" ")) #type: ignore
    
        for key in keys_locations[::-1]:
            idx = search.index(":", key)
            key_name = search[key+1:idx]
            if key_name not in meta_fields:
                continue
            value_end = len(search) - 1
            if key + 1 < len(search):
                try:
                    value_end = search.index("@", key + 1) - 1
                except Exception as _:
                    value_end = len(search) - 1
            search = search[:key] + search[value_end+1:]
        
        if search:
            search = search.replace("email_unescaped", "email")
            # Remove '@' symbols not prefixed by '\'
            search = re.sub(r'(?<!\\)@', '', search)
            
            # Replace ':' with '=' and enclose the following word in single quotes
            search = re.sub(r':([^ ]+)', r"='\1' AND", search)
            search = search.rstrip(' AND')    
            
            # Replace '{' and '}' with single quotes
            search = re.sub(r'\{(.+)\}', r"\1", search)
        
        return search, filters
        
            
            
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
        search, filters = self.redis_search_str_to_manticore_search_str(search, filters)
        subpath_query = ""
        if "subpath" in filters:
            requests_subpaths = ""
            if isinstance(filters["subpath"], str):
                requests_subpaths = filters["subpath"].strip("/")
            elif isinstance(filters["subpath"], list):
                filters["subpath"] = [item.strip("/") for item in filters["subpath"]]
                requests_subpaths = "("
                requests_subpaths += "|".join(filters["subpath"])
                requests_subpaths += ")"
            if exact_subpath:
                subpath_query = f"REGEX(subpath, '^\\/?{requests_subpaths}$') as subpath_match, "
            else:
                if requests_subpaths == "()":
                    requests_subpaths = ""
                suffix: str = "(\\/([A-Za-z0-9_])*)" if requests_subpaths != "" else "([A-Za-z0-9_]*)"
                subpath_query = f"REGEX(subpath, '^\\/?{requests_subpaths}{suffix}?$') as subpath_match, "
                
            del filters["subpath"]
        
        sql_str = f"SELECT {subpath_query} "
        sql_str += "*" if len(return_fields) == 0 else ",".join(return_fields)
        if highlight_fields and len(highlight_fields) != 0:
            sql_str += ", HIGHLIGHT({}, %s)" % ",".join(highlight_fields)

        sql_str += f" FROM {space_name}__{branch_name}__{schema_name}"

        # manticore_escape_chars = str.maketrans(
        #     {":": r"\:", "/": r"\/", "-": r"\-"}
        # )

        match_query = "match('"
        where_filters = []
        if len(filters.keys()) != 0:
            for key, value in filters.items():
                if key in ["tags", "query_policies"] and value:
                    value = ['"'+item+'"' for item in value]
                    match_query += f" @{key} {'|'.join(value)} "
                    if filters.get("user_shortname", None) is not None and key == "query_policies":
                        match_query += f" | @view_acl {filters['user_shortname']} "
                elif isinstance(value, list) and value:
                    if len(value):
                        where_filters.append(f"{key} IN ('" + ', '.join(map(str, value)) + "')")
                elif isinstance(value, str) and value and key != "user_shortname":
                    where_filters.append(f"{key}='{value}'")
                elif value and key != "user_shortname":
                    where_filters.append(f"{key}={value}")
                    

        if not search:
            search = f" {match_query}')"
        elif "match('" in search:
            search = search.replace("match('", f"{match_query}")
        else:
            search += f" AND {match_query}')"
            
        sql_str += f" WHERE {search}"
        if subpath_query:
            sql_str += " AND subpath_match = 1 "
        
        
        if where_filters:
           sql_str += " AND " 
           
        sql_str += " AND ".join(where_filters)
        
            
        if sort_by:
            sql_str += f" ORDER BY {sort_by} {'asc' if sort_type == SortType.ascending else 'desc'}"

        sql_str += f" LIMIT {limit} OFFSET {offset}"
        sql_str = sql_str.replace(" AND match('')", "")
        

        result = self.mc_command(sql_str)
        if not result:
            return 0, []
        
        decoded_result = []
        for doc in result["data"]:
            decoded_result.append(self.decode_db_data(doc))

        return result["total"], decoded_result

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
        if not search:
            search = ""
        search, filters = self.redis_search_str_to_manticore_search_str(search, filters)
        subpath_query = ""
        if "subpath" in filters:
            requests_subpaths = ""
            if isinstance(filters["subpath"], str):
                requests_subpaths = filters["subpath"]
            elif isinstance(filters["subpath"], list):
                requests_subpaths = "("
                requests_subpaths += "|".join(filters["subpath"])
                requests_subpaths += ")"
            if exact_subpath:
                subpath_query = f"REGEX(subpath, '^\\/?{requests_subpaths}$') as subpath_match, "
            else:
                subpath_query = f"REGEX(subpath, '^\\/?{requests_subpaths}(\\/([A-Za-z0-9_])*)?$') as subpath_match, "
                
            del filters["subpath"]
        
        sql_str = f"SELECT {subpath_query} "
        if len(reducers) == 0:
            sql_str += "*"
        else:
            for reducer_index in range(len(reducers)):
                for operation, fields in reducers[reducer_index].items():
                    sql_str += f'{operation}({",".join(fields)})'
                    if reducer_index < len(reducers) - 1:
                        sql_str += ", "

        sql_str += f" FROM {space_name}__{branch_name}__{schema_name}"

        # if search:
        #     sql_str += f" WHERE {search})"
        # manticore_escape_chars = str.maketrans(
        #     {":": r"\:", "/": r"\/", "-": r"\-"}
        # )

        match_query = "match('"
        where_clauses = []
        for key, value in filters.items():
            if key in ["tags", "query_policies"] and value is not None:
                match_query += f" @{key} {' '.join(value)} "
                if filters.get("user_shortname", None) is not None and key == "query_policies":
                    match_query += f" | @view_acl {filters['user_shortname']} "
            elif isinstance(value, list) and value:
                where_clauses.append(f"{key} IN ({', '.join(map(str, value))})")
            elif isinstance(value, str) and value and key != "user_shortname":
                where_clauses.append(f"{key}='{value}'")
            elif value and key != "user_shortname":
                where_clauses.append(f"{key} = '{value}'")

        
        if not search:
            search = f" {match_query}')"
        elif "match('" in search:
            search = search.replace("match('", f"{match_query}")
        else:
            search += f" AND {match_query}')"
        sql_str += f" WHERE {search} "
        if subpath_query:
            sql_str += " AND subpath_match = 1 "
        if where_clauses:
           sql_str += " AND " 
        sql_str += " AND ".join(where_clauses)
        

        if group_by:
            sql_str += " GROUP BY "
            sql_str += ", ".join(group_by)

        if sort_by:
            sql_str += f" ORDER BY {sort_by} {sort_type}"

        sql_str += f" LIMIT {limit}"

        result = self.mc_command(sql_str)

        if not result or "data" not in result or not isinstance(result["data"], list):
            return []

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
        
        if not result or "data" not in result or not isinstance(result["data"], list) or not isinstance(result["data"][0]["c"], int):
            return 0
        return result["data"][0]["c"]

    async def free_search(
        self, index_name: str, search_str: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        sql_str = f"SELECT * FROM {index_name}"
        if search_str:
            sql_str += f" WHERE {search_str}"
        sql_str += f" LIMIT {limit} OFFSET {offset}"

        result = self.mc_command(sql_str)
        if not result or "data" not in result or not isinstance(result["data"], list):
            return []
        return result["data"]

    async def dto_doc_id(self, dto: EntityDTO) -> str:
        return self.generate_doc_id(dto.space_name, dto.branch_name, dto.schema_shortname, dto.shortname, dto.subpath)

    async def find_key(self, key: str) -> str | None:
        res = self.mc_command(f"select * from key_value_pairs where key = '{key}' limit 1")
        if res is None or res['total'] == 0:
            return None
        
        if res['data'][0]['ex'] and ((res['data'][0]['created_at'] + res['data'][0]['ex']) < datetime.now()):
            await self.delete_doc_by_id(key)
            return None
        
        return str(res['data'][0]['value'])
    
    async def set_key(self, key: str, value: str, ex=None, nx: bool = False) -> bool:
        await self.create_key_value_pairs_index()
        
        statement = {
            "index": "key_value_pairs",
            "doc": {
                "key": key, "value": value, "ex": ex if ex else 0, "created_at": datetime.now().timestamp()
            }
        }
        find_res = self.mc_command(f"select * from key_value_pairs where key = '{key}' limit 1")
        if find_res is None or find_res['total'] == 0:
            res = self.indexApi.insert(statement)
        else:
            statement["id"] = find_res['data'][0]['id']
            res = self.indexApi.replace(statement)
            
        
        return bool(res)
    
    def parse_db_record(self, db_record: dict[str, Any], is_source: bool = False) -> dict[str, Any]:
        if db_record['total'] == 0:
            return {}
        document: dict[str, Any] = db_record["data"][0]["value"] if "value" in db_record["data"][0] else db_record["data"][0]
        if isinstance(document, dict):
            document = document
        elif isinstance(document, str):
            document = json.loads(document)
        else:
            raise Exception(f"Invalid data type {type(document)}")
        
        # Don't attempt to decode the spaces document
        if is_source or ('key' in db_record["data"][0] and db_record["data"][0]["key"] == "spaces"):
            return document
        
        return self.decode_db_data(document)
                
    
    async def find(self, dto: EntityDTO) -> None | dict[str, Any]:
        document_id = await self.dto_doc_id(dto)
        index_name = self.get_index_name_from_doc_id(document_id)
        identifier = "document_id"
        if index_name == "key_value_pairs":
            identifier = "key"
        sql_str = f"SELECT * FROM {index_name}"
        sql_str += f" WHERE {identifier}='{document_id}'"
        result = self.mc_command(sql_str)
        if not result:
            return None
        
        return self.parse_db_record(result)
    
    def decode_db_data(self, data: dict[str, Any]) -> dict[str, Any]:
        data = delete_empty_strings(data)
        decoded_data = {}
        for key, value in data.items():
            if key in ["subpath_match", "id"]:
                continue
            if isinstance(value, str) and (value.startswith("{") or value.startswith("[")):
                decoded_data[key] = json.loads(value)
            else:
                decoded_data[key] = value

        return decoded_data

    def get_index_name_from_doc_id(self, doc_id: str) -> str:
        if ":" not in doc_id:
            return "key_value_pairs"
        
        doc_id_parts = doc_id.split(":")
        
        if len(doc_id_parts) < 3:
            raise Exception(f"Invalid document id, {doc_id}")
        
        schema_name = doc_id_parts[2]
        # Store schema payload docs in key_value_pairs table
        if schema_name == "meta_schema":
            return "key_value_pairs"
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
            
            return self.parse_db_record(find_res)
        except Exception as e:
            logger.error(f"Error at ManticoreDB.find_by_id: {e.args}")
            return {}
    
    async def list_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        return []
    
    async def delete_keys(self, keys: list[str]) -> bool:
        return True

    async def find_payload_data_by_id(
        self, id: str, resource_type: ResourceType
    ) -> dict[str, Any]:
        return await self.find_by_id(id)

    
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

    def is_entry_exist(self, id: str):
        try:
            index_name: str = self.get_index_name_from_doc_id(id)
            identifier = "document_id"
            if index_name == "key_value_pairs":
                identifier = "key"
            find_res = self.mc_command(
                f"select * from {index_name} where {identifier} = '{id}' limit 1"
            )
            if not find_res:
                return {}
            return self.parse_db_record(find_res, True)
        except Exception as e:
            logger.error(f"Error at ManticoreDB.is_entry_exist {e}")
        
            
    async def save_at_id(self, id: str, doc: dict[str, Any] = {}) -> bool:
        if ":" not in id:
            await self.set_key(id, json.dumps(doc))
            
        try:
            doc['document_id'] = id
            index = self.get_index_name_from_doc_id(id)
            existing_entry = self.is_entry_exist(id)
            if existing_entry and "id" in existing_entry:
                res = self.indexApi.replace({
                    "index": index,
                    "id": existing_entry["id"],
                    "doc": doc
                })
            else:
                res = self.indexApi.insert({
                    "index": index,
                    "doc": doc
                })
            if not res or not isinstance(res, dict):
                return False
            
            return 'created' in res and res['created'] is True
        except Exception as e:
            logger.error(f"Error at ManticoreDB.save_at_id: {e}")
            return False

    async def save_bulk(self, index: str, docs: list[dict[str, Any]]) -> int:
        if len(docs) == 0:
            return 0
        try:
            # Store schema payload docs in key_value_pairs table
            if index.endswith("meta_schema"):
                index = "key_value_pairs"
                docs = [{"key": doc['document_id'], "value": json.dumps(doc)} for doc in docs]
            
            docs = [{"insert": {"index": index, "doc": doc}} for doc in docs]
            
            res: BulkResponse = self.indexApi.bulk('\n'.join(map(json.dumps,docs))) # type: ignore
            
            if res.errors is not False:
                raise Exception(res.errors)
            
            if not isinstance(res.items, list) or not isinstance(res.items[0], dict):
                raise Exception("Invalid response " + str(res.items))
            
            
            return int(res.items[0]['bulk']['created'])
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
        
        meta_json = self.encode_doc(meta_json, meta_doc_id)
        
        # Encode list to json string
        meta_json = {key: json.dumps(value) if isinstance(value, list) else value for key, value in meta_json.items()}

        return meta_doc_id, meta_json

    def encode_doc(self, doc: dict[str, Any], id: str) -> dict[str, Any]:
        
        filtered_doc: dict[str, Any] = {}

        index_name = self.get_index_name_from_doc_id(id)
        res = self.mc_command(f"describe {index_name}")
        if not res:
            return filtered_doc
        
        index_schema = res['data']
        index_fields = {field['Field'] for field in index_schema}
        filtered_doc = {field: doc[field] for field in doc if field in index_fields}
        
        # Encode list to json string
        filtered_doc = {
            key: json.dumps(value) if isinstance(value, list) else value
            for key, value in filtered_doc.items()
        }
        
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

        payload = self.encode_doc(payload, docid)

        

        return docid, payload

    async def delete(self, dto: EntityDTO) -> bool:
        return await self.delete_doc_by_id(await self.dto_doc_id(dto))
        

    async def delete_doc_by_id(self, id: str) -> bool:
        idx_name = self.get_index_name_from_doc_id(id)
        identifier = "document_id"
        if idx_name == "key_value_pairs":
            identifier = "key"
        command = f"DELETE FROM {idx_name} WHERE {identifier} = '{id}'"
        try:
            self.utilsApi.sql(command)
            return True
        except Exception as e:
            logger.error(f"Error at ManticoreDB.delete: {e}")
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
    
    async def create_lock_indexes(self):
        spaces = await self.find_by_id("spaces")
        for space_name in spaces:
            self.mc_command(f"create table if not exists {space_name}__master__lock(owner_shortname string, lock_time string, document_id string) morphology='stem_en'")
        return True
        
    async def save_lock_doc(
        self, dto: EntityDTO, owner_shortname: str, ttl: int = settings.lock_period
    ) -> LockAction | None:
        lock_doc_id = self.generate_doc_id(
            dto.space_name, 
            dto.branch_name, 
            "lock", 
            dto.shortname, 
            dto.subpath
        )
        lock_data = await self.get_lock_doc(
            dto
        )
        # idx = self.dto_doc_id(dto)
        if not lock_data:
            payload = {
                "owner_shortname": owner_shortname,
                "lock_time": str(datetime.now().isoformat()),
            }

            # alternaticr
            result = await self.save_at_id(lock_doc_id, payload) # , nx=True
            if result is None:
                lock_payload = await self.get_lock_doc(
                    dto
                )
                if lock_payload["owner_shortname"] != owner_shortname:
                    raise api.Exception(
                        status_code=status.HTTP_403_FORBIDDEN,
                        error=api.Error(
                            type="lock",
                            code= 31, # InternalErrorCode.LOCKED_ENTRY,
                            message=f"Entry is already locked by {lock_payload['owner_shortname']}",
                        ),
                    )
            lock_type = LockAction.lock
        else:
            lock_type = LockAction.extend
        return lock_type

    async def get_lock_doc(self, dto: EntityDTO) -> dict[str, Any]:
        lock_doc_id = self.generate_doc_id(
            dto.space_name,
            dto.branch_name, 
            "lock", 
            dto.shortname, 
            dto.subpath
        )
        lock_doc =  await self.find_by_id(lock_doc_id)
        
        # Handle new spaces lock tables
        if not lock_doc:
            self.mc_command(f"create table if not exists {dto.space_name}__master__lock(owner_shortname string, lock_time string, document_id string) morphology='stem_en'")
            
        return lock_doc

    async def is_locked_by_other_user(
        self, dto: EntityDTO
    ) -> bool:
        try:
            lock_payload = await self.get_lock_doc(dto)

            if lock_payload:
                if dto.user_shortname:
                    return bool(lock_payload["owner_shortname"] != dto.user_shortname)
                else:
                    return True
            return False

        except Exception as e:
            logger.error(f"Error at BaseDB.is_locked_by_other: {e}")
            return False

    async def delete_lock_doc(self, dto: EntityDTO) -> None:
        await self.delete(dto)
