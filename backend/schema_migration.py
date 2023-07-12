import argparse
import asyncio
from enum import Enum
import re
import sys
from models.enums import ContentType
from utils import db, helpers
from models.core import Meta, Schema
from utils.repository import _sys_update_model
from utils.settings import settings

class FieldType(Enum):
    string = "string"
    number = "number"
    integer = "integer"
    array = "array"
    
    
FIELD_TYPE_PARSER: dict = {
    "string": str,
    "number": int,
    "integer": int,
    "array": list
}
    
    
async def change_field_type(
    space: str,
    schema_model: Schema,
    schema_payload: dict,
    field: str,
    new_type: FieldType
):
    # 3-update field type to new_type
    schema_properties = schema_payload["properties"]
    schema_properties[field]["type"] = new_type
    await _sys_update_model(
        space_name=space,
        subpath="schema",
        meta=schema_model,
        payload_dict=schema_payload,
        updates={
            "properties": schema_properties
        },
        branch_name=settings.default_branch
    )
    
    updated_num = 0
    
    # 4-loop over space by glob "*/.dm/*/meta.*.json"
    path = settings.spaces_folder / space
    entries_glob = "*/.dm/*/meta.*.json"
    FILE_PATTERN = re.compile("(\\w*)\\/\\.dm\\/(\\w*)\\/meta\\.([a-zA-Z]*)\\.json$")
    for one in path.glob(entries_glob):
        match = FILE_PATTERN.search(str(one))
        if not match or not one.is_file:
            continue
        subpath = match.group(1)
        shortname = match.group(2)
        resource_type = match.group(3)
        resource_cls = getattr(
            sys.modules["models.core"], helpers.camel_case(resource_type)
        )
        try:
            resource_obj: Meta = await db.load(
                space_name=space,
                subpath=subpath,
                shortname=shortname,
                class_type=resource_cls
            )
            
            # 5-if resource.schema_shortname == schema:
            if resource_obj.payload.schema_shortname != schema_model.shortname:
                continue
            
            # 5.1-load payload file
            resource_payload = db.load_resource_payload(
                space_name=space,
                subpath=subpath,
                filename=resource_obj.payload.body,
                class_type=resource_cls
            )
        except Exception as ex:
            print(f"Error loading {one}", ex)
            continue
        
        
        if field not in resource_payload:
            continue
        
        # 5.2-parse field's old_type to new_type
        await _sys_update_model(
            space_name=space,
            subpath=subpath,
            meta=resource_obj,
            payload_dict=resource_payload,
            updates={
                field: FIELD_TYPE_PARSER[new_type](resource_payload[field])
            },
            branch_name=settings.default_branch
        )
        updated_num += 1
        
    return updated_num
    

async def main(
    space: str,
    schema: str,
    field: str,
    old_type: FieldType,
    new_type: FieldType
):
    """
    Algorithm:
    1-load schema
    2-make sure field with old_type exist
    3-update field type to new_type
    4-loop over space by glob "*/.dm/*/meta.*.json"
    5-if resource.schema_shortname == schema:
        5.1-load payload file
        5.2-parse field's old_type to new_type
    """
    
    # 1-load schema
    schema_model: Schema = await db.load(
        space_name=space,
        subpath="schema",
        shortname=schema,
        class_type=Schema
    )
    if(
        schema_model.payload.content_type != ContentType.json or
        not schema_model.payload.body
    ):
        print(f"Invalid schema file: \n{schema_model.json()}")
        return
    schema_payload: dict = db.load_resource_payload(
        space_name=space,
        subpath="schema",
        filename=schema_model.payload.body,
        class_type=Schema
    )
    
    # 2-make sure field with old_type exist
    if schema_payload["properties"].get(field, {}).get("type") != old_type:
        print("Invalid old type for the specified field under the specified schema")
        return
        
        
    updated_num = await change_field_type(
        space,
        schema_model,
        schema_payload,
        field,
        new_type
    )
    
    print(f"Successfully updated the schema along with {updated_num} resource files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Change field type in a specific Schema under a specific Space",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-p", "--space", help="Space name")
    parser.add_argument("-c", "--schema", help="Schema name")
    parser.add_argument("-f", "--field", help="Field name to change")
    parser.add_argument("--old-type", help="Field's old type")
    parser.add_argument("--new-type", help="Field's new type")

    args = parser.parse_args()

    asyncio.run(main(
        args.space, 
        args.schema, 
        args.field, 
        args.old_type,
        args.new_type
    ))