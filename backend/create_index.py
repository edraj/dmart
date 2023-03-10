#!/usr/bin/env -S BACKEND_ENV=config.env python3

import argparse
import json
import re
import traceback

import models.api as api
import utils.db as db
import models.core as core
import sys
from models.enums import ContentType, ResourceType
from utils.helpers import branch_path, camel_case, divide_chunks
from utils.custom_validations import validate_payload_with_schema
from jsonschema.exceptions import ValidationError as SchemaValidationError
from utils.redis_services import RedisServices
from utils.settings import settings
import utils.regex as regex
import asyncio
from utils.spaces import get_spaces, initialize_spaces
from utils.access_control import access_control
from time import time
from multiprocessing import Pool, current_process


async def load_data_to_redis(space_name, branch_name, subpath, allowed_resource_types):
    """
    Load meta files inside subpath then store them to redis as :space_name:meta prefixed doc,
    and if the meta file has a separate payload file follwing a schema we loads the payload content and store it to redis as :space_name:schema_name prefixed doc
    """
    start_time: int = int(time())

    #print(f"\n\nSTART EXAMINING SUBPATH: {subpath}  {int(time()) - start_time} ")

    locators_len, locators = db.locators_query(
        api.Query(
            space_name=space_name,
            branch_name=branch_name,
            subpath=subpath,
            type=api.QueryType.subpath,
            limit=10000000,
            filter_types=allowed_resource_types,
        )
    )
    #print(f"Ended loading {locators_len} files, starting parsing data in each file {int(time()) - start_time}")

    if locators_len <= 5000:
        redis_docs_chunks = [await generate_redis_docs(locators)]
    else:
        with Pool() as pool:
            multiple_results = [
                pool.apply_async(generate_redis_docs_process, (locators_chunk, )) 
                for locators_chunk in divide_chunks(locators, 5000)
            ]
            redis_docs_chunks = [process_res.get() for process_res in multiple_results]

    
    saved_docs = []
    #print(f"""
    #    Completed parsing {locators_len} files, 
    #    generated {len(redis_docs_chunks)} chunks of docs to be stored in Redis, 
    #    time: {int(time()) - start_time}
    #""")
    
    async with RedisServices() as redis_man:
        for redis_docs_chunk in redis_docs_chunks:
            saved_docs += await redis_man.save_bulk(redis_docs_chunk)


    return {"subpath": subpath, "documents": len(saved_docs)}


def generate_redis_docs_process(locators: list):
    return asyncio.run(generate_redis_docs(locators))

async def generate_redis_docs(locators: list) -> list:
    redis_docs = []
    redis_man : RedisServices = await RedisServices()
    for one in locators:
        try:
            myclass = getattr(sys.modules["models.core"], camel_case(one.type))

            meta = await db.load(
                space_name=one.space_name,
                branch_name=one.branch_name,
                subpath=one.subpath,
                shortname=one.shortname,
                class_type=myclass,
                user_shortname="anonymous",
            )
            meta_doc_id, meta_data = redis_man.prepate_meta_doc(
                one.space_name, one.branch_name, one.subpath, meta
            )
            redis_docs.append({"doc_id": meta_doc_id, "payload": meta_data})
            if (
                meta.payload
                and meta.payload.content_type == ContentType.json
                and meta.payload.schema_shortname
            ):
                payload_data = {}
                try:
                    payload_path = db.payload_path(
                        one.space_name, one.subpath, myclass, one.branch_name
                    ) / str(meta.payload.body)
                    payload_data = json.loads(payload_path.read_text())
                    await validate_payload_with_schema(
                        payload_data=payload_data,
                        space_name=one.space_name,
                        branch_name=one.branch_name,
                        schema_shortname=meta.payload.schema_shortname,
                    )
                    doc_id, payload = redis_man.prepare_payload_doc(
                        space_name=one.space_name,
                        branch_name=one.branch_name,
                        subpath=one.subpath,
                        resource_type=one.type,
                        payload=payload_data,
                        meta=meta,
                    )
                    payload.update(meta_data)
                    redis_docs.append({"doc_id": doc_id, "payload": payload})
                except SchemaValidationError as e:
                    print(
                        f"Error: @{one.space_name}/{one.subpath}/{meta.shortname} does not match the schema {meta.payload.schema_shortname}"
                    )
                except Exception as ex:
                    print(f"Error: @{one.space_name}:{one.subpath} {meta.shortname=}, {ex}")

        except:
            print(f"path: {one.space_name}/{one.subpath}/{one.shortname}")
            print("stacktrace:")
            print(f"    {traceback.format_exc()}")
            pass
        
    del redis_man

    return redis_docs



async def load_custom_indices_data(for_space: str | None = None):
    for index in RedisServices.CUSTOM_INDICES:
        if for_space and index["space"] != for_space:
            continue

        res = await load_data_to_redis(
            index["space"],
            index["branch"],
            index["subpath"],
            [ResourceType(index["class"].__name__.lower())],
        )
        print(
            f"{res['documents']}\tCustom  {index['space']}:{index['branch']}:meta:{index['subpath']}"
        )


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

    for subpath in path.iterdir():
        if (
            branch_name == settings.default_branch
            and subpath.parts[space_parts_count + 1] == "branches"
        ):
            continue

        if subpath.is_dir() and re.match(regex.SUBPATH, subpath.name):
            await traverse_subpaths_entries(
                subpath,
                space_name,
                branch_name,
                loaded_data,
                space_branches,
                for_subpaths,
            )

            subpath_name = "/".join(subpath.parts[subpath_index:])
            if for_subpaths and subpath_name not in for_subpaths:
                continue

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
                    ],
                )
            )
    return loaded_data


async def load_all_spaces_data_to_redis(
    for_space: str | None = None, for_subpaths: list | None = None
):
    """
    Loop over spaces and subpaths inside it and load the data to redis of indexing_enabled for the space
    """
    loaded_data = {}
    spaces = await get_spaces()
    for space_name, space_json in spaces.items():
        space_obj = core.Space.parse_raw(space_json)
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
    
    async with RedisServices() as redis_man:
        if flushall:
            print("FLUSHALL")
            await redis_man.client.flushall()

        print("Intializing spaces")
        await initialize_spaces()

        print(f"Creating Redis indices: {for_space=} {for_schemas=}")
        await access_control.load_permissions_and_roles()
        await redis_man.create_indices_for_all_spaces_meta_and_schemas(
            for_space, for_schemas
        )
    res = await load_all_spaces_data_to_redis(for_space, for_subpaths)
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
