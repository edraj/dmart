#!/usr/bin/env -S BACKEND_ENV=config.env python3

import argparse
import asyncio
import json
import re
import traceback
from typing import Any
from db.manticore_db import ManticoreDB
from models.api import Query
from models.core import EntityDTO, Locator, Space, Meta
from models.enums import ContentType, QueryType, ResourceType
from utils.bootstrap import bootstrap_all
from utils.custom_validations import validate_payload_with_schema
from utils.helpers import branch_path, divide_chunks
from utils.operational_repo import operational_repo
from utils.operational_database import operational_db
from utils.settings import settings
from utils import regex
from utils import db
from multiprocessing import Pool
from jsonschema.exceptions import ValidationError as SchemaValidationError
from copy import copy


async def load_data_to_redis(
    space_name, 
    branch_name, 
    subpath, 
    allowed_resource_types
) -> dict:
    """
    Load meta files inside subpath then store them to redis as :space_name:meta prefixed doc,
    and if the meta file has a separate payload file follwing a schema 
    we loads the payload content and store it to redis as :space_name:schema_name prefixed doc
    """
    # start_time: int = int(time())

    #print(f"\n\nSTART EXAMINING SUBPATH: {subpath}  {int(time()) - start_time} ")

    locators_len, locators = db.locators_query(
        Query(
            space_name=space_name,
            branch_name=branch_name,
            subpath=subpath,
            type=QueryType.subpath,
            limit=10000000,
            filter_types=allowed_resource_types,
        )
    )

    # Add Folder locator to the loaded locators
    folder_meta = settings.spaces_folder / space_name / subpath / ".dm/meta.folder.json"
    if ResourceType.folder in allowed_resource_types and  folder_meta.is_file():
        folder_parts = subpath.split("/")
        folder_locator = Locator(
            type=ResourceType.folder,
            space_name=space_name,
            branch_name=branch_name,
            subpath="/".join(folder_parts[:-1]) or "/",
            shortname=folder_parts[-1]
        )
        locators.append(folder_locator)
        locators_len += 1

    # print(f"\nEnded loading {locators_len} files, starting parsing data in each file {int(time()) - start_time}")

    if locators_len <= 5000:
        db_docs_chunks = [await generate_db_docs(locators)]
    else:
        with Pool() as pool:
            multiple_results = [
                pool.apply_async(generate_db_docs_process, (locators_chunk, )) 
                for locators_chunk in divide_chunks(locators, 5000)
            ]
            db_docs_chunks = [process_res.get() for process_res in multiple_results]

    
    saved_docs_count = 0
    #print(f"""
    #    Completed parsing {locators_len} files, 
    #    generated {len(db_docs_chunks)} chunks of docs to be stored in Redis, 
    #    time: {int(time()) - start_time}
    #""")
    
    for db_docs_chunk in db_docs_chunks:
        for schema, chunk in db_docs_chunk.items():
            saved_docs_count += await operational_repo.save_bulk(f"{space_name}__{branch_name}__{schema}", chunk)

    # pp(subpath=subpath, saved_docs_count=saved_docs_count)
    # x = 1/0
    return {"subpath": subpath, "documents": saved_docs_count}

def generate_db_docs_process(locators: list):
    return asyncio.run(generate_db_docs(locators))

async def generate_db_docs(locators: list) -> dict[str, list[Any]]:
    db_docs: dict[str, list[Any]] = {
        "meta": [],
    }
    for one in locators:
        try:
            # print(f"{one=}")

            dto = EntityDTO(
                space_name=one.space_name,
                branch_name=one.branch_name,
                subpath=one.subpath,
                shortname=one.shortname,
                user_shortname="anonymous",
                resource_type=one.type
            )
            meta: Meta | None = await db.load_or_none(dto) #type: ignore
            if not meta:
                continue
            
            meta_doc_id, meta_data = await operational_db.prepare_meta_doc(
                one.space_name, one.branch_name, one.subpath, meta
            )
            payload_data = {}
            if (
                meta.payload
                and isinstance(meta.payload.body, str)
                and meta.payload.content_type == ContentType.json
                and meta.payload.schema_shortname
            ):
                try:
                    payload_path = db.payload_path(dto) / str(meta.payload.body)
                    payload_data = json.loads(payload_path.read_text())
                    await validate_payload_with_schema(
                        payload_data=payload_data,
                        space_name=one.space_name,
                        branch_name=one.branch_name,
                        schema_shortname=meta.payload.schema_shortname,
                    )
                    payload_doc_id, payload = await operational_db.prepare_payload_doc(
                        dto,
                        meta,
                        payload=copy(payload_data),
                    )
                    payload.update(meta_data)
                    payload["document_id"] = payload_doc_id
                    
                    db_docs.setdefault(meta.payload.schema_shortname, [])
                    db_docs[meta.payload.schema_shortname].append(payload)
                except SchemaValidationError as _:
                    print(
                        f"Error: @{one.space_name}/{one.subpath}/{meta.shortname} "
                        f"does not match the schema {meta.payload.schema_shortname}"
                    )
                except Exception as ex:
                    print(f"Error: @{one.space_name}:{one.subpath} {meta.shortname=}, {ex}")
                    
            meta_data["payload_string"] = await operational_repo.generate_payload_string(
                dto=EntityDTO(
                    space_name=one.space_name, 
                    subpath=one.subpath, 
                    shortname=one.shortname, 
                    branch_name=one.branch_name, 
                    resource_type=one.type,
                ),
                payload=payload_data,
            )
            
            meta_data["document_id"] = meta_doc_id
            db_docs["meta"].append(meta_data)   

        except Exception:
            print(f"path: {one.space_name}/{one.subpath}/{one.shortname} ({one.type})")
            print("stacktrace:")
            print(f"    {traceback.format_exc()}")
            pass

    return db_docs


