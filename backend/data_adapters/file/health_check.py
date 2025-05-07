#!/usr/bin/env -S BACKEND_ENV=config.env python3

import argparse
import asyncio
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from jsonschema.validators import Draft7Validator
from redis.commands.search.query import Query
from redis.commands.search.result import Result

from api.managed.router import serve_request
from models.core import Folder
from utils import repository
from data_adapters.adapter import data_adapter as db
from data_adapters.file.custom_validations import get_schema_path
from utils.helpers import camel_case
from data_adapters.file.redis_services import RedisServices
from models import core, api
from models.enums import ContentType, RequestType, ResourceType
from utils.settings import settings

duplicated_entries : dict= {}

key_entries: dict = {}
MAX_INVALID_SIZE = 100

# {"space_name": {"schema_name": SCHEMA_DATA_DICT}}
spaces_schemas: dict[str, dict[str, dict]] = {}


async def main(health_type: str, space_param: str, schemas_param: list):
    try:
        spaces = await db.get_spaces()
        if space_param != "all" and space_param not in spaces:
            print("space name is not found")
            return
        if space_param == "all":
            for space in spaces:
                await main(health_type, space, schemas_param)
                return
        space_obj = core.Space.model_validate_json(spaces[space_param])
        if not space_obj.check_health:
            print(f"EARLY EXIT, health check disabled for space {space_param}")
            return
        
        await cleanup_spaces()
        is_full: bool = True if not args.space or args.space == 'all' else False
        print_header()
        if health_type == 'soft':
            print("Running soft healthcheck")
            if not schemas_param and not is_full:
                print('Add the space name and at least one schema')
                return
            if is_full:
                params = await load_spaces_schemas(space_param)
            else:
                params = {space_param: schemas_param}
            for space in params:
                print(f'>>>> Processing {space:<10} <<<<')
                before_time = time.time()
                health_check : dict[str, list|dict] | None = {'invalid_folders': [], 'folders_report': {}}
                for schema in params.get(space, []):
                    health_check_res = await soft_health_check(space, schema)
                    if health_check_res and health_check and isinstance(health_check['folders_report'], dict):
                        health_check['folders_report'].update(health_check_res.get('folders_report', {}))
                print_health_check(health_check)
                await save_health_check_entry(health_check, space)
                print(f'Completed in: {"{:.2f}".format(time.time() - before_time)} sec')

        elif not health_type or health_type == 'hard':
            print("Running hard healthcheck")
            spaces = {space_param : {}}
            if is_full:
                spaces = await db.get_spaces()
            for space in spaces:
                print(f'>>>> Processing {space:<10} <<<<')
                before_time = time.time()
                health_check = await hard_health_check(space)
                if health_check:
                    await save_health_check_entry(health_check, space)
                print_health_check(health_check)
                print(f'Completed in: {"{:.2f}".format(time.time() - before_time)} sec')
        else:
            print("Wrong mode specify [soft or hard]")
            return
        await save_duplicated_entries()
    finally:
        await RedisServices().close_pool()


def print_header() -> None:
    print("{:<32} {:<6} {:<6}".format(
        'subpath',
        'valid',
        'invalid')
    )


def print_health_check(health_check):
    if health_check:
        for schema_path, val in health_check.get('folders_report', {}).items():
            valid = val.get('valid_entries', 0)
            invalid = len(val.get('invalid_entries', []))
            print("{:<32} {:<6} {:<6}".format(
                schema_path,
                valid,
                invalid)
            )
            for one in val.get("invalid_entries", []):
                print(f"\t\t\t\tInvalid item/issues: {one.get('shortname', 'n/a')}/"
                      f"{','.join(one.get('issues', []))} - {one.get('exception','')}")
    if health_check.get('invalid_folders'):
        print('Invalid folders :')
    for val in health_check.get('invalid_folders'):
        print(f"\t\t\t\t {val}")


