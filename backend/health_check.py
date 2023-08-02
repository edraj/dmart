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

from jsonschema.validators import Draft4Validator
from redis.commands.search.query import Query
from redis.commands.search.result import Result

from api.managed.router import serve_request
from models.core import Folder
from utils import repository, db
from utils.custom_validations import get_schema_path
from utils.helpers import camel_case, branch_path
from utils.redis_services import RedisServices
from models import core, api
from models.enums import ContentType, RequestType, ResourceType
from utils.settings import settings
from utils.spaces import get_spaces

duplicated_entries = {}
key_entries: dict = {}
MAX_INVALID_SIZE = 3


async def main(health_type: str, space_param: str, schemas_param: list, branch_name: str):
    await cleanup_spaces()
    is_full: bool = True if not args.space or args.space == 'all' else False
    print_header()
    if health_type == 'soft':
        print("Running soft healthcheck")
        if not schemas_param and not is_full:
            print('Add the space name and at least one schema')
            return
        if is_full:
            params = await load_spaces_schemas_names(branch_name)
        else:
            params = {space_param: schemas_param}
        for space in params:
            print(f'>>>> Processing {space:<10} <<<<')
            before_time = time.time()
            health_check = {'invalid_folders': [], 'folders_report': {}}
            for schema in params.get(space, []):
                health_check_res = await soft_health_check(space, schema, branch_name)
                if health_check_res:
                    health_check['folders_report'].update(health_check_res.get('folders_report', {}))
            print_health_check(health_check)
            await save_health_check_entry(health_check, space)
            print(f'Completed in: {"{:.2f}".format(time.time() - before_time)} sec')

    elif not health_type or health_type == 'hard':
        print("Running hard healthcheck")
        spaces = [space_param]
        if is_full:
            spaces = await get_spaces()
        for space in spaces:
            print(f'>>>> Processing {space:<10} <<<<')
            before_time = time.time()
            health_check = await hard_health_check(space, branch_name)
            if health_check:
                await save_health_check_entry(health_check, space)
            print_health_check(health_check)
            print(f'Completed in: {"{:.2f}".format(time.time() - before_time)} sec')
    else:
        print("Wrong mode specify [soft or hard]")
        return
    await save_duplicated_entries()


def print_header():
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
                print(f"\t\t\t\tInvalid item/issues: {one.get('shortname', 'n/a')}/{','.join(one.get('issues', []))}")


async def load_spaces_schemas_names(branch_name):
    result: dict = {}
    spaces = await get_spaces()
    for space_name in spaces:
        schemas = [schema for schema in load_space_schemas(space_name, branch_name)]
        if schemas:
            result[space_name] = schemas
    return result


def load_space_schemas(space_name: str, branch_name: str):
    schemas: dict = {}
    schemas_path = Path(settings.spaces_folder / space_name / "schema" / ".dm")
    if not schemas_path.is_dir():
        return {}
    for entry in os.scandir(schemas_path):
        if entry.is_dir():
            schema_path_meta = Path(schemas_path / entry.name / "meta.schema.json")
            if schema_path_meta.is_file():
                schema_meta = json.loads(schema_path_meta.read_text())
                if schema_meta.get("payload", {}).get('body'):
                    schema_path_body = get_schema_path(
                        space_name=space_name,
                        branch_name=branch_name,
                        schema_shortname=schema_meta.get("payload").get('body'),
                    )
                    if schema_path_body.is_file():
                        schemas[schema_meta['shortname']] = json.loads(schema_path_body.read_text())
    return schemas


async def soft_health_check(
        space_name: str,
        schema_name: str,
        branch_name: str = settings.default_branch
):
    schemas = load_space_schemas(space_name, branch_name)
    limit = 1000
    offset = 0
    folders_report = {}
    async with RedisServices() as redis:
        while True:
            try:
                ft_index = redis.client.ft(f"{space_name}:{branch_name}:{schema_name}")
                await ft_index.info()
            except Exception as _:
                if 'meta_schema' not in schema_name:
                    print(f"can't find index: `{space_name}:{branch_name}:{schema_name}`")
                return None
            search_query = Query(query_string="*")
            search_query.paging(offset, limit)
            offset += limit
            res_data: Result = await ft_index.search(query=search_query) #type: ignore
            if not res_data.docs:
                break
            for redis_doc_dict in res_data.docs:
                redis_doc_dict = json.loads(redis_doc_dict.json)
                subpath = redis_doc_dict['subpath']
                meta_doc_content = {}
                payload_doc_content = {}
                resource_class = getattr(
                    sys.modules["models.core"],
                    camel_case(redis_doc_dict["resource_type"]),
                )
                system_attributes = [
                    "branch_name",
                    "query_policies",
                    "subpath",
                    "resource_type",
                    "meta_doc_id",
                    "payload_doc_id",
                ]
                class_fields = resource_class.__fields__.keys()
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
                    meta = resource_class.parse_obj(meta_doc_content)
                except Exception as ex:
                    status['is_valid'] = False
                    status['invalid']['exception'] = str(ex)
                    status['invalid']['issues'].append('meta')
                if meta:
                    try:
                        if meta.payload and meta.payload.schema_shortname and payload_doc_content is not None:
                            schema_dict: dict = schemas.get(meta.payload.schema_shortname, {})
                            if schema_dict:
                                Draft4Validator(schema_dict).validate(payload_doc_content)
                            else:
                                continue
                        if folders_report[subpath].get('valid_entries'):
                            folders_report[subpath]['valid_entries'] += 1
                        else:
                            folders_report[subpath]['valid_entries'] = 1
                        status['is_valid'] = True
                    except Exception as ex:
                        status['is_valid'] = False
                        status['invalid']['exception'] = str(ex)
                        status['invalid']['issues'].append('payload')

                if not status['is_valid']:
                    if not folders_report.get(subpath, {}).get('invalid_entries'):
                        folders_report[subpath]['invalid_entries'] = []
                    if meta_doc_content["shortname"] not in folders_report[redis_doc_dict['subpath']]["invalid_entries"]:
                        if len(folders_report[redis_doc_dict['subpath']]["invalid_entries"]) >= MAX_INVALID_SIZE:
                            break
                        folders_report[redis_doc_dict['subpath']]["invalid_entries"].append(status.get('invalid'))

                uuid = redis_doc_dict['uuid'][:8]
                await collect_duplicated_with_key('uuid', uuid)
                if redis_doc_dict.get('slug'):
                    await collect_duplicated_with_key('slug', redis_doc_dict.get('slug'))

    return {"invalid_folders": [], "folders_report": folders_report}


