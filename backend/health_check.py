#!/usr/bin/env -S BACKEND_ENV=config.env python3

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema.validators import Draft7Validator

from api.managed.router import serve_request
from models.core import EntityDTO, Folder
from utils import db
from utils.custom_validations import get_schema_path, validate_payload_with_schema
from utils.helpers import camel_case, branch_path
from models import core, api
from models.enums import ContentType, RequestType, ResourceType
from utils.regex import ATTACHMENT_PATTERN, FILE_PATTERN, IMG_EXT
from utils.settings import settings
from utils.operational_repo import operational_repo

duplicated_entries : dict= {}
key_entries: dict = {}
MAX_INVALID_SIZE = 100

# {"space_name": {"schema_name": SCHEMA_DATA_DICT}}
spaces_schemas: dict[str, dict[str, dict]] = {}


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
            params = await load_spaces_schemas(branch_name, space_param)
        else:
            params = {space_param: schemas_param}
        for space in params:
            print(f'>>>> Processing {space:<10} <<<<')
            before_time = time.time()
            health_check : dict[str, list|dict] | None = {'invalid_folders': [], 'folders_report': {}}
            for schema in params.get(space, []):
                health_check_res = await soft_health_check(space, schema, branch_name)
                if health_check_res and health_check and isinstance(health_check['folders_report'], dict):
                    health_check['folders_report'].update(health_check_res.get('folders_report', {}))
            print_health_check(health_check)
            await save_health_check_entry(health_check, space)
            print(f'Completed in: {"{:.2f}".format(time.time() - before_time)} sec')

    elif not health_type or health_type == 'hard':
        print("Running hard healthcheck")
        spaces  : dict = {space_param : {}}
        if is_full:
            spaces = await operational_repo.find_by_id("spaces")
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
    await save_duplicated_entries(branch_name)


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


async def load_spaces_schemas(branch_name: str, for_space: str | None = None) -> dict:
    global spaces_schemas
    if spaces_schemas:
        return spaces_schemas
    spaces = await operational_repo.find_by_id("spaces")
    if for_space and for_space != "all" and for_space in spaces:
        spaces_schemas[for_space] = load_space_schemas(for_space, branch_name)
        return spaces_schemas
    for space_name in spaces:
        schemas = load_space_schemas(space_name, branch_name)
        if schemas:
            spaces_schemas[space_name] = schemas
    return spaces_schemas


