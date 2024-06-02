import asyncio
from datetime import datetime
import json
from time import time
import os
import shutil
import sys
import argparse
from utils.helpers import camel_case
from utils.redis_services import RedisServices
from utils.settings import settings


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


async def archive(space: str, subpath: str, schema: str, timewindow: int):
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
    offset = 0

    timestamp = int(time()) - (timewindow * 24 * 60 * 60)
    async with RedisServices() as redis_services:
        while True:
            redis_res = await redis_services.search(
                space_name=space,
                branch_name=settings.default_branch,
                schema_name=schema,
                search=f"(@updated_at:[-inf {timestamp}])",
                filters={
                    "subpath": [subpath],
                },
                exact_subpath=True,
                limit=limit,
                offset=offset,

            )
            if not redis_res or redis_res["total"] == 0:
                break
            offset += limit
            
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
                        await redis_services.json().delete(key=record.get("payload_doc_id"))  # type: ignore

                    # Delete Meta Doc from Redis
                    if "meta_doc_id" in record:
                        await redis_services.json().delete(key=record.get("meta_doc_id"))  # type: ignore
                    else:
                        await redis_services.delete_doc(
                            space,
                            settings.default_branch,
                            "meta",
                            record.get("shortname"),
                            record["subpath"],
                        )
                except Exception as e:
                    print(f"Error archiving {record.get('shortname')}: {e} at line {sys.exc_info()[-1].tb_lineno}") # type: ignore
                    continue


    await RedisServices.POOL.aclose()
    await RedisServices.POOL.disconnect(True)


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
        "timewindow",
        type=int,
        help="Time window in days to consider for archiving.",
    )

    args = parser.parse_args()
    space = args.space
    subpath = args.subpath
    timewindow = args.timewindow
    schema = args.schema or "meta"

    asyncio.run(archive(space, subpath, schema, timewindow))
    print("Done.")