async def collect_duplicated_with_key(key, value):
    spaces = await get_spaces()
    async with RedisServices() as redis:
        for space_name, space_data in spaces.items():
            space_data = json.loads(space_data)
            for branch in space_data["branches"]:
                try:
                    ft_index = redis.client.ft(f"{space_name}:{branch}:meta")
                    await ft_index.info()
                except:
                    continue
                search_query = Query(query_string=f"@{key}:{value}*")
                search_query.paging(0, 1000)
                res_data: Result = await ft_index.search(query=search_query) #type: ignore
                for redis_doc_dict in res_data.docs:
                    redis_doc_dict = json.loads(redis_doc_dict.json)
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


async def hard_health_check(space_name: str, branch_name: str):
    spaces = await get_spaces()
    if space_name not in spaces:
        print("space name is not found")
        return None
    # remove checking check_health value from meta space
    # space_obj = core.Space.parse_raw(spaces[space_name])
    # if not space_obj.check_health:
    #     print("EARLY EXIT")
    #     return None

    invalid_folders = []
    folders_report: dict[str, dict] = {}
    meta_folders_health: list = []

    path = settings.spaces_folder / space_name / branch_path(branch_name)

    subpaths = os.scandir(path)
    # print(f"{path=} {subpaths=}")
    for subpath in subpaths:
        if subpath.is_file():
            continue

        await repository.validate_subpath_data(
            space_name=space_name,
            subpath=subpath.path,
            branch_name=branch_name,
            user_shortname='dmart',
            invalid_folders=invalid_folders,
            folders_report=folders_report,
            meta_folders_health=meta_folders_health,
            max_invalid_size=MAX_INVALID_SIZE
        )
    res = {"invalid_folders": invalid_folders, "folders_report": folders_report}
    if meta_folders_health:
        res['invalid_meta_folders'] = meta_folders_health
    return res


async def save_health_check_entry(health_check, space_name: str, branch_name: str = 'master'):
    request_type = RequestType.create
    entry_path = Path(settings.spaces_folder / "management/health_check/.dm" / space_name / "meta.content.json")
    if entry_path.is_file():
        request_type = RequestType.update
    await serve_request(
        request=api.Request(
            space_name="management",
            request_type=request_type,
            records=[
                core.Record(
                    resource_type=ResourceType.content,
                    shortname=space_name,
                    subpath="/health_check",
                    branch_name=branch_name,
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


async def save_duplicated_entries(branch_name: str = 'master'):
    entry_path = Path(settings.spaces_folder / "management/health_check/.dm/duplicated_entries/meta.content.json")
    request_type = RequestType.create
    if entry_path.is_file():
        request_type = RequestType.update
    await serve_request(
        request=api.Request(
            space_name="management",
            request_type=request_type,
            records=[
                core.Record(
                    resource_type=ResourceType.content,
                    shortname="duplicated_entries",
                    subpath="/health_check",
                    branch_name=branch_name,
                    attributes={
                        "is_active": True,
                        "updated_at": str(datetime.now()),
                        "payload": {
                            "schema_shortname": "health_check",
                            "content_type": ContentType.json,
                            "body": {"entries": duplicated_entries}
                        }
                    },
                )
            ],
        ),
        owner_shortname='dmart',
    )



async def cleanup_spaces():
    spaces = await get_spaces()
    # create health check path meta
    folder_path = Path(settings.spaces_folder / "management/health_check/.dm")
    if not os.path.isdir(folder_path):
        os.makedirs(folder_path)
    file_path = Path(folder_path / "meta.folder.json")
    # create meta folder
    if not os.path.isfile(file_path):
        meta_obj = Folder(shortname="health_check", is_active=True, owner_shortname='dmart')
        with open(file_path, "w") as f:
            f.write(meta_obj.json(exclude_none=True))
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
                body=f"health_check.json",
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
        await db.save("management", "schema", meta, settings.default_branch)
        await db.save_payload_from_json("management", "schema", meta, schema, settings.default_branch)

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
    parser.add_argument("-b", "--branch", help="target a specific branch")
    parser.add_argument("-m", "--schemas", nargs="*", help="hit the target schema inside the space")

    args = parser.parse_args()
    if not args.branch:
        args.branch = settings.default_branch
    before_time = time.time()
    asyncio.run(main(args.type, args.space, args.schemas, args.branch))
    print(f'total time: {"{:.2f}".format(time.time() - before_time)} sec')
