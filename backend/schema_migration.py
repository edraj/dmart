import argparse
import asyncio
from enum import Enum
import re
import sys
from models.enums import ContentType
from utils import helpers
from data_adapters.adapter import data_adapter as db
from models.core import Meta, Schema
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
    await db.internal_sys_update_model(
        space_name=space,
        subpath="schema",
        meta=schema_model,
        payload_dict=schema_payload,
        updates={
            "properties": schema_properties
        },
    )
    
    updated_num = 0
    
    # 4-loop over space by glob "*/.dm/*/meta.*.json"
    path = settings.spaces_folder / space
    entries_glob = "*/.dm/*/meta.*.json"
    FILE_PATTERN = re.compile("(\\w*)\\/\\.dm\\/(\\w*)\\/meta\\.([a-zA-Z]*)\\.json$")
    for one in path.glob(entries_glob):
        match = FILE_PATTERN.search(str(one))
        if not match or not one.is_file():
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
            if(
                not resource_obj.payload or
                not isinstance(resource_obj.payload.body, str) or
                resource_obj.payload.schema_shortname != schema_model.shortname
            ):
                continue
            
            # 5.1-load payload file
            resource_payload = await db.load_resource_payload(
                space_name=space,
                subpath=subpath,
                filename=resource_obj.payload.body,
                class_type=resource_cls
            )
        except Exception as ex:
            print(f"Error loading {one}", ex)
            continue
        
        resource_payload_keys = helpers.flatten_dict(resource_payload)
        if field not in resource_payload_keys or not resource_payload:
            continue
        
        # 5.2-parse field's old_type to new_type
        field_tree = field.split(".")
        last_idx = len(field_tree)-1
        main_field = resource_payload[field_tree[0]]
        field_to_update = main_field
        for i in range(1, last_idx):
            field_to_update = main_field[field_tree[i]] #type: ignore
        field_to_update[field_tree[last_idx]] = FIELD_TYPE_PARSER[new_type](field_to_update[field_tree[last_idx]])#type: ignore
        await db.internal_sys_update_model(
            space_name=space,
            subpath=subpath,
            meta=resource_obj,
            payload_dict=resource_payload,
            updates={
                field_tree[0]: main_field
            },
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
    schema_model: Schema = Schema.model_validate(
        await db.load(
            space_name=space,
            subpath="schema",
            shortname=schema,
            class_type=Schema
        )
    )
    if(
        not schema_model.payload or
        schema_model.payload.content_type != ContentType.json or
        not isinstance(schema_model.payload.body, str)
    ):
        print(f"Invalid schema file: \n{schema_model.model_dump_json()}")
        return
    schema_payload = await db.load_resource_payload(
        space_name=space,
        subpath="schema",
        filename=schema_model.payload.body,
        class_type=Schema
    )
    
    if not schema_payload: 
        return
    
    # 2-make sure field with old_type exist
    field_tree = field.split(".")
    field_definition = schema_payload
    for f in field_tree:
        field_definition = field_definition["properties"].get(f, {})
        
    if field_definition.get("type") != old_type:
        print("Invalid old type for the specified field under the specified schema")
        return
        
    field_definition["type"] = new_type
        
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
    parser.add_argument(
        "--old-type", 
        help="Field's old type, supported types: string, number, integer, array"
    )
    parser.add_argument(
        "--new-type", 
        help="Field's new type, supported types: string, number, integer, array"
    )

    args = parser.parse_args()

    asyncio.run(main(
        args.space, 
        args.schema, 
        args.field, 
        args.old_type,
        args.new_type
    ))
