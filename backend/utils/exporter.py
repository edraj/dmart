#!/usr/bin/env python3
import argparse
import asyncio
from hashlib import blake2b, md5
import json
import os
import shutil
import sys
import copy
import jsonschema
from aiofiles import open as aopen
from pathlib import Path

# from pydantic import config


def hashing_data(data: str, hashed_data: dict):
    hash = blake2b(salt=md5(data.encode()).digest())
    hash.update(data.encode())
    hashed_val = md5(hash.digest()).hexdigest()
    hashed_data[hashed_val] = data
    return hashed_val


def exit_with_error(msg: str):
    print("ERROR!!", msg)
    sys.exit(1)


SECURED_FIELDS = [
    "name",
    "email",
    "ip",
    "pin",
    "RechargeNumber",
    "CallingNumber",
    "shortname",
    "contact_number",
    "pin",
    "msisdn",
    "imsi",
    "sender_msisdn",
    "old_username",
    "firstname",
    "lastname",
]
OUTPUT_FOLDER_NAME = "spaces_data"

def meta_path(
    space_path: Path, 
    subpath: str, 
    file_path: str, 
    resource_type: str
) -> Path:
    return space_path / f"{subpath}/.dm/{file_path}/meta.{resource_type}.json"    

async def get_meta(
    *, 
    space_path: Path, 
    subpath: str, 
    file_path: str, 
    resource_type: str
):
    meta_content = meta_path(space_path, subpath, file_path, resource_type)
    async with aopen(meta_content, "r") as f:
        return json.loads(await f.read())


def validate_config(config_obj: dict):
    if (
        not config_obj.get("space")
        or not config_obj.get("subpath")
        or not config_obj.get("resource_type")
        or not config_obj.get("schema_shortname")
    ):
        return False
    return True


def remove_fields(src: dict, restricted_keys: list):
    for k in list(src.keys()):
        if isinstance(src[k], list):
            for item in src[k]:
                if isinstance(item, dict):
                    item = remove_fields(item, restricted_keys)
        elif isinstance(src[k], dict):
            src[k] = remove_fields(src[k], restricted_keys)
            
        if k in restricted_keys:
            del src[k]

    return src

def enc_dict(d: dict, hashed_data: dict):
    for k, v in d.items():
        if isinstance(v, dict):
            d[k] = enc_dict(v, hashed_data)
        elif isinstance(d[k], list):
            for item in d[k]:
                if isinstance(item, dict):
                    item = enc_dict(item, hashed_data)

        # if k == "msisdn":
        #     d[k] = hashing_data(str(v))
        #     try:
        #         print("ADD TO SQLLITE")
        #         cur.execute(f"INSERT INTO migrated_data VALUES('{v}', '{d[k]}')")
        #         con.commit()
        #         print("FINSIHED")
        #     except sqlite3.IntegrityError as e:
        #         if "migrated_data.hash" in str(e):  # msisdn already in db
        #             raise Exception(f"Collision on: msisdn {v}, hash {d[k]}")
        elif k in SECURED_FIELDS:
            d[k] = hashing_data(str(v), hashed_data)

    return d


def prepare_output(
    meta: dict,
    payload: dict,
    included_meta_fields: dict,
    excluded_payload_fields: dict,
):
    out = payload
    for field_meta in included_meta_fields:
        field_name = field_meta.get("field_name")
        rename_to = field_meta.get("rename_to")
        if not field_name:
            continue
        if rename_to:
            out[rename_to] = meta.get(field_name, "")
        else:
            out[field_name] = meta.get(field_name, "")

    out = remove_fields(
        out, 
        [field["field_name"] for field in excluded_payload_fields]
    )
    return out


                

