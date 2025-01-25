#!/usr/bin/env -S BACKEND_ENV=config.env python3

import argparse
from copy import copy
import json
import re
import traceback

import models.api as api
from data_adapters.adapter import data_adapter as db
import models.core as core
import sys
from models.enums import ContentType, ResourceType
from utils.helpers import camel_case, divide_chunks
from jsonschema.exceptions import ValidationError as SchemaValidationError
from data_adapters.file.redis_services import RedisServices
from data_adapters.file.adapter_helpers import generate_payload_string
from utils.settings import settings
import utils.regex as regex
import asyncio
from utils.access_control import access_control
from multiprocessing import Pool


async def load_data_to_redis(
    space_name,
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
        api.Query(
            space_name=space_name,
            subpath=subpath,
            type=api.QueryType.subpath,
            limit=10000000,
            filter_types=allowed_resource_types,
        )
    )

    # Add Folder locator to the loaded locators
    folder_meta = settings.spaces_folder / space_name / subpath / ".dm/meta.folder.json"
    if ResourceType.folder in allowed_resource_types and  folder_meta.is_file():
        folder_parts = subpath.split("/")
        folder_locator = core.Locator(
            type=ResourceType.folder,
            space_name=space_name,
            subpath="/".join(folder_parts[:-1]) or "/",
            shortname=folder_parts[-1]
        )
        locators.append(folder_locator)
        locators_len += 1

    # print(f"\nEnded loading {locators_len} files, starting parsing data in each file {int(time()) - start_time}")

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
    async with RedisServices() as redis_man:
        for one in locators:
            try:
                myclass = getattr(sys.modules["models.core"], camel_case(one.type))
                # print(f"{one=}")

                try:
                    meta = await db.load(
                        space_name=one.space_name,
                        subpath=one.subpath,
                        shortname=one.shortname,
                        class_type=myclass,
                        user_shortname="anonymous",
                    )
                except Exception as e:
                    print(e)
                    continue
                meta_doc_id, meta_data = redis_man.prepare_meta_doc(
                    one.space_name, one.subpath, meta
                )
                payload_data = {}
                if (
                    meta.payload
                    and isinstance(meta.payload.body, str)
                    and meta.payload.content_type == ContentType.json
                    and meta.payload.schema_shortname
                ):
                    try:
                        payload_path = db.payload_path(
                            one.space_name, one.subpath, myclass
                        ) / str(meta.payload.body)
                        payload_data = json.loads(payload_path.read_text())
                        await db.validate_payload_with_schema(
                            payload_data=payload_data,
                            space_name=one.space_name,
                            schema_shortname=meta.payload.schema_shortname,
                        )
                        doc_id, payload = redis_man.prepare_payload_doc(
                            space_name=one.space_name,
                            subpath=one.subpath,
                            resource_type=one.type,
                            payload=copy(payload_data),
                            meta=meta,
                        )
                        payload.update(meta_data)
                        redis_docs.append({"doc_id": doc_id, "payload": payload})
                    except SchemaValidationError as _:
                        print(
                            f"Error: @{one.space_name}/{one.subpath}/{meta.shortname} "
                            f"does not match the schema {meta.payload.schema_shortname}"
                        )
                    except Exception as ex:
                        print(f"Error: @{one.space_name}:{one.subpath} {meta.shortname=}, {ex}")

                meta_data["payload_string"] = await generate_payload_string(
                    db,
                    space_name=one.space_name, 
                    subpath=one.subpath, 
                    shortname=one.shortname, 
                    payload=payload_data,
                ) if settings.store_payload_string else ""
                
                redis_docs.append({"doc_id": meta_doc_id, "payload": meta_data})

            except Exception:
                print(f"path: {one.space_name}/{one.subpath}/{one.shortname} ({one.type})")
                print("stacktrace:")
                print(f"    {traceback.format_exc()}")

    return redis_docs



async def load_custom_indices_data(for_space: str | None = None):
    for i, index in enumerate(RedisServices.CUSTOM_INDICES):
        if for_space and index["space"] != for_space:
            continue

        if i < len(RedisServices.CUSTOM_CLASSES) and issubclass(RedisServices.CUSTOM_CLASSES[i], core.Meta):
            res = await load_data_to_redis(
                index["space"],
                index["subpath"],
                [ResourceType(RedisServices.CUSTOM_CLASSES[i].__name__.lower())],
            )
            print(
                f"{res['documents']}\tCustom  {index['space']}:meta:{index['subpath']}"
            )


async def traverse_subpaths_entries(
    path,
    space_name,
    loaded_data,
    for_subpaths: list | None = None,
):
    # print(f"{subpath_index=} @{space_name} {path=}")
    space_parts_count = len(settings.spaces_folder.parts)
    subpath_index = space_parts_count + 1

    for subpath in path.iterdir():
        # print(f"{subpath=} 1")

        # print(f"{subpath=} 2 {subpath.is_dir()} {re.match(regex.SUBPATH, subpath.name)}")

        if subpath.is_dir() and re.match(regex.SUBPATH, subpath.name):
            await traverse_subpaths_entries(
                subpath,
                space_name,
                loaded_data,
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


async def load_all_spaces_data_to_redis(
    for_space: str | None = None, for_subpaths: list | None = None
):
    """
    Loop over spaces and subpaths inside it and load the data to redis of indexing_enabled for the space
    """
    loaded_data = {}
    spaces = await db.get_spaces()
    for space_name, space_json in spaces.items():
        space_obj = core.Space.model_validate_json(space_json)
        if (for_space and for_space != space_name) or not space_obj.indexing_enabled:
            continue

        path = settings.spaces_folder / space_name
        if not path.is_dir():
            continue

        space_meta_file = path / ".dm/meta.space.json"
        if not space_meta_file.is_file():
            continue

        print(f"Checking space name: {space_name}")
        path = settings.spaces_folder / space_name

        loaded_data[
            f"{space_name}"
        ] = await traverse_subpaths_entries(
            path, space_name, [], for_subpaths
        )

    await load_custom_indices_data(for_space)

    return loaded_data


async def main(
    for_space: str | None = None,
    for_schemas: list | None = None,
    for_subpaths: list | None = None,
    flushall: bool = False
):
    
    try:
        async with RedisServices() as redis_man:
            if flushall:
                print("FLUSHALL")
                await redis_man.flushall()

            print("Intializing spaces")
            await db.initialize_spaces()

            print(f"Creating Redis indices: {for_space=} {for_schemas=}")
            await access_control.load_permissions_and_roles()
            await redis_man.create_indices(
                for_space=for_space, 
                for_schemas=for_schemas,
                del_docs=not bool(for_subpaths)
            )
        res = await load_all_spaces_data_to_redis(for_space, for_subpaths)
        for space_name, loaded_data in res.items():
            if loaded_data:
                for item in loaded_data:
                    print(f"{item['documents']}\tRegular {space_name}/{item['subpath']}")
    finally:
        await RedisServices().close_pool()



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
