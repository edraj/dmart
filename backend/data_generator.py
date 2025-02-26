import argparse
import asyncio
from pathlib import Path
from uuid import uuid4
from models.core import Content, Payload
from models.enums import ContentType
from jsf import JSF # type: ignore
from data_adapters.adapter import data_adapter as db


async def main(
    space: str,
    subpath: str,
    schema_path: str,
    num: int
):

    if not Path(schema_path).is_file():
        print("Invalid schema file path")


    faker = JSF.from_json(Path(schema_path)) # type: ignore
    for i in range(0, num):
        payload = faker.generate()
        uuid = uuid4()
        shortname = str(uuid)[:8]
        meta = Content(
            uuid = uuid,
            shortname = shortname,
            is_active=True,
            owner_shortname="generator_script",
            payload=Payload(
                content_type=ContentType.json,
                schema_shortname=schema_path.split("/")[-1].split(".")[0],
                body=f"{shortname}.json"
            )
        )
        await db.internal_save_model(
            space_name=space,
            subpath=subpath,
            meta=meta,
            payload=payload
        )
        print(f"Generated new doc with shortname: {shortname}")

    print("====================================================")
    print(f"The generator script is finished, {num} of records generated")
    print("====================================================")




if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate fake records based on a specific schema,\
            it only creates resources of type Content.\
            Stores the data in the flat-file DB and Redis",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-p", "--space", help="Store records under this space"
    )
    parser.add_argument(
        "-s", "--subpath", help="Store records under this subpath"
    )
    parser.add_argument(
        "-c", "--schema-path", help="Generate records according to this schema (path)"
    )
    parser.add_argument(
        "-n", "--num", help="Number of records to be generated", type=int
    )

    args = parser.parse_args()

    asyncio.run(main(
      args.space,
      args.subpath,
      args.schema_path,
      args.num
    ))