def load_space_schemas(space_name: str, branch_name: str) -> dict[str, dict]:
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
    global spaces_schemas
    if space_name not in spaces_schemas:
        await load_spaces_schemas(branch_name, space_name)
        
    schemas = spaces_schemas[space_name]
    
    limit = 1000
    offset = 0
    folders_report : dict = {}
    if not await operational_repo.is_index_exist(f"{space_name}:{branch_name}:{schema_name}"):
        if 'meta_schema' not in schema_name:
                print(f"can't find index: `{space_name}:{branch_name}:{schema_name}`")
        return None
    
    # searcs_res = await operational_repo.search(Query(
    #     type=QueryType.search,
    # ))

    while True:
        
        docs: list[dict[str, Any]] = await operational_repo.free_search(
            f"{space_name}:{branch_name}:{schema_name}", 
            "*",
            limit,
            offset
        )
        offset += limit
        if not docs:
            break
        for redis_doc_dict in docs:
            subpath = redis_doc_dict['subpath']
            meta_doc_content = {}
            payload_doc_content = {}
            resource_class = getattr(
                sys.modules["models.core"],
                camel_case(redis_doc_dict["resource_type"]),
            )
            system_attributes = [
                "payload_string",
                "branch_name",
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
                payload_redis_doc = await operational_repo.find_by_id(redis_doc_dict["payload_doc_id"])
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
    spaces = await operational_repo.find_by_id("spaces")
    for space_name, space_data in spaces.items():
        space_data = json.loads(space_data)
        for branch in space_data["branches"]:
            if not await operational_repo.is_index_exist(f"{space_name}:{branch}:meta"):
                continue
            
            docs: list[dict[str, Any]] = await operational_repo.free_search(
                f"{space_name}:{branch}:meta", 
                "@{key}:{value}*",
                1000
            )
            if not docs:
                continue
    
            for redis_doc_dict in docs:
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


async def hard_health_check(space_name: str, branch_name: str):
    spaces = await operational_repo.find_by_id("spaces")
    if space_name not in spaces:
        print("space name is not found")
        return None
    # remove checking check_health value from meta space
    # space_obj = core.Space.model_validate_json(spaces[space_name])
    # if not space_obj.check_health:
    #     print("EARLY EXIT")
    #     return None

    invalid_folders : list = []
    folders_report: dict[str, dict] = {}
    meta_folders_health: list = []

    path = settings.spaces_folder / space_name / branch_path(branch_name)

    subpaths = os.scandir(path)
    # print(f"{path=} {subpaths=}")
    for subpath in subpaths:
        if subpath.is_file():
            continue

        await validate_subpath_data(
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
        res['invalid_folders'] = meta_folders_health
    return res

async def health_check_entry(
    entity: EntityDTO
):
    
    entry_meta_obj = await db.load(entity)
    if entry_meta_obj.shortname != entity.shortname:
        raise Exception(
            "the shortname which got from the folder path doesn't match the shortname in the meta file."
        )
    payload_file_path = None
    if (
        entry_meta_obj.payload
        and entry_meta_obj.payload.content_type == ContentType.image
    ):
        payload_file_path = Path(f"{entity.subpath}/{entry_meta_obj.payload.body}")
        if (
            not payload_file_path.is_file()
            or not bool(
                re.match(
                    IMG_EXT,
                    entry_meta_obj.payload.body.split(".")[-1],
                )
            )
            or not os.access(payload_file_path, os.R_OK)
            or not os.access(payload_file_path, os.W_OK)
        ):
            if payload_file_path:
                raise Exception(
                    f"can't access this payload {payload_file_path}"
                )
            else:
                raise Exception(
                    f"can't access this payload {entity.subpath}"
                    f"/{entry_meta_obj.shortname}"
                )
    elif (
        entry_meta_obj.payload
        and isinstance(entry_meta_obj.payload.body, str)
        and entry_meta_obj.payload.content_type == ContentType.json
    ):
        payload_file_path = Path(f"{entity.subpath}/{entry_meta_obj.payload.body}")
        if not entry_meta_obj.payload.body.endswith(
            ".json"
        ) or not os.access(payload_file_path, os.W_OK):
            raise Exception(
                f"can't access this payload {payload_file_path}"
            )
        payload_file_content = await db.load_resource_payload(entity)
        if entry_meta_obj.payload.schema_shortname:
            await validate_payload_with_schema(
                payload_data=payload_file_content,
                space_name=entity.space_name,
                branch_name=entity.branch_name or settings.default_branch,
                schema_shortname=entry_meta_obj.payload.schema_shortname,
            )

    if(
        entry_meta_obj.payload.checksum and 
        entry_meta_obj.payload.client_checksum and 
        entry_meta_obj.payload.checksum != entry_meta_obj.payload.client_checksum
    ): 
        raise Exception(
            f"payload.checksum not equal payload.client_checksum {entity.subpath}/{entry_meta_obj.shortname}"
        )
        
async def validate_subpath_data(
    space_name: str,
    subpath: str,
    branch_name: str | None,
    user_shortname: str,
    invalid_folders: list[str],
    folders_report: dict[str, dict[str, Any]],
    meta_folders_health: list[str],
    max_invalid_size: int,
):
    """
    Params:
    @subpath: str holding the full path, ex: ../spaces/aftersales/reports

    Algorithm:
    - if subpath ends with .dm return
    - for folder in scandir(subpath)
        - if folder ends with .dm
            - get folder_meta = folder/meta.folder.json
            - validate folder_meta
            - loop over folder.entries and validate them along with theire attachments
        - else
            - call myself with subpath = folder
    """
    spaces_path_parts = str(settings.spaces_folder).split("/")
    folder_name_index = len(spaces_path_parts) + 1

    if subpath.endswith(".dm"):
        return

    subpath_folders = os.scandir(subpath)
    for folder in subpath_folders:
        if not folder.is_dir():
            continue

        if folder.name != ".dm":
            await validate_subpath_data(
                space_name,
                folder.path,
                branch_name,
                user_shortname,
                invalid_folders,
                folders_report,
                meta_folders_health,
                max_invalid_size,
            )
            continue

        folder_meta = Path(f"{folder.path}/meta.folder.json")
        folder_name = "/".join(subpath.split("/")[folder_name_index:])
        if not folder_meta.is_file():
            meta_folders_health.append(
                str(folder_meta)[len(str(settings.spaces_folder)):]
            )
            continue

        folder_meta_content = None
        folder_meta_payload = None
        try:
            folder_entity = EntityDTO(
                space_name=space_name,
                subpath=folder_name,
                shortname="",
                resource_type=ResourceType.folder,
                user_shortname=user_shortname,
                branch_name=branch_name,
            )
            folder_meta_content = await db.load(folder_entity)
            if (
                folder_meta_content.payload
                and folder_meta_content.payload.content_type == ContentType.json
            ):
                payload_path = "/"
                subpath_parts = subpath.split("/")
                if len(subpath_parts) > (len(spaces_path_parts) + 2):
                    payload_path = "/".join(
                        subpath_parts[folder_name_index:-1])
                folder_meta_payload = await db.load_resource_payload(folder_entity)
                if folder_meta_content.payload.schema_shortname:
                    await validate_payload_with_schema(
                        payload_data=folder_meta_payload,
                        space_name=space_name,
                        branch_name=branch_name or settings.default_branch,
                        schema_shortname=folder_meta_content.payload.schema_shortname,
                    )
        except Exception:
            invalid_folders.append(folder_name)

        folders_report.setdefault(folder_name, {})

        # VALIDATE FOLDER ENTRIES
        folder_entries = os.scandir(folder.path)
        for entry in folder_entries:
            if entry.is_file():
                continue

            entry_files = os.scandir(entry)
            entry_match = None
            for file in entry_files:
                if file.is_dir():
                    continue
                entry_match = FILE_PATTERN.search(file.path)

                if entry_match:
                    break

            if not entry_match:
                issue = {
                    "issues": ["meta"],
                    "uuid": "",
                    "shortname": entry.name,
                    "exception": f"Can't access this meta {subpath[len(str(settings.spaces_folder)):]}/{entry.name}",
                }

                if "invalid_entries" not in folders_report[folder_name]:
                    folders_report[folder_name]["invalid_entries"] = [issue]
                else:
                    if (
                        len(folders_report[folder_name]["invalid_entries"])
                        >= max_invalid_size
                    ):
                        break
                    folders_report[folder_name]["invalid_entries"].append(
                        issue)
                continue

            entry_shortname = entry_match.group(1)
            entry_resource_type = entry_match.group(2)

            if folder_name == "schema" and entry_shortname == "meta_schema":
                folders_report[folder_name].setdefault("valid_entries", 0)
                folders_report[folder_name]["valid_entries"] += 1
                continue

            entry_meta_obj = None
            try:
                await health_check_entry(EntityDTO(
                    space_name=space_name,
                    subpath=folder_name,
                    shortname=entry_shortname,
                    resource_type=entry_resource_type,
                    user_shortname=user_shortname,
                    branch_name=branch_name,
                ))
                    
                # VALIDATE ENTRY ATTACHMENTS
                attachments_path = f"{folder.path}/{entry_shortname}"
                attachment_folders = os.scandir(attachments_path)
                for attachment_folder in attachment_folders:
                    # i.e. attachment_folder = attachments.media
                    if attachment_folder.is_file():
                        continue

                    attachment_folder_files = os.scandir(attachment_folder)
                    for attachment_folder_file in attachment_folder_files:
                        # i.e. attachment_folder_file = meta.*.json or *.png
                        if (
                            not attachment_folder_file.is_file()
                            or not os.access(attachment_folder_file.path, os.W_OK)
                            or not os.access(attachment_folder_file.path, os.R_OK)
                        ):
                            raise Exception(
                                f"can't access this attachment {attachment_folder_file.path[len(str(settings.spaces_folder)):]}"
                            )
                        
                        attachment_match = ATTACHMENT_PATTERN.search(attachment_folder_file.path)
                        if not attachment_match:
                            # if it's the media file not its meta json file
                            continue
                        attachment_shortname = attachment_match.group(2)
                        attachment_resource_type = attachment_match.group(1)
                        await health_check_entry(EntityDTO(   
                            space_name=space_name,
                            subpath=f"{folder_name}/{entry_shortname}",
                            shortname=attachment_shortname,
                            resource_type=attachment_resource_type,
                            user_shortname=user_shortname,
                            branch_name=branch_name,
                        ))

                if "valid_entries" not in folders_report[folder_name]:
                    folders_report[folder_name]["valid_entries"] = 1
                else:
                    folders_report[folder_name]["valid_entries"] += 1
            except Exception as e:
                issue_type = "payload"
                uuid = ""
                if not entry_meta_obj:
                    issue_type = "meta"
                else:
                    uuid = str(
                        entry_meta_obj.uuid) if entry_meta_obj.uuid else ""

                issue = {
                    "issues": [issue_type],
                    "uuid": uuid,
                    "shortname": entry_shortname,
                    "resource_type": entry_resource_type,
                    "exception": str(e),
                }

                if "invalid_entries" not in folders_report[folder_name]:
                    folders_report[folder_name]["invalid_entries"] = [issue]
                else:
                    if (
                        len(folders_report[folder_name]["invalid_entries"])
                        >= max_invalid_size
                    ):
                        break
                    folders_report[folder_name]["invalid_entries"].append(
                        issue)

        if not folders_report.get(folder_name, {}):
            del folders_report[folder_name]

async def save_health_check_entry(health_check, space_name: str, branch_name: str = 'master'):
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


async def save_duplicated_entries(
    branch_name: str = settings.default_branch
):
    print('>>>> Processing UUID duplication <<<<')
    before_time = time.time()
    uuid_scanned_entries = set()
    uuid_duplicated_entries: dict = {}
    
    slug_scanned_entries = set()
    slug_duplicated_entries: dict = {}
    spaces = await operational_repo.find_by_id("spaces")
    for space_name, space_data in spaces.items():
        space_data = json.loads(space_data)
        for branch in space_data["branches"]:
            if not await operational_repo.is_index_exist(f"{space_name}:{branch}:meta"):
                continue

            offset = 0
            limit = 10000
            while True:
    
                docs: list[dict[str, Any]] = await operational_repo.free_search(
                    f"{space_name}:{branch}:meta", 
                    "*",
                    limit,
                    offset
                )
                offset += limit
                if not docs:
                    break
                for redis_doc_dict in docs:
                    if not isinstance(redis_doc_dict, dict):
                        print("Loaded document is not a proper dictionary")
                        continue
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
                    branch_name=branch_name,
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
    spaces = await operational_repo.find_by_id("spaces")
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
        entity = EntityDTO(
            space_name=settings.management_space,
            subpath="schema",
            shortname=meta.shortname,
            resource_type=ResourceType.schema,
            user_shortname="dmart",
            
        )
        await db.save(entity, meta, schema)

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