async def load_spaces_schemas(for_space: str | None = None) -> dict:
    global spaces_schemas
    if spaces_schemas:
        return spaces_schemas
    spaces = await db.get_spaces()
    if for_space and for_space != "all" and for_space in spaces:
        spaces_schemas[for_space] = load_space_schemas(for_space)
        return spaces_schemas
    for space_name in spaces:
        schemas = load_space_schemas(space_name)
        if schemas:
            spaces_schemas[space_name] = schemas
    return spaces_schemas


def load_space_schemas(space_name: str) -> dict[str, dict]:
    schemas: dict[str, dict] = {}
    schemas_path = Path(settings.spaces_folder / space_name / "schema" / ".dm")
    if not schemas_path.is_dir():
        return {}
    for entry in os.scandir(schemas_path):
        if not entry.is_dir():
            continue

        schema_path_meta = Path(schemas_path / entry.name / "meta.schema.json")
        if not schema_path_meta.is_file():
            continue
        
        schema_meta = json.loads(schema_path_meta.read_text())
        if schema_meta.get("payload", {}).get('body'):
            schema_path_body = get_schema_path(
                space_name=space_name,
                schema_shortname=schema_meta.get("payload").get('body'),
            )
            if schema_path_body.is_file():
                schemas[schema_meta['shortname']] = json.loads(schema_path_body.read_text())
    return schemas


async def soft_health_check(
        space_name: str,
        schema_name: str,
):
    global spaces_schemas
    if space_name not in spaces_schemas:
        await load_spaces_schemas(space_name)
        
    schemas = spaces_schemas[space_name]
    
    limit = 1000
    offset = 0
    folders_report : dict = {}
    async with RedisServices() as redis:
        try:
            ft_index = redis.ft(f"{space_name}:{schema_name}")
            await ft_index.info()
        except Exception:
            if 'meta_schema' not in schema_name:
                print(f"can't find index: `{space_name}:{schema_name}`")
            return None
        while True:
            search_query = Query(query_string="*")
            search_query.paging(offset, limit)
            offset += limit
            x = await ft_index.search(query=search_query)  # type: ignore
            if x and isinstance(x, dict) and "results" in x:
                res_data : list = [one["extra_attributes"]["$"] for one in x["results"] if "extra_attributes" in one]
                if not res_data:
                    break
            else: 
                break
            for redis_doc_dict in res_data:
                redis_doc_dict = json.loads(redis_doc_dict)
                subpath = redis_doc_dict['subpath']
                meta_doc_content = {}
                payload_doc_content = {}
                resource_class = getattr(
                    sys.modules["models.core"],
                    camel_case(redis_doc_dict["resource_type"]),
                )
                system_attributes = [
                    "payload_string",
                    "query_policies",
                    "subpath",
                    "resource_type",
                    "meta_doc_id",
                    "payload_doc_id",
                ]
                class_fields = resource_class.model_fields.keys()
                for key, value in redis_doc_dict.items():
                    if key in class_fields:
                        meta_doc_content[key] = value
                    elif key not in system_attributes:
                        payload_doc_content[key] = value

                if not payload_doc_content and redis_doc_dict.get("payload_doc_id"):
                    payload_redis_doc = await redis.get_doc_by_id(
                        redis_doc_dict["payload_doc_id"]
                    )
                    if payload_redis_doc:
                        not_payload_attr = system_attributes + list(class_fields)
                        for key, value in payload_redis_doc.items():
                            if key not in not_payload_attr:
                                payload_doc_content[key] = value

                meta_doc_content["created_at"] = datetime.fromtimestamp(
                    meta_doc_content["created_at"]
                )
                meta_doc_content["updated_at"] = datetime.fromtimestamp(
                    meta_doc_content["updated_at"]
                )
                if not folders_report.get(subpath):
                    folders_report[subpath] = {}

                meta = None
                status = {
                    'is_valid': True,
                    "invalid": {
                        "issues": [],
                        "uuid": redis_doc_dict.get("uuid"),
                        "shortname": redis_doc_dict.get("shortname"),
                        "resource_type": redis_doc_dict["resource_type"],
                        "exception": ""
                    }
                }
                try:
                    meta = resource_class.model_validate(meta_doc_content)
                except Exception as ex:
                    status['is_valid'] = False
                    if not isinstance(status, dict) and isinstance(status["invalid"], dict):
                        status['invalid']['exception'] = str(ex)
                        status['invalid']['issues'].append('meta')
                if meta:
                    try:
                        if meta.payload and meta.payload.schema_shortname and payload_doc_content is not None:
                            schema_dict: dict = schemas.get(meta.payload.schema_shortname, {})
                            if schema_dict:
                                Draft7Validator(schema_dict).validate(payload_doc_content)
                            else:
                                continue
                        if(
                            meta.payload.checksum and 
                            meta.payload.client_checksum and 
                            meta.payload.checksum != meta.payload.client_checksum
                        ): 
                            raise Exception(
                                f"payload.checksum not equal payload.client_checksum {subpath}/{meta.shortname}"
                            )
                        if folders_report[subpath].get('valid_entries'):
                            folders_report[subpath]['valid_entries'] += 1
                        else:
                            folders_report[subpath]['valid_entries'] = 1
                        status['is_valid'] = True
                    except Exception as ex:
                        status['is_valid'] = False
                        if not isinstance(status, dict) and isinstance(status["invalid"], dict):
                            status['invalid']['exception'] = str(ex)
                            status['invalid']['issues'].append('payload')

                if not status['is_valid']:
                    if not folders_report.get(subpath, {}).get('invalid_entries'):
                        folders_report[subpath]['invalid_entries'] = []
                    if meta_doc_content["shortname"] not in folders_report[redis_doc_dict['subpath']]["invalid_entries"]:
                        if len(folders_report[redis_doc_dict['subpath']]["invalid_entries"]) >= MAX_INVALID_SIZE:
                            break
                        folders_report[redis_doc_dict['subpath']]["invalid_entries"].append(status.get('invalid'))

                # uuid = redis_doc_dict['uuid'][:8]
                # await collect_duplicated_with_key('uuid', uuid)
                # if redis_doc_dict.get('slug'):
                #     await collect_duplicated_with_key('slug', redis_doc_dict.get('slug'))

    return {"invalid_folders": [], "folders_report": folders_report}


