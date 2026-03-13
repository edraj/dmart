#!/usr/bin/env -S BACKEND_ENV=config.env python3

import argparse
import asyncio

from jsonschema import ValidationError
from jsonschema.validators import Draft7Validator
import json
import time
from sqlmodel import select, col, delete
from adapter import SQLAdapter
from data_adapters.adapter import data_adapter as db
from data_adapters.sql.create_tables import Entries, Spaces
from typing import Any

from models import core, api
from models.enums import ContentType, RequestType, ResourceType
from api.managed.router import serve_request


duplicated_entries : dict= {}

key_entries: dict = {}
MAX_INVALID_SIZE = 100

# {"space_name": {"schema_name": SCHEMA_DATA_DICT}}
spaces_schemas: dict[str, dict[str, dict]] = {}


async def main(health_type: str, space_param: str, schemas_param: list):
    async with SQLAdapter().get_session() as session:
        session.execute(
            delete(Entries).where(col(Entries.subpath) == "/health_check")
        )
        await session.commit()

    health_type = "hard" if health_type is None else health_type
    space_param = "all" if space_param is None else space_param

    if health_type not in ["soft", "hard"]:
        print("Wrong mode specify [soft or hard]")
        return

    spaces = await db.get_spaces()
    spaces_names : list = []

    if space_param != "all":
        if space_param not in spaces.keys():
            print(f"space name {space_param} is not found")
            return
        spaces_names = [spaces[space_param]]
    else:
        spaces_names = list(spaces.keys())

    if health_type == "soft":
        pass
    elif health_type == "hard":
        for space in spaces_names:
            await hard_space_check(space)


async def hard_space_check(space):
    async with SQLAdapter().get_session() as session:
        sql_stm = select(Entries).where(col(Entries.space_name) == space)
        _result = session.exec(sql_stm).all()
        _result = [r[0] for r in _result]
        entries = list(_result)
        folders_report: dict[str, dict[str, Any]] = {}

        _sql_stm = select(Spaces).where(col(Spaces.shortname) == space)
        target_space: Spaces | None = session.exec(_sql_stm).first()
        if target_space:
            schema_data_space: Entries | None = session.exec(
                select(Entries)
                .where(Entries.shortname == 'metafile')
                .where(Entries.subpath == "/schema")
            ).first()
            if "/" not in folders_report:
                folders_report["/" ] = {
                    "valid_entries": 0,
                }

            if schema_data_space and schema_data_space.payload:
                try:
                    if isinstance(schema_data_space.payload, dict):
                        Draft7Validator(
                            schema_data_space.payload["body"]
                        ).validate(
                            json.loads(target_space.model_dump_json())
                        )
                    folders_report['/']["valid_entries"] += 1
                except ValidationError as e:
                    issue = {
                        "issues": ["payload"],
                        "uuid": str(target_space.uuid),
                        "shortname": target_space.shortname,
                        "resource_type": 'space',
                        "exception": str(e),
                    }
                    if folders_report['/'].get("invalid_entries", None) is None:
                        folders_report['/']["invalid_entries"] = []
                    folders_report['/']["invalid_entries"] = [
                        *folders_report['/']["invalid_entries"],
                        issue
                    ]

        for entry in entries:
            subpath = entry.subpath[1:]
            if subpath == "":
                subpath = "/"

            payload : core.Payload
            if entry.payload and isinstance(entry.payload, dict):
                try:
                    payload = core.Payload.model_validate(entry.payload)
                except Exception as e:
                    issue = {
                        "issues": ["payload"],
                        "uuid": str(entry.uuid),
                        "shortname": entry.shortname,
                        "resource_type": 'space',
                        "exception": str(e),
                    }
                    if folders_report['/'].get("invalid_entries", None) is None:
                        folders_report['/']["invalid_entries"] = []
                    folders_report['/']["invalid_entries"] = [
                        *folders_report['/']["invalid_entries"],
                        issue
                    ]
                    continue
            elif isinstance(entry.payload, core.Payload):
                payload = entry.payload
            else:
                continue

            if not payload.schema_shortname:
                continue

            body = payload.body
            schema_data = session.exec(
                select(Entries)
                .where(Entries.shortname == payload.schema_shortname)
                .where(Entries.subpath == "/schema")
            ).first()

            if not schema_data:
                continue

            schema_payload : core.Payload
            if schema_data.payload and isinstance(schema_data.payload, dict):
                schema_payload = core.Payload.model_validate(schema_data.payload)
            elif schema_data.payload and isinstance(schema_data.payload, core.Payload):
                schema_payload = schema_data.payload
            else:
                continue

            if not schema_payload.body:
                continue
            schema_body = schema_payload.body
            if isinstance(schema_body, str):
                continue

            if subpath not in folders_report:
                folders_report[subpath] = {
                    "valid_entries": 0,
                }

            try:
                Draft7Validator(
                    schema_body
                ).validate(body)
                folders_report[subpath]["valid_entries"] += 1
            except ValidationError as e:
                issue = {
                    "issues": ["payload"],
                    "uuid": str(entry.uuid),
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
    try:
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
    except Exception as e:
        print(e)

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
