#!/usr/bin/env -S BACKEND_ENV=config.env python3

import argparse
import asyncio

from jsonschema import ValidationError
from jsonschema.validators import Draft7Validator
import time
from sqlmodel import select
from data_adapters.sql_adapter import SQLAdapter
from data_adapters.adapter import data_adapter as db
from utils.database.create_tables import Entries
from typing import Any

from models import core, api
from models.enums import ContentType, RequestType, ResourceType
from api.managed.router import serve_request
from datetime import datetime


duplicated_entries : dict= {}

key_entries: dict = {}
MAX_INVALID_SIZE = 100

# {"space_name": {"schema_name": SCHEMA_DATA_DICT}}
spaces_schemas: dict[str, dict[str, dict]] = {}


async def main(health_type: str, space_param: str, schemas_param: list):
    health_type = "hard" if health_type is None else health_type
    space_param = "all" if space_param is None else space_param

    if health_type not in ["soft", "hard"]:
        print("Wrong mode specify [soft or hard]")
        return

    spaces = await db.get_spaces()
    print(f"{spaces=}")
    if space_param != "all":
        if space_param not in spaces.keys():
            print(f"space name {space_param} is not found")
            return
        spaces = [spaces[space_param]]

    if health_type == "soft":
        pass
    elif health_type == "hard":
        for space in spaces:
            await hard_space_check(space)


async def hard_space_check(space):
    with SQLAdapter().get_session() as session:
        sql_stm = select(Entries).where(Entries.space_name == space)
        entries = list(session.exec(sql_stm).all())
        folders_report: dict[str, dict[str, Any]] = {}
        for entry in entries:
            subpath = entry.subpath[1:]
            if subpath == "":
                subpath = "/"

            if entry is None or entry.payload is None \
                    or not entry.payload.get("body", None): # type: ignore
                continue

            if not entry.payload.get("schema_shortname", None): # type: ignore
                continue

            body = entry.payload["body"] # type: ignore
            schema_data = session.exec(
                select(Entries)
              .where(Entries.shortname == entry.payload["schema_shortname"]) # type: ignore
              .where(Entries.subpath == "/schema")
            ).first() # type: ignore

            if schema_data is None or schema_data.payload is None \
                    or not schema_data.payload.get("body", None): # type: ignore
                continue

            if subpath not in folders_report:
                folders_report[subpath] = {
                    "valid_entries": 0,
                }

            try:
                Draft7Validator(
                    schema_data.payload.get("body", {}) # type: ignore
                ).validate(body)
                folders_report[subpath]["valid_entries"] += 1
            except ValidationError as e:
                issue = {
                    "issues": ["payload"],
                    "uuid": entry.uuid,
                    "shortname": entry.shortname,
                    "resource_type": entry.resource_type,
                    "exception": str(e),
                }
                if folders_report[subpath].get("invalid_entries", None) is None:
                    folders_report[subpath]["invalid_entries"] = []
                folders_report[subpath]["invalid_entries"] = [
                    *folders_report[subpath]["invalid_entries"],
                    issue
                ]

        await save_health_check_entry(
            {"folders_report": folders_report}, space
        )


async def save_health_check_entry(health_check, space_name: str):
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