async def collect_duplicated_with_key(key, value) -> None:
    spaces = await db.get_spaces()
    async with RedisServices() as redis:
        for space_name, space_data in spaces.items():
            space_data = json.loads(space_data)
            try:
                ft_index = redis.ft(f"{space_name}:meta")
                await ft_index.info()
            except Exception:
                continue
            search_query = Query(query_string=f"@{key}:{value}*")
            search_query.paging(0, 1000)
            x = await ft_index.search(query=search_query) # type: ignore
            if x and isinstance(x, Result):
                res_data: Result = x
                for redis_doc_dict in res_data.docs:
                    redis_doc_dict = json.loads(redis_doc_dict.json)
                    if isinstance(redis_doc_dict, dict):
                        if redis_doc_dict['subpath'] == '/':
                            redis_doc_dict['subpath'] = ''
                        loc = space_name + "/" + redis_doc_dict['subpath']
                        if key not in key_entries:
                            key_entries[key] = {}
                        if not key_entries[key].get(value):
                            key_entries[key][value] = loc
                        else:
                            if not duplicated_entries.get(key):
                                duplicated_entries[key] = {}
                            if not duplicated_entries[key].get(value) or \
                                    key_entries[key][value] not in duplicated_entries[key][value]['loc']:
                                duplicated_entries[key][value] = {}
                                duplicated_entries[key][value]['loc'] = [key_entries[key][value]]
                                duplicated_entries[key][value]['total'] = 1
                            if loc not in duplicated_entries[key][value]['loc']:
                                duplicated_entries[key][value]['total'] += 1
                                duplicated_entries[key][value]['loc'].append(loc)


