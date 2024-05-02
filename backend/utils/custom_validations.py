import json
from typing import Any
import aiofiles
from fastapi import status
from utils.helpers import branch_path, csv_file_to_json
from utils.internal_error_code import InternalErrorCode
from models.api import Exception as API_Exception, Error as API_Error
from utils.settings import settings
from pathlib import Path as FSPath
from jsonschema import Draft7Validator
from starlette.datastructures import UploadFile

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
    schema_path: FSPath = (
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
        message = f"Invalid schema path, {schema_path} is not a file"
        raise Exception(message)
    
    return schema_path
    




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