async def traverse_subpaths_entries(
    path,
    space_name,
    branch_name,
    loaded_data,
    space_branches,
    for_subpaths: list | None = None,
):
    space_parts_count = len(settings.spaces_folder.parts)
    if branch_name == settings.default_branch:
        subpath_index = space_parts_count + 1
    else:
        subpath_index = space_parts_count + 3


    # print(f"{subpath_index=} @{space_name} {path=}")

    for subpath in path.iterdir():
        # print(f"{subpath=} 1")
        if (
            branch_name == settings.default_branch
            and subpath.parts[space_parts_count + 1] == "branches"
        ):
            continue

        # print(f"{subpath=} 2 {subpath.is_dir()} {re.match(regex.SUBPATH, subpath.name)}")

        if subpath.is_dir() and re.match(regex.SUBPATH, subpath.name):
            await traverse_subpaths_entries(
                subpath,
                space_name,
                branch_name,
                loaded_data,
                space_branches,
                for_subpaths,
            )

            # print(f"{subpath=} 3")
            subpath_name = "/".join(subpath.parts[subpath_index:])
            if for_subpaths:
                subpath_enabled = any(
                    [subpath_name.startswith(subpath) for subpath in for_subpaths]
                )
                if not subpath_enabled:
                    continue

            # print(f"{subpath=} 4")
            loaded_data.append(
                await load_data_to_redis(
                    space_name,
                    branch_name,
                    subpath_name,
                    [
                        ResourceType.content,
                        ResourceType.ticket,
                        ResourceType.schema,
                        ResourceType.notification,
                        ResourceType.post,
                        ResourceType.folder
                    ],
                )
            )
    return loaded_data

async def load_custom_indices_data(for_space: str | None = None):
    for i, index in enumerate(operational_db.SYS_INDEXES):
        if for_space and index["space"] != for_space:
            continue

        if i < len(operational_db.SYS_INDEXES) and issubclass(operational_db.SYS_INDEXES[i]["class"], Meta):
            res = await load_data_to_redis(
                index["space"],
                index["branch"],
                index["subpath"],
                [ResourceType(operational_db.SYS_INDEXES[i]["class"].__name__.lower())],
            )
            print(
                f"{res['documents']}\tCustom  {index['space']}:{index['branch']}:meta:{index['subpath']}"
            )

async def migrate_data_to_operational_db(
    for_space: str | None = None, for_subpaths: list | None = None
):
    """
    Loop over spaces and subpaths inside it and load the data to redis of indexing_enabled for the space
    """
    loaded_data = {}
    spaces = await operational_repo.find_by_id("spaces")
    for space_name, space_json in spaces.items():
        space_obj = Space.model_validate_json(space_json)
        if (for_space and for_space != space_name) or not space_obj.indexing_enabled:
            continue

        path = settings.spaces_folder / space_name
        if not path.is_dir():
            continue

        space_meta_file = path / ".dm/meta.space.json"
        if not space_meta_file.is_file():
            continue

        for branch_name in space_obj.branches:
            print(f"Checking space name: {space_name}, branch name: {branch_name}")
            path = settings.spaces_folder / space_name / branch_path(branch_name)

            loaded_data[
                f"{space_name}:{branch_name}"
            ] = await traverse_subpaths_entries(
                path, space_name, branch_name, [], space_obj.branches, for_subpaths
            )

    await load_custom_indices_data(for_space)

    return loaded_data

async def main(
    for_space: str | None = None,
    for_schemas: list | None = None,
    for_subpaths: list | None = None,
    flushall: bool = False
):
    manticore_db = ManticoreDB()
    if flushall:
        print("FLUSHALL")
        await manticore_db.flush_all()
    
    await bootstrap_all(reload_db=True, for_space=for_space, flushall=flushall)
    
    res = await migrate_data_to_operational_db(for_space, for_subpaths)
    # res = {
    #     "management": [
    #         {
    #             "documents": 55,
    #             "subpath": "permissions"
    #         }
    #     ]
    # }
    for space_name, loaded_data in res.items():
        if loaded_data:
            for item in loaded_data:
                print(f"{item['documents']}\tRegular {space_name}/{item['subpath']}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Recreate Redis indices based on the available schema definitions",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-p", "--space", help="recreate indices for this space only")
    parser.add_argument(
        "-c", "--schemas", nargs="*", help="recreate indices for this schemas only"
    )
    parser.add_argument(
        "-s", "--subpaths", nargs="*", help="upload documents for this subpaths only"
    )
    parser.add_argument(
        "--flushall", action='store_true', help="FLUSHALL data on Redis"
    )

    args = parser.parse_args()

    asyncio.run(main(args.space, args.schemas, args.subpaths, args.flushall))

    # test_search = redis_services.search(
    #     space_name="products",
    #     schema_name="offer",
    #     search="@cbs_name:DB_ATLDaily_600MB",
    #     filters={"subpath": ["offers"], "shortname": ["2140692"]},
    #     limit=10,
    #     offset=0,
    #     sort_by="cbs_id"
    # )
    # print("\n\n\nresult count: ", len(test_search), "\n\nresult: ", test_search)