async def hard_health_check(space_name: str):
    spaces = await db.get_spaces()
    if space_name not in spaces:
        print("space name is not found")
        return None
    # remove checking check_health value from meta space
    # space_obj = core.Space.model_validate_json(spaces[space_name])
    # if not space_obj.check_health:
    #     print(f"EARLY EXIT, health check disabled for space {space_name}")
    #     return None

    invalid_folders : list = []
    folders_report: dict[str, dict] = {}
    meta_folders_health: list = []

    path = settings.spaces_folder / space_name

    subpaths = os.scandir(path)
    # print(f"{path=} {subpaths=}")
    for subpath in subpaths:
        if subpath.is_file():
            continue

        await repository.validate_subpath_data(
            space_name=space_name,
            subpath=subpath.path,
            user_shortname='dmart',
            invalid_folders=invalid_folders,
            folders_report=folders_report,
            meta_folders_health=meta_folders_health,
            max_invalid_size=MAX_INVALID_SIZE
        )
    res = {"invalid_folders": invalid_folders, "folders_report": folders_report}
    if meta_folders_health:
        res['invalid_folders'] = meta_folders_health
    return res


async def save_health_check_entry(health_check, space_name: str):
    meta_path = Path(settings.spaces_folder / "management/health_check/.dm" / space_name)
    entry_path = Path(settings.spaces_folder / "management/health_check" / f"{space_name}.json")
    if meta_path.is_dir():
        shutil.rmtree(meta_path)
    if entry_path.is_file():
        os.remove(entry_path)
    await serve_request(
        request=api.Request(
            space_name="management",
            request_type=RequestType.create,
            records=[
                core.Record(
                    resource_type=ResourceType.content,
                    shortname=space_name,
                    subpath="/health_check",
                    attributes={
                        "is_active": True,
                        "updated_at": str(datetime.now()),
                        "payload": {
                            "schema_shortname": "health_check",
                            "content_type": ContentType.json,
                            "body": health_check
                        }
                    },
                )
            ],
        ),
        owner_shortname='dmart',
    )


