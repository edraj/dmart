#!/usr/bin/env -S BACKEND_ENV=config.env python3

import argparse
import asyncio
from db.manticore_db import ManticoreDB
from utils.bootstrap import bootstrap_all


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
    
    await bootstrap_all()


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
