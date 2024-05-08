
import json
import re
from typing import Any
from db.base_db import BaseDB
import manticoresearch
from fastapi.logger import logger
from models.core import EntityDTO, Meta, Space
from models.enums import LockAction, ResourceType, SortType
from utils.helpers import resolve_schema_references
from utils.settings import settings


class ManticoreDB(BaseDB):
    config = manticoresearch.Configuration(
        host = f"{settings.operational_db_host}:{settings.operational_db_port}",
        username=settings.operational_db_user,
        password=settings.operational_db_password
    )
    client = manticoresearch.ApiClient(config)
    indexApi = manticoresearch.IndexApi(client)
    searchApi = manticoresearch.SearchApi(client)
    utilsApi = manticoresearch.UtilsApi(client)
    
    META_SCHEMA = [
        "document_id string",
        "uuid string",
        "shortname string",
        "slug string",
        "subpath string",
        "exact_subpath string",
        "resource_type string",
        "displayname_en string",
        "displayname_ar string",
        "displayname_kd string",
        "description_en string",
        "description_ar string",
        "description_kd string",

        "is_active bool",

        "payload_content_type string",
        "schema_shortname string",
        
        "payload_content_type string",
        "payload_content_type string",
        
        "created_at timestamp",
        "updated_at timestamp",
        
        "view_acl text",
        "tags text",
        "query_policies text",
        
        "owner_shortname string",
        "payload_content_type string",


        # User fields
        "msisdn string",
        "email string",
        # Ticket fields
        "state string",
        "is_open bool",
        "workflow_shortname string",
        "collaborators_delivered_by string",
        "collaborators_processed_by string",
        "resolution_reason string",

        # Notification fields
        "type string",
        "is_read string",
        "priority string",
        "reporter_type string",
        "reporter_name string",
        "reporter_channel string",
        "reporter_distributor string",
        "reporter_governorate string",
        "reporter_msisdn string",
        
        "payload_string string",
    ]

    async def create_index(self, name: str, fields: list[Any], **kwargs) -> bool:
        try:
            self.utilsApi.sql(f"DROP TABLE {name};")
        except Exception as _:
            pass
        
        try:
            sql_str = f"CREATE TABLE {name}("
            for field in fields:
                sql_str += field
            sql_str.strip(",")
            sql_str += ");"
            self.utilsApi.sql(sql_str)
            return True
        except Exception as e:
            logger.error(f"Error at ManticoreDB.create_index: {e.args}")
            return False
            
    def get_index_fields_from_json_schema_property(self, key_chain, property, redis_schema_definition):
        """
        takes a key and a value of a schema definition property, and returns the redis schema index
        """
        SCHEMA_DATA_TYPES_MAPPER = {
            "string": "string",
            "boolean": "bool",
            "integer": "int",
            "number": "int",
            "array": "text",
        }
        if not isinstance(property, dict) or key_chain.endswith("."):
            return redis_schema_definition

        if "type" in property and property["type"] != "object":
            if property["type"] in ["null", "boolean"] or not isinstance(
                property["type"], str
            ):
                return redis_schema_definition

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
                    redis_schema_definition.append(f"{key_chain}_{property_key} text")
                return redis_schema_definition

            # if property["type"] == "array":
            #     key_chain += ".*"

            redis_schema_definition.append(
                f"{key_chain} {SCHEMA_DATA_TYPES_MAPPER[property['type']]}"
            )
            return redis_schema_definition

        if "oneOf" in property:
            for item in property["oneOf"]:
                redis_schema_definition = self.get_index_fields_from_json_schema_property(
                    key_chain, item, redis_schema_definition
                )
            return redis_schema_definition

        if "properties" not in property:
            return redis_schema_definition

        for property_key, property_value in property["properties"].items():
            redis_schema_definition = self.get_index_fields_from_json_schema_property(
                f"{key_chain}.{property_key}", property_value, redis_schema_definition
            )

        return redis_schema_definition
    
    def append_unique_index_fields(self, new_index: list[str], base_index: list[str]):
        unique_fields = set(base_index).union(set(new_index))
        return list(unique_fields)
    
    async def create_application_indexes(
        self, 
        for_space: str | None = None, 
        for_schemas: list | None = None, 
        for_custom_indices: bool = True, 
        del_docs: bool = True
    ) -> None:
        
        spaces = await self.find_by_id("spaces")
        for space_name in spaces:
            space_obj = Space.model_validate_json(spaces[space_name])
            if (
                for_space and for_space != space_name
            ) or not space_obj.indexing_enabled:
                continue

            # CREATE REDIS INDEX FOR THE META FILES INSIDE THE SPACE
            # self.redis_indices[f"{space_name}:{branch_name}"] = {}
            # self.redis_indices[f"{space_name}:{branch_name}"]["meta"] = self.ft(
            #     f"{space_name}:{branch_name}:meta"
            # )

            await self.create_index(
                f"{space_name}:meta", self.META_SCHEMA
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
                redis_schema_definition = list(self.META_SCHEMA)
                if "properties" in schema_content:
                    for key, property in schema_content["properties"].items():
                        generated_schema_fields = self.get_index_fields_from_json_schema_property(
                            key, property, []
                        )
                        redis_schema_definition = self.append_unique_index_fields(
                            generated_schema_fields, redis_schema_definition
                        )

                elif "oneOf" in schema_content:
                    for item in schema_content["oneOf"]:
                        for key, property in item["properties"].items():
                            generated_schema_fields = self.get_index_fields_from_json_schema_property(
                                key, property, []
                            )
                            redis_schema_definition = (
                                self.append_unique_index_fields(
                                    generated_schema_fields, redis_schema_definition
                                )
                            )

                if redis_schema_definition:
                    redis_schema_definition.append("meta_doc_id string")

                    await self.create_index(
                        f"{space_name}:{schema_shortname}",
                        redis_schema_definition
                    )

        # if for_custom_indices:
        #     await self.create_custom_indices(for_space)
    
    async def flush_all(self) -> None:
        try:
            tables = self.utilsApi.sql('SHOW TABLES') 
            if(
                not isinstance(tables, list) or 
                len(tables) == 0 or 
                not isinstance(tables[0], dict)
            ):
                return
            
            for table in tables[0].get('data', []):
                self.utilsApi.sql(f'DROP TABLE {table['Index']}')
                
        except Exception as e:
            logger.error(f"Error at ManticoreDB.flush_all: {e.args}")
            
            
    async def list_indexes(self) -> set[str]:
        return set("")

    async def drop_index(self, name: str, delete_docs: bool) -> bool:
        return True
    
    
    async def create_custom_indices(self, for_space: str | None = None) -> None:
        pass
        
    
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

        sql_query = "SELECT"
        if len(highlight_fields) == 0:
            sql_query += "*" if len(return_fields) == 0 else ",".join(return_fields)
        else:
            sql_query += "HIGHLIGHT({}, %s) as snippet" % ",".join(highlight_fields)

        sql_query += f" FROM {space_name} WHERE MATCH('{search}')"

        where_filters = []
        if len(filters.keys()) != 0:
            sql_query += " AND "
            for key, value in filters.items():
                if isinstance(value, str):
                    where_filters.append(f"{key}='{value}'")
                else:
                    where_filters.append(f"{key}={value}")

            sql_query += " AND ".join(where_filters)

        sql_query += f" ORDER BY {sort_by} {sort_type} LIMIT {limit} OFFSET {offset}"
        result = self.utilsApi.sql(sql=sql_query)

        return (result[0]["total"], result[0]["data"])

    async def aggregate(self,
        space_name: str,
        filters: dict[str,
        str | list | None],
        group_by: list[str],
        reducers: list[Any],
        search: str | None = None,
        max: int = 10,
        branch_name: str = settings.default_branch,
        exact_subpath: bool = False,
        sort_type: SortType = SortType.ascending,
        sort_by: str | None = None,
        schema_name: str = "meta",
        load: list = []
    ) -> list[Any]:
        return []
    
    async def get_count(self, 
        space_name: str, 
        schema_shortname: str, 
        branch_name: str = settings.default_branch
    ) -> int:
        return 0
    
    async def free_search(self, 
        index_name: str, 
        search_str: str, 
        limit: int = 20, 
        offset: int = 0
    ) -> list[dict[str, Any]]:
        return []
    
    async def dto_doc_id(self, dto: EntityDTO) -> str:
        return ""
    
    async def find_key(self, key: str) -> str | None:
        pass
    
    async def set_key(self, key: str, value: str, ex=None, nx: bool = False) -> bool:
        return True
    
    async def find(self, dto: EntityDTO) -> None | dict[str, Any]:
        pass
    
    
    async def find_by_id(self, id: str) -> dict[str, Any]:
        try:
            return {}
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
        return {}


    async def save_at_id(self, id: str, doc: dict[str, Any] = {}) -> bool:
        return True


    async def prepare_meta_doc(
        self, space_name: str, branch_name: str | None, subpath: str, meta: Meta
    ) -> tuple[str, dict[str, Any]]:
        return {}


    async def prepare_payload_doc(
        self,
        dto: EntityDTO,
        meta: Meta,
        payload: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        return ("", {})
    


    async def delete(self, dto: EntityDTO) -> bool:
        return True


    async def delete_doc_by_id(self, id: str) -> bool:
        return True
    
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
        return True
    
    

    async def save_lock_doc(
        self, dto: EntityDTO, owner_shortname: str, ttl: int = settings.lock_period
    ) -> LockAction | None:
        pass


    async def get_lock_doc(self, dto: EntityDTO) -> dict[str, Any]:
        return {}


    async def is_locked_by_other_user(
        self, dto: EntityDTO
    ) -> bool:
        return True
    

    async def delete_lock_doc(self, dto: EntityDTO) -> None:
        pass
        