async def save_duplicated_entries() -> None:
    print('>>>> Processing UUID duplication <<<<')
    before_time = time.time()
    uuid_scanned_entries: set = set()
    uuid_duplicated_entries: dict = {}
    
    slug_scanned_entries = set()
    slug_duplicated_entries: dict = {}
    spaces : dict = await db.get_spaces()
    async with RedisServices() as redis:
        for space_name, space_data in spaces.items():
            space_data = json.loads(space_data)
            try:
                ft_index = redis.ft(f"{space_name}:meta")
                index_info = await ft_index.info() # type: ignore
            except Exception:
                continue
            for i in range(0, int(index_info["num_docs"]), 10000):  # type: ignore
                search_query = Query(query_string="*")
                search_query.paging(i, 10000)
                x = await ft_index.search(query=search_query) # type: ignore
                if x and isinstance(x, dict) and "results" in x:
                    res_data : list = [ one["extra_attributes"]["$"] for one in x["results"] if 'extra_attributes' in one]
                    for redis_doc_dict in res_data:
                        redis_doc_dict = json.loads(redis_doc_dict)
                        if isinstance(redis_doc_dict, dict):
                            if "uuid" in redis_doc_dict:
                                # Handle UUID
                                if "uuid" in redis_doc_dict and redis_doc_dict["uuid"] in uuid_scanned_entries:
                                    short_uuid = redis_doc_dict["uuid"][:8]
                                    uuid_duplicated_entries.setdefault(
                                        short_uuid, {"loc": [], "total": 0}
                                    )
                                    uuid_duplicated_entries[short_uuid]["loc"].append(
                                        space_name + "/" + redis_doc_dict['subpath'] + "/" + redis_doc_dict['shortname']
                                    )
                                    uuid_duplicated_entries[short_uuid]["total"]+=1
                                else:
                                    uuid_scanned_entries.add(redis_doc_dict["uuid"])
                            else:
                                print ("UUID is missing", redis_doc_dict)
                        
                            # Handle Slug
                            if "slug" in redis_doc_dict and redis_doc_dict["slug"] in slug_scanned_entries:
                                slug_duplicated_entries.setdefault(
                                    "slug", {"loc": [], "total": 0}
                                )
                                slug_duplicated_entries["slug"]["loc"].append(
                                    space_name + "/" + redis_doc_dict['subpath'] + "/" + redis_doc_dict['shortname']
                                )
                                slug_duplicated_entries["slug"]["total"]+=1
                            elif "slug" in redis_doc_dict:
                                slug_scanned_entries.add(redis_doc_dict["slug"])
                        else:
                            print("Loaded document is not a proper dictionary")
                        
                        


    entry_path = Path(settings.spaces_folder / "management/health_check/.dm/duplicated_entries/meta.content.json")
    request_type = RequestType.create
    if entry_path.is_file():
        request_type = RequestType.update
    await serve_request(
        request=api.Request(
            space_name=settings.management_space,
            request_type=request_type,
            records=[
                core.Record(
                    resource_type=ResourceType.content,
                    shortname="duplicated_entries",
                    subpath="/health_check",
                    attributes={
                        "is_active": True,
                        "updated_at": str(datetime.now()),
                        "payload": {
                            "schema_shortname": "health_check",
                            "content_type": ContentType.json,
                            "body": {
                                "entries": {
                                    "uuid": uuid_duplicated_entries,
                                    "slug": slug_duplicated_entries
                                }
                            }
                        }
                    },
                )
            ],
        ),
        owner_shortname='dmart',
    )
    
    print(f'Completed in: {"{:.2f}".format(time.time() - before_time)} sec')
    

async def cleanup_spaces() -> None:
    spaces = await db.get_spaces()
    # create health check path meta
    folder_path = Path(settings.spaces_folder / "management/health_check/.dm")
    if not os.path.isdir(folder_path):
        os.makedirs(folder_path)
    file_path = Path(folder_path / "meta.folder.json")
    # create meta folder
    if not os.path.isfile(file_path):
        meta_obj = Folder(shortname="health_check", is_active=True, owner_shortname='dmart')
        with open(file_path, "w") as f:
            f.write(meta_obj.model_dump_json(exclude_none=True))
    # create health check schema
    if (
            not os.path.isfile(Path(settings.spaces_folder / "management/schema/health_check.json")) or
            not os.path.isfile(Path(settings.spaces_folder / "management/schema/.dm/health_check/meta.schema.json"))
    ):
        meta = core.Schema(
            shortname="health_check",
            is_active=True,
            owner_shortname="dmart",
            payload=core.Payload(
                content_type=ContentType.json,
                body="health_check.json",
            ),
        )
        schema = {
            "type": "object",
            "title": "health_check",
            "additionalProperties": True,
            "properties": {
            },
            "required": []
        }
        await db.save("management", "schema", meta)
        await db.save_payload_from_json("management", "schema", meta, schema)

    # clean up entries
    for folder_name in os.listdir(folder_path):
        if not os.path.isdir(os.path.join(folder_path, folder_name)):
            continue
        if folder_name not in spaces:
            shutil.rmtree(Path(folder_path / folder_name))
            os.remove(Path(settings.spaces_folder / "management/health_check" / f"{folder_name}.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="This created for doing health check functionality",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-t", "--type", help="type of health check (soft or hard)")
    parser.add_argument("-s", "--space", help="hit the target space or pass (all) to make the full health check")
    parser.add_argument("-m", "--schemas", nargs="*", help="hit the target schema inside the space")

    args = parser.parse_args()
    before_time = time.time()
    asyncio.run(main(args.type, args.space or "all", args.schemas))
    print(f'total time: {"{:.2f}".format(time.time() - before_time)} sec')
