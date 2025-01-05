import json
from typing import Any
import aiofiles
from utils.helpers import csv_file_to_json
from utils.settings import settings
from pathlib import Path as FSPath
from jsonschema import Draft7Validator


def get_schema_path(space_name: str, schema_shortname: str):
    # Tries to get the schema from the management space first
    schema_path = (
        settings.spaces_folder / 
        settings.management_space / 
        "schema" /
        schema_shortname
    )

    if schema_path.is_file():
        return schema_path

    schema_path = (
        settings.spaces_folder / 
        space_name / 
        "schema" /
        schema_shortname
    )
    
    if not schema_path.is_file():
        raise Exception(f"Invalid schema path, {schema_path=} is not a file")
    
    return schema_path

async def validate_jsonl_with_schema(
    file_path: FSPath,
    space_name: str,
    schema_shortname: str,
) -> None:

    schema_path = get_schema_path(
        space_name=space_name,
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
) -> None:

    schema_path = get_schema_path(
        space_name=space_name,
        schema_shortname=f"{schema_shortname}.json",
    )

    schema = json.loads(FSPath(schema_path).read_text())

    jsonl: list[dict[str, Any]] = await csv_file_to_json(file_path)
    for json_item in jsonl:
        Draft7Validator(schema).validate(json_item)
