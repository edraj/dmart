import argparse
import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from aiofiles import open as aopen

from utils.exporter_helpers import validate_config, exit_with_error, enc_dict, prepare_output


OUTPUT_FOLDER_NAME = "spaces_data"


async def extract(
    config_obj, spaces_path, output_path, entries_since=None, entries_limit=None
):
    space = config_obj.get("space")
    subpath = config_obj.get("subpath")
    resource_type = config_obj.get("resource_type")
    included_meta_fields = config_obj.get("included_meta_fields", [])
    excluded_payload_fields = config_obj.get("excluded_payload_fields", [])
    ignore_since_filter = config_obj.get("ignore_since_filter", False)

    space_path = Path(f"{spaces_path}/{space}")

    output_subpath = Path(f"{output_path}/{OUTPUT_FOLDER_NAME}/{space}/{subpath}")
    if not output_subpath.is_dir():
        os.makedirs(output_subpath)

    # Generat output content file
    data_file = output_subpath / f"data.ljson"
    data_file_nohash = output_subpath / f"data_nohash.ljson"
    path = os.path.join(spaces_path, space, subpath)
    count = 0
    print(f"Start reading files under {path}")
    async with aopen(data_file, "a") as df, aopen(data_file_nohash, "a") as df_nohash:
        for file_name in os.listdir(path):
            if not file_name.endswith(".json"):
                continue
            full_file_path = None
            try:
                full_file_path = os.path.join(path, file_name)
                if entries_since and not ignore_since_filter:
                    payload_ts = int(
                        round(os.path.getmtime(full_file_path) * 1000)
                    )
                    meta_ts = int(
                        round(
                            os.path.getmtime(
                                meta_path(
                                    space_path, subpath, file_name.split(".")[0], resource_type
                                )
                            )
                            * 1000
                        )
                    )
                    if payload_ts <= entries_since and meta_ts <= entries_since:
                        continue

                async with aopen(full_file_path, "r") as f:
                    content = await f.read()
                payload = json.loads(content)
                meta = await get_meta(
                    space_path=space_path,
                    subpath=subpath,
                    file_path=file_name.split(".")[0],
                    resource_type=resource_type,
                )
            except Exception as e:
                logging.exception(msg=f"Unexpected error while processing {full_file_path}")
                continue

            out = prepare_output(
                meta, payload, included_meta_fields, excluded_payload_fields
            )

            await df_nohash.write(json.dumps(out) + "\n")

            encrypted_out = enc_dict(out)
            await df.write(json.dumps(encrypted_out) + "\n")
            count += 1
            if entries_limit and count > entries_limit:
                break


async def main(tasks):
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", required=True, help="Json config relative path from the script"
    )
    parser.add_argument(
        "--spaces", required=True, help="Spaces relative path from the script"
    )
    parser.add_argument(
        "--output",
        help="Output relative path from the script (the default path is the current script path",
    )
    parser.add_argument(
        "--since",
        help="Export entries created/updated since the provided timestamp",
    )
    parser.add_argument(
        "--limit",
        help="Export entries up to a limit",
    )
    args = parser.parse_args()
    since = None
    limit = None
    output_path = ""
    if args.output:
        output_path = args.output

    if args.since:
        since = int(round(float(args.since) * 1000))

    if args.limit:
        limit = int(args.limit)

    if not os.path.isdir(args.spaces):
        exit_with_error(f"The spaces folder {args.spaces} is not found.")

    out_path = os.path.join(output_path, OUTPUT_FOLDER_NAME)
    if os.path.isdir(out_path):
        shutil.rmtree(out_path)

    tasks = []
    with open(args.config, "r") as f:
        config_objs = json.load(f)

    for config_obj in config_objs:
        if not validate_config(config_obj):
            continue
        tasks.append(extract(config_obj, args.spaces, output_path, since, limit))

    asyncio.run(main(tasks))

    print(
        f"Output path: {os.path.abspath(os.path.join(output_path, OUTPUT_FOLDER_NAME))}"
    )
