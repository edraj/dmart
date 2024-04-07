import json
from typing import Any
import aiofiles
from fastapi import status
from models.core import EntityDTO, Record
from models.enums import QueryType, RequestType
from utils.helpers import branch_path, csv_file_to_json, flatten_dict, flatten_list_of_dicts_in_dict
from utils.internal_error_code import InternalErrorCode
from models.api import Exception as API_Exception, Error as API_Error, Query
from utils.settings import settings
from pathlib import Path as FSPath
from jsonschema import Draft7Validator
from starlette.datastructures import UploadFile
from utils.operational_repo import operational_repo

async def validate_payload_with_schema(
    payload_data: UploadFile | dict,
    space_name: str,
    schema_shortname: str,
    branch_name: str | None = settings.default_branch,
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
        branch_name=branch_name,
        schema_shortname=f"{schema_shortname}.json",
    )

    schema = json.loads(FSPath(schema_path).read_text())

    if not isinstance(payload_data, dict):
        data = json.load(payload_data.file)
        payload_data.file.seek(0)
    else:
        data = payload_data

    Draft7Validator(schema).validate(data)


def get_schema_path(space_name: str, branch_name: str | None, schema_shortname: str):
    # Tries to get the schema from the management space first
    schema_path = (
        settings.spaces_folder / 
        settings.management_space / 
        branch_path(settings.management_space_branch) / 
        "schema" /
        schema_shortname
    )

    if schema_path.is_file():
        return schema_path

    schema_path = (
        settings.spaces_folder / 
        space_name / 
        branch_path(branch_name) / 
        "schema" /
        schema_shortname
    )
    
    if not schema_path.is_file():
        raise Exception(f"Invalid schema path, {schema_path=} is not a file")
    
    return schema_path
    


async def validate_uniqueness(
    entity: EntityDTO, input_data: dict[str, Any], action: str = RequestType.create
):
    """
    Get list of unique fields from entry's folder meta data
    ensure that each sub-list in the list is unique across all entries
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
    redis_replace_chars : dict[int, str] = str.maketrans(
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
            if not entry_dict_flattened.get(unique_key, None) :
                continue

            redis_column = unique_key.split("payload.body.")[-1].replace(".", "_")

            # construct redis search string
            if(
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
            elif(
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
                
            elif(
                isinstance(entry_dict_flattened[unique_key], list)
            ):
                redis_search_str += (
                    " @"
                    + redis_column
                    + ":{"
                    + "|".join([
                        item.translate(redis_escape_chars).replace("\\\\", "\\") for item in entry_dict_flattened[unique_key]
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

        subpath = entity.subpath
        if subpath[0] == "/":
            subpath = subpath[1:]

        # redis_search_str += f" @subpath:{subpath}"

        if action == RequestType.update:
            redis_search_str += f" (-@shortname:{entity.shortname})"

        schema_name = input_data.get("payload", {}).get("schema_shortname", None)

        for index in operational_repo.SYS_INDEXES:
            if entity.space_name == index["space"] and index["subpath"] == subpath:
                schema_name = "meta"
                break

        if not schema_name:
            continue

        redis_search_res = await operational_repo.search(Query(
            type=QueryType.search,
            space_name=entity.space_name,
            branch_name=entity.branch_name,
            search=redis_search_str,
            subpath=subpath,
            filter_schema_name=[schema_name],
            limit=1
        ))

        if redis_search_res and redis_search_res[0] > 0:
            raise API_Exception(
                status.HTTP_400_BAD_REQUEST,
                API_Error(
                    type="request",
                    code=InternalErrorCode.DATA_SHOULD_BE_UNIQUE,
                    message=f"Entry should have unique values on the following fields: {', '.join(composite_unique_keys)}",
                ),
            )


async def validate_jsonl_with_schema(
    file_path: FSPath,
    space_name: str,
    schema_shortname: str,
    branch_name: str | None = settings.default_branch,
) -> None:

    schema_path = get_schema_path(
        space_name=space_name,
        branch_name=branch_name,
        schema_shortname=f"{schema_shortname}.json",
    )

    schema = json.loads(FSPath(schema_path).read_text())

    async with aiofiles.open(file_path, "r") as file:
        lines = await file.readlines()
        for line in lines:
            Draft7Validator(schema).validate(line)
            
            
async def validate_csv_with_schema(
    file_path: FSPath,
    space_name: str,
    schema_shortname: str,
    branch_name: str | None = settings.default_branch,
) -> None:

    schema_path = get_schema_path(
        space_name=space_name,
        branch_name=branch_name,
        schema_shortname=f"{schema_shortname}.json",
    )

    schema = json.loads(FSPath(schema_path).read_text())

    jsonl: list[dict[str, Any]] = await csv_file_to_json(file_path)
    for json_item in jsonl:
        Draft7Validator(schema).validate(json_item)