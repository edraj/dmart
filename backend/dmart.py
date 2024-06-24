#!/usr/bin/env -S BACKEND_ENV=config.env python3
import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from utils.settings import settings
from create_index import main as create_index
from main import main as server
from health_check import main as health_check
from utils.exporter import main as exporter, exit_with_error, OUTPUT_FOLDER_NAME, validate_config, extract
from archive import archive


commands = """    server
    health-check
    create-index
    export
    settings
    set-password
    archive
    help
    version 
    info
"""

sys.argv = sys.argv[1:]
if len(sys.argv) == 0:
    print("You must provide a command to run:")
    print(commands)
    sys.exit(1)

match sys.argv[0]:
    case "server":
        asyncio.run(server())
    case "health-check":
        parser = argparse.ArgumentParser(
            description="This created for doing health check functionality",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add_argument("-t", "--type", help="type of health check (soft or hard)")
        parser.add_argument("-s", "--space", help="hit the target space or pass (all) to make the full health check")
        parser.add_argument("-m", "--schemas", nargs="*", help="hit the target schema inside the space")

        args = parser.parse_args()
        before_time = time.time()
        asyncio.run(health_check(args.type, args.space, args.schemas, "master"))  # type: ignore
        print(f'total time: {"{:.2f}".format(time.time() - before_time)} sec')
    case "create-index":
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

        asyncio.run(create_index(args.space, args.schemas, args.subpaths, args.flushall))
    case "export":
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
        args = parser.parse_args()
        since = None
        output_path = ""
        if args.output:
            output_path = args.output

        if args.since:
            since = int(round(float(args.since) * 1000))

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
            tasks.append(extract(config_obj.get("space", ""),
                                 config_obj.get("subpath", ""),
                                 config_obj.get("resource_type", ""),
                                 config_obj.get("schema_shortname", ""),
                                 config_obj.get("included_meta_fields", {}),
                                 config_obj.get("excluded_payload_fields", {}),
                                 args.spaces, output_path, since))

        asyncio.run(exporter(tasks))

        print(
            f"Output path: {os.path.abspath(os.path.join(output_path, OUTPUT_FOLDER_NAME))}"
        )
    case "settings":
        print(settings.model_dump_json())
    case "set-password":
        import set_admin_passwd  # noqa: F401
    case "archive":
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
    case "help":
        print("Available commands:")
        print(commands)
    case "version":
        if __file__.endswith(".pyc"):
            with open("info.json") as info:
                print(json.load(info).get("tag"))
        else:
            tag_cmd = "git describe --tags"
            result, _ = subprocess.Popen(tag_cmd.split(" "), stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE).communicate()
            tag = None if result is None or len(result) == 0 else result.decode().strip()
            print(tag)
    case "info":
        if __file__.endswith(".pyc"):
            with open("info.json") as info:
                print(json.load(info))
        else:
            branch_cmd = "git rev-parse --abbrev-ref HEAD"
            result, _ = subprocess.Popen(branch_cmd.split(" "), stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE).communicate()
            branch = None if result is None or len(result) == 0 else result.decode().strip()

            version_cmd = "git rev-parse --short HEAD"
            result, _ = subprocess.Popen(version_cmd.split(" "), stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE).communicate()
            version = None if result is None or len(result) == 0 else result.decode().strip()

            tag_cmd = "git describe --tags"
            result, _ = subprocess.Popen(tag_cmd.split(" "), stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE).communicate()
            tag = None if result is None or len(result) == 0 else result.decode().strip()

            version_date_cmd = "git show --pretty=format:'%ad'"
            result, _ = subprocess.Popen(version_date_cmd.split(" "), stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE).communicate()
            version_date = None if result is None or len(result) == 0 else result.decode().split("\n")[0]

            print({
                "commit_hash": version,
                "date": version_date,
                "branch": branch,
                "tag": tag
            })
