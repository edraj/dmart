import asyncio
import argparse
from typing import Awaitable
from data_adapters.file.redis_services import RedisServices

#!/usr/bin/env python

# Your code goes here

async def drop_index(space: str, schema: str) -> None:
    try:
        async with RedisServices() as redis_services:
            print("Dropping Meta Docs")
            # Delete Meta docs
            document_ids = await redis_services.get_all_document_ids(f"{space}:meta", f"@schema_shortname:{schema}")
            for id in document_ids:
                x = redis_services.json().delete(id)
                if x and isinstance(x, Awaitable):
                    await x
                print(f"Deleted: {id}")
                    
            # Drop the index and delete it's docs
            print("Dropping The Index")
            await redis_services.drop_index(f"{space}:{schema}", True)
            print("DONE.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script to drop index and delete associated documents in Redis.")
    parser.add_argument("space", help="Space name where the index is located.")
    parser.add_argument("schema", help="Schema name to drop index for.")

    args = parser.parse_args()
    
    if args.schema == "meta":
        print("Cannot drop index for schema 'meta'")

    asyncio.run(drop_index(args.space, args.schema))
