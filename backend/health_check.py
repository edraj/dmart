import argparse
import asyncio
import json
import sys
from datetime import datetime
from redis.commands.search.query import Query
from redis.commands.search.result import Result
from utils import db
from utils.custom_validations import validate_payload_with_schema
from utils.helpers import camel_case
from utils.redis_services import RedisServices
from models import core
from models.core import Payload
from models.enums import ResourceType, ContentType, ValidationEnum


async def main(health_type: str, space_name: str, schemas: list):
    if not space_name or not schemas:
        print('Add the space name and at least one schema')
        return

    if not health_type or health_type == 'soft':
        for schema_name in schemas:
            health_check: dict = await soft_health_check(space_name, schema_name)
            if not health_check:
                return
            await save_health_check_entry(health_check, space_name)


async def soft_health_check(space_name: str, schema_name: str, branch_name: str = 'master'):
    limit = 10000
    offset = 0
    folders_report = {}
    async with RedisServices() as redis:
        while True:
            try:
                ft_index = redis.client.ft(f"{space_name}:{branch_name}:{schema_name}")
                await ft_index.info()
            except Exception as x:
                print(f"can't find index: `{space_name}:{branch_name}:{schema_name}`")
                return None
            search_query = Query(query_string="*")
            search_query.paging(offset, limit)
            offset += limit
            res_data: Result = await ft_index.search(query=search_query)
            if not res_data.docs:
                break
            for redis_doc_dict in res_data.docs:
                is_valid = True
                redis_doc_dict = json.loads(redis_doc_dict.json)
                subpath = redis_doc_dict['subpath']
                meta_doc_content = {}
                payload_doc_content = {}
                resource_class = getattr(
                    sys.modules["models.core"],
                    camel_case(redis_doc_dict["resource_type"]),
                )
                system_attributes = [
                    "branch_name",
                    "query_policies",
                    "subpath",
                    "resource_type",
                    "meta_doc_id",
                    "payload_doc_id",
                ]
                for key, value in redis_doc_dict.items():
                    if key in resource_class.__fields__.keys():
                        meta_doc_content[key] = value
                    elif key not in system_attributes:
                        payload_doc_content[key] = value

                if (
                        not payload_doc_content
                        and "payload_doc_id" in redis_doc_dict
                ):
                    payload_redis_doc = await redis.get_doc_by_id(
                        redis_doc_dict["payload_doc_id"]
                    )
                    if payload_redis_doc:
                        for key, value in payload_redis_doc.items():
                            not_payload_attr = system_attributes + list(
                                resource_class.__fields__.keys()
                            )
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
                try:
                    meta = resource_class.parse_obj(meta_doc_content)
                    if (
                            meta.payload
                            and meta.payload.schema_shortname
                            and payload_doc_content is not None
                    ):
                        # TODO schema json need to be loaded before the loop and check it here
                        await validate_payload_with_schema(
                            payload_data=payload_doc_content,
                            space_name=space_name,
                            branch_name=branch_name,
                            schema_shortname=meta.payload.schema_shortname,
                        )

                    if folders_report[subpath].get('valid_entries'):
                        folders_report[subpath]['valid_entries'] += 1
                    else:
                        folders_report[subpath]['valid_entries'] = 1

                except:
                    is_valid = False
                    if not folders_report.get(subpath).get('invalid_entries'):
                        folders_report[subpath]['invalid_entries'] = []
                    if meta_doc_content["shortname"] \
                            not in folders_report[redis_doc_dict['subpath']]["invalid_entries"]:
                        folders_report[redis_doc_dict['subpath']]["invalid_entries"].append(
                            meta_doc_content["shortname"]
                        )
                if meta:
                    await update_validation_status(
                        space_name=space_name,
                        subpath=subpath,
                        meta=meta,
                        branch_name=branch_name,
                        is_valid=is_valid
                    )

    return {"invalid_folders": {}, "folders_report": folders_report}


async def update_validation_status(space_name: str, subpath: str, meta: core.Meta, is_valid: bool, branch_name: str):
    meta.payload.validation_status = ValidationEnum.valid if is_valid else ValidationEnum.invalid
    meta.payload.last_validated = datetime.now()
    await db.save(
        space_name=space_name,
        subpath=subpath,
        meta=meta,
        branch_name=branch_name
    )
    async with RedisServices() as redis:
        await redis.save_meta_doc(space_name, branch_name, subpath, meta)


async def save_health_check_entry(health_check: dict, space_name: str, branch_name: str = 'master'):
    schema_shortname = 'health_check'
    management_space = 'management'
    try:
        meta = await db.load(
            space_name=management_space,
            subpath="info",
            shortname="health_check",
            class_type=getattr(sys.modules["models.core"], ResourceType.content),
            user_shortname='dmart',
            branch_name=branch_name,
            schema_shortname=schema_shortname,
        )
    except:
        meta = core.Content(
            shortname='health_check',
            is_active=True,
            owner_shortname='dmart',
            payload=Payload(
                content_type=ContentType.json,
                schema_shortname=schema_shortname,
                body="health_check.json"
            )
        )
    try:
        body = db.load_resource_payload(
            space_name=management_space,
            subpath="info",
            filename="health_check.json",
            class_type=getattr(sys.modules["models.core"], ResourceType.content),
            branch_name=branch_name,
            schema_shortname=schema_shortname,
        )
    except:
        body = {}

    body[space_name] = health_check
    body[space_name]['updated_at'] = str(datetime.now())
    meta.updated_at = datetime.now()
    await db.save(
        space_name=management_space,
        subpath="info",
        meta=meta,
        branch_name=branch_name
    )
    await db.save_payload_from_json(
        space_name=management_space,
        subpath='info',
        meta=meta,
        payload_data=body,
        branch_name=branch_name,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="This created for doing health check functionality",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-t", "--type", help="type of health check (soft or hard)")
    parser.add_argument("-s", "--space", help="hit the target space")
    parser.add_argument("-m", "--schemas", nargs="*", help="hit the target schema inside the space")

    args = parser.parse_args()

    asyncio.run(main(args.type, args.space, args.schemas))