async def extract(
        space : str, 
        subpath : str, # = config_obj.get("subpath")
        resource_type : str, #  = config_obj.get("resource_type")
        schema_shortname : str, #  = config_obj.get("schema_shortname")
        included_meta_fields : dict, #  = config_obj.get("included_meta_fields", [])
        excluded_payload_fields : dict, # = config_obj.get("excluded_payload_fields", [])
        spaces_path: str, 
        output_path : str, 
    entries_since = None
) -> None:
    hashed_data: dict[str, str] = {}

    space_path = Path(f"{spaces_path}/{space}")
    subpath_schema_obj = None
    with open(space_path / f"schema/{schema_shortname}.json", "r") as f:
        subpath_schema_obj = json.load(f)
    input_subpath_schema_obj = copy.deepcopy(subpath_schema_obj)

    output_subpath = Path(f"{output_path}/{OUTPUT_FOLDER_NAME}/{space}/{subpath}")
    if not output_subpath.is_dir():
        os.makedirs(output_subpath)

    # Generat output schema
    schema_fil = output_subpath / "schema.json"
    for field in included_meta_fields:
        if "oneOf" in subpath_schema_obj:
            for schema in subpath_schema_obj["oneOf"]:
                schema["properties"][field["field_name"]] = field["schema_entry"]
                if field.get("rename_to"):
                    schema["properties"][field["rename_to"]] = schema[
                        "properties"
                    ].pop(field["field_name"])
        else:
            subpath_schema_obj["properties"][field["field_name"]] = field["schema_entry"]
            if field.get("rename_to"):
                subpath_schema_obj["properties"][field["rename_to"]] = subpath_schema_obj[
                    "properties"
                ].pop(field["field_name"])
    if "oneOf" in subpath_schema_obj:
        for schema in subpath_schema_obj["oneOf"]:
            schema["properties"] = remove_fields(
                schema["properties"], 
                [field["field_name"] for field in excluded_payload_fields]
            )
    else:
        subpath_schema_obj["properties"] = remove_fields(
            subpath_schema_obj["properties"], 
            [field["field_name"] for field in excluded_payload_fields]
        )
    open(schema_fil, "w").write(json.dumps(subpath_schema_obj) + "\n")

    # Generat output content file
    data_file = output_subpath / "data.ljson"
    path = os.path.join(spaces_path, space, subpath)
    for file_name in os.listdir(path):
        if not file_name.endswith(".json"):
            continue
        if entries_since:
            payload_ts = int(round(
                os.path.getmtime(os.path.join(path, file_name)) * 1000
            ))
            meta_ts = int(round(os.path.getmtime(meta_path(
                space_path, 
                subpath, 
                file_name.split(".")[0], 
                resource_type
            )) * 1000))
            if payload_ts <= entries_since and meta_ts <= entries_since:
                continue
            
        async with aopen(os.path.join(path, file_name), "r") as f:
            content = await f.read()
        try:
            payload = json.loads(content)
            jsonschema.validate(
                instance=payload, schema=input_subpath_schema_obj
            )
            meta = await get_meta(
                space_path=space_path,
                subpath=subpath,
                file_path=file_name.split(".")[0],
                resource_type=resource_type,
            )
        except Exception:
            # print(f"ERROR: {error.args = }")
            continue

        out = prepare_output(
            meta, payload, included_meta_fields, excluded_payload_fields
        )

        # jsonschema.validate(instance=out, schema=subpath_schema_obj)

        encrypted_out = enc_dict(out, hashed_data)
        open(data_file, "a").write(json.dumps(encrypted_out) + "\n")
        
    open(f"{output_subpath}/hashed_data.json", "w").write(json.dumps(hashed_data))
        


async def main(tasks):
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", required=True, help="Json config relative path from the script"
    )
    parser.add_argument(
        "--spaces", required=True, help="Spaces relative path from the script"
    )
    parser.add_argument(
        "--output",
        help="Output relative path from the script (the default path is the current script path",
    )
    parser.add_argument(
        "--since",
        help="Export entries created/updated since the provided timestamp",
    )
    args = parser.parse_args()
    since = None
    output_path = ""
    if args.output:
        output_path = args.output
        
    if args.since:
        since = int(round(float(args.since) * 1000))

    if not os.path.isdir(args.spaces):
        exit_with_error(f"The spaces folder {args.spaces} is not found.")

    out_path = os.path.join(output_path, OUTPUT_FOLDER_NAME)
    if os.path.isdir(out_path):
        shutil.rmtree(out_path)

    # con = sqlite3.connect(f"../../exporter_data/output/data.db")
    # cur = con.cursor()
    # cur.execute("DROP TABLE IF EXISTS migrated_data")
    # cur.execute(
    #     "CREATE TABLE migrated_data(hash VARCHAR UNIQUE, msisdn VARCHAR UNIQUE)"
    # )
    # print(con)

    tasks = []
    with open(args.config, "r") as f:
        config_objs = json.load(f)

    for config_obj in config_objs:
        if not validate_config(config_obj):
            continue
        tasks.append(extract(config_obj.get("space", ""), 
                             config_obj.get("subpath", ""), 
                             config_obj.get("resource_type", ""), 
                             config_obj.get("schema_shortname", ""), 
                             config_obj.get("included_meta_fields", {}), 
                             config_obj.get("excluded_payload_fields", {}), 
                             args.spaces, output_path, since))

    asyncio.run(main(tasks))

    print(
        f"Output path: {os.path.abspath(os.path.join(output_path, OUTPUT_FOLDER_NAME))}"
    )
