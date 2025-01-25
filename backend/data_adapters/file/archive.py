#!/usr/bin/env -S BACKEND_ENV=config.env python3

import asyncio
from datetime import datetime
import json
from time import time
import os
import shutil
import sys
import argparse
from utils.helpers import camel_case
from data_adapters.file.redis_services import RedisServices
from utils.settings import settings
from typing import Awaitable


def redis_doc_to_meta(doc: dict):
    meta_doc_content = {}
    resource_class = getattr(
        sys.modules["models.core"],
        camel_case(doc["resource_type"]),
    )
    for key, value in doc.items():
        if key in resource_class.model_fields.keys():
            meta_doc_content[key] = value
    meta_doc_content["created_at"] = datetime.fromtimestamp(
        meta_doc_content["created_at"]
    )
    meta_doc_content["updated_at"] = datetime.fromtimestamp(
        meta_doc_content["updated_at"]
    )
    return resource_class.model_validate(meta_doc_content)


async def archive(space: str, subpath: str, schema: str, olderthan: int):
    """
    Archives records from a specific space, subpath, and schema.

    Args:
        space (str): The name of the space.
        subpath (str): The subpath within the space.
        schema (str): The schema name.

    Returns:
        None
    """
    limit = 10000
    counter = 0

    timestamp = int(time()) - (olderthan * 24 * 60 * 60)
    async with RedisServices() as redis_services:
        while True:
            redis_res = await redis_services.search(
                space_name=space,
                schema_name=schema,
                search=f"(@updated_at:[-inf {timestamp}])",
                filters={
                    "subpath": [subpath],
                },
                exact_subpath=True,
                limit=limit,
                offset=0,

            )
            if not redis_res or redis_res["total"] == 0:
                print(f"No more data left. {redis_res=}")
                break
            counter += redis_res["total"]
            
            search_res = redis_res["data"]

            for redis_document in search_res:
                record = json.loads(redis_document)

                try:
                    # Move payload file
                    payload_file = f"{settings.spaces_folder}/{space}/{record['subpath']}/{record.get('shortname')}.json"
                    if os.path.exists(payload_file):
                        os.makedirs(f"{settings.spaces_folder}/archive/{space}/{record['subpath']}", exist_ok=True)
                        shutil.move(
                            src=payload_file,
                            dst=f"{settings.spaces_folder}/archive/{space}/{record['subpath']}/{record.get('shortname')}.json",
                        )

                    # Move meta folder / files
                    meta_folder = f"{settings.spaces_folder}/{space}/{record['subpath']}"
                    dest_folder = f"{settings.spaces_folder}/archive/{space}/{record['subpath']}"
                    if record["resource_type"] != "folder":
                        meta_folder += "/.dm"
                        dest_folder += "/.dm"
                        
                        
                    os.makedirs(
                        f"{dest_folder}", exist_ok=True
                    )
                    shutil.move(
                        src = f"{meta_folder}/{record.get('shortname')}",
                        dst=f"{dest_folder}",
                    )

                    # Delete Payload Doc from Redis
                    if record.get("payload_doc_id"):
                        x = redis_services.json().delete(key=record.get("payload_doc_id"))
                        if isinstance(x, Awaitable):
                            await x

                    # Delete Meta Doc from Redis
                    if "meta_doc_id" in record:
                        y = redis_services.json().delete(key=record.get("meta_doc_id"))
                        if isinstance(y, Awaitable):
                            await y
                    else:
                        await redis_services.delete_doc(
                            space,
                            "meta",
                            record.get("shortname"),
                            record["subpath"],
                        )
                except Exception as e:
                    print(f"Error archiving {record.get('shortname')}: {e} at line {sys.exc_info()[-1]}")
                    continue
            print(f'Processed {counter}')
    await RedisServices().close_pool()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script for archiving records from different spaces and subpaths."
    )
    parser.add_argument("space", type=str, help="The name of the space")
    parser.add_argument("subpath", type=str, help="The subpath within the space")
    parser.add_argument(
        "schema",
        type=str,
        help="The subpath within the space. Optional, if not provided move everything",
        nargs="?",
    )
    parser.add_argument(
        "olderthan",
        type=int,
        help="The number of day, older than which, the entries will be archived (based on updated_at)",
    )

    args = parser.parse_args()
    space = args.space
    subpath = args.subpath
    olderthan = args.olderthan
    schema = args.schema or "meta"

    asyncio.run(archive(space, subpath, schema, olderthan))
    print("Done.")
