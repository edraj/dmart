import json
import aiofiles
import json
from fastapi import status
from models.core import Record
from models.enums import RequestType
from utils.helpers import branch_path, flatten_dict, flatten_list_of_dicts_in_dict
from utils.redis_services import RedisServices
from models.api import Exception as API_Exception, Error as API_Error
from utils.settings import settings
from pathlib import Path as FSPath
from utils.settings import settings
from jsonschema import Draft7Validator
from starlette.datastructures import UploadFile


async def validate_payload_with_schema(
    payload_data: UploadFile | dict,
    space_name: str,
    schema_shortname: str,
    branch_name: str | None = settings.default_branch,
):

    if type(payload_data) not in [dict, UploadFile]:
        raise API_Exception(
            status.HTTP_400_BAD_REQUEST,
            API_Error(
                type="request",
                code=406,
                message="Invalid payload.body",
            ),
        )

    schema_path = get_schema_path(
        space_name=space_name,
        branch_name=branch_name,
        schema_shortname=f"{schema_shortname}.json",
    )

    if not schema_path.is_file():
        raise Exception(f"Invalid schema path, {schema_path=} is not a file")

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

    return (
        settings.spaces_folder / 
        space_name / 
        branch_path(branch_name) / 
        "schema" /
        schema_shortname
    )


async def validate_uniqueness(
    space_name: str, record: Record, action: str = RequestType.create
):
    """
    Get list of unique fields from entry's folder meta data
    ensure that each sub-list in the list is unique across all entries
    """
    folder_meta_path = (
        settings.spaces_folder
        / space_name
        / branch_path(record.branch_name)
        / f"{record.subpath[1:] if record.subpath[0] == '/' else record.subpath}.json"
    )

    if not folder_meta_path.is_file():
        return True

    async with aiofiles.open(folder_meta_path, "r") as file:
        content = await file.read()
    folder_meta = json.loads(content)

    if type(folder_meta.get("unique_fields", None)) != list:
        return True

    entry_dict_flattened = flatten_list_of_dicts_in_dict(
        flatten_dict(record.attributes)
    )
    redis_escape_chars = str.maketrans(
        {".": r"\.", "@": r"\@", ":": r"\:", "/": r"\/", "-": r"\-", " ": r"\ "}
    )
    # Go over each composite unique array of fields and make sure there's no entry with those values
    for composite_unique_keys in folder_meta["unique_fields"]:
        redis_search_str = ""
        for unique_key in composite_unique_keys:
            base_unique_key = unique_key
            if unique_key.endswith("_unescaped"):
                unique_key = unique_key.replace("_unescaped", "") 
            if unique_key not in entry_dict_flattened:
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
                type(entry_dict_flattened[unique_key]) == list
            ):
                redis_search_str += (
                    " @"
                    + redis_column
                    + ":{"
                    + "|".join(entry_dict_flattened[unique_key])
                    + "}"
                )
            elif type(entry_dict_flattened[unique_key]) in [
                str,
                bool,
            ]:  # booleans are indexed as TextField
                redis_search_str += (
                    " @"
                    + redis_column
                    + ":"
                    + entry_dict_flattened[unique_key]
                    .translate(redis_escape_chars)
                    .replace("\\\\", "\\")
                )

            elif type(entry_dict_flattened[unique_key]) == int:
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

        if action == RequestType.update:
            redis_search_str += f" (-@shortname:{record.shortname})"

        schema_name = record.attributes.get("payload", {}).get("schema_shortname", None)

        for index in RedisServices.CUSTOM_INDICES:
            if space_name == index["space"] and index["subpath"] == subpath:
                schema_name = f"meta"
                break

        if not schema_name:
            continue

        async with RedisServices() as redis_services:
            redis_search_res = await redis_services.search(
                space_name=space_name,
                branch_name=record.branch_name,
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
                    code=415,
                    message=f"Entry should have unique values on the following fields: {', '.join(composite_unique_keys)}",
                ),
            )
