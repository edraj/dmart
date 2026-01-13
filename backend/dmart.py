#!/usr/bin/env -S BACKEND_ENV=config.env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import warnings
from multiprocessing import freeze_support
from pathlib import Path

from hypercorn.config import Config
from hypercorn.run import run

from data_adapters.file.archive import archive
from data_adapters.file.create_index import main as create_index
from data_adapters.file.health_check import main as health_check
from data_adapters.sql.json_to_db_migration import main as json_to_db_migration
from data_adapters.sql.db_to_json_migration import main as db_to_json_migration
from main import main as server
from utils.exporter import main as exporter, exit_with_error, OUTPUT_FOLDER_NAME, validate_config, extract
from utils.settings import settings

freeze_support()

commands = """    server
    hyper
    health-check
    create-index
    export
    settings
    set_password
    archive
    json_to_db
    db_to_json
    help
    version 
    info
"""

sentinel = object()


def hypercorn_main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "application", help="The application to dispatch to as path.to.module:instance.path"
    )
    parser.add_argument("--access-log", help="Deprecated, see access-logfile", default=sentinel)
    parser.add_argument(
        "--access-logfile",
        help="The target location for the access log, use `-` for stdout",
        default=sentinel,
    )
    parser.add_argument(
        "--access-logformat",
        help="The log format for the access log, see help docs",
        default=sentinel,
    )
    parser.add_argument(
        "--backlog", help="The maximum number of pending connections", type=int, default=sentinel
    )
    parser.add_argument(
        "-b",
        "--bind",
        dest="binds",
        help=""" The TCP host/address to bind to. Should be either host:port, host,
        unix:path or fd://num, e.g. 127.0.0.1:5000, 127.0.0.1,
        unix:/tmp/socket or fd://33 respectively.  """,
        default=[],
        action="append",
    )
    parser.add_argument("--ca-certs", help="Path to the SSL CA certificate file", default=sentinel)
    parser.add_argument("--certfile", help="Path to the SSL certificate file", default=sentinel)
    parser.add_argument("--cert-reqs", help="See verify mode argument", type=int, default=sentinel)
    parser.add_argument("--ciphers", help="Ciphers to use for the SSL setup", default=sentinel)
    parser.add_argument(
        "-c",
        "--config",
        help="Location of a TOML config file, or when prefixed with `file:` a Python file, or when prefixed with `python:` a Python module.",  # noqa: E501
        default=None,
    )
    parser.add_argument(
        "--debug",
        help="Enable debug mode, i.e. extra logging and checks",
        action="store_true",
        default=sentinel,
    )
    parser.add_argument("--error-log", help="Deprecated, see error-logfile", default=sentinel)
    parser.add_argument(
        "--error-logfile",
        "--log-file",
        dest="error_logfile",
        help="The target location for the error log, use `-` for stderr",
        default=sentinel,
    )
    parser.add_argument(
        "--graceful-timeout",
        help="""Time to wait after SIGTERM or Ctrl-C for any remaining requests (tasks)
        to complete.""",
        default=sentinel,
        type=int,
    )
    parser.add_argument(
        "--read-timeout",
        help="""Seconds to wait before timing out reads on TCP sockets""",
        default=sentinel,
        type=int,
    )
    parser.add_argument(
        "--max-requests",
        help="""Maximum number of requests a worker will process before restarting""",
        default=sentinel,
        type=int,
    )
    parser.add_argument(
        "--max-requests-jitter",
        help="This jitter causes the max-requests per worker to be "
        "randomized by randint(0, max_requests_jitter)",
        default=sentinel,
        type=int,
    )
    parser.add_argument(
        "-g", "--group", help="Group to own any unix sockets.", default=sentinel, type=int
    )
    parser.add_argument(
        "-k",
        "--worker-class",
        dest="worker_class",
        help="The type of worker to use. "
        "Options include asyncio, uvloop (pip install hypercorn[uvloop]), "
        "and trio (pip install hypercorn[trio]).",
        default=sentinel,
    )
    parser.add_argument(
        "--keep-alive",
        help="Seconds to keep inactive connections alive for",
        default=sentinel,
        type=int,
    )
    parser.add_argument("--keyfile", help="Path to the SSL key file", default=sentinel)
    parser.add_argument(
        "--keyfile-password", help="Password to decrypt the SSL key file", default=sentinel
    )
    parser.add_argument(
        "--insecure-bind",
        dest="insecure_binds",
        help="""The TCP host/address to bind to. SSL options will not apply to these binds.
        See *bind* for formatting options. Care must be taken! See HTTP -> HTTPS redirection docs.
        """,
        default=[],
        action="append",
    )
    parser.add_argument(
        "--log-config",
        help=""""A Python logging configuration file. This can be prefixed with
        'json:' or 'toml:' to load the configuration from a file in
        that format. Default is the logging ini format.""",
        default=sentinel,
    )
    parser.add_argument(
        "--log-level", help="The (error) log level, defaults to info", default=sentinel
    )
    parser.add_argument(
        "-p", "--pid", help="Location to write the PID (Program ID) to.", default=sentinel
    )
    parser.add_argument(
        "--quic-bind",
        dest="quic_binds",
        help="""The UDP/QUIC host/address to bind to. See *bind* for formatting
        options.
        """,
        default=[],
        action="append",
    )
    parser.add_argument(
        "--reload",
        help="Enable automatic reloads on code changes",
        action="store_true",
        default=sentinel,
    )
    parser.add_argument(
        "--root-path", help="The setting for the ASGI root_path variable", default=sentinel
    )
    parser.add_argument(
        "--server-name",
        dest="server_names",
        help="""The hostnames that can be served, requests to different hosts
        will be responded to with 404s.
        """,
        default=[],
        action="append",
    )
    parser.add_argument(
        "--statsd-host", help="The host:port of the statsd server", default=sentinel
    )
    parser.add_argument("--statsd-prefix", help="Prefix for all statsd messages", default="")
    parser.add_argument(
        "-m",
        "--umask",
        help="The permissions bit mask to use on any unix sockets.",
        default=sentinel,
        type=int,
    )
    parser.add_argument(
        "-u", "--user", help="User to own any unix sockets.", default=sentinel, type=int
    )

    def _convert_verify_mode(value: str) -> ssl.VerifyMode:
        try:
            return ssl.VerifyMode[value]
        except KeyError:
            raise argparse.ArgumentTypeError(f"'{value}' is not a valid verify mode")

    parser.add_argument(
        "--verify-mode",
        help="SSL verify mode for peer's certificate, see ssl.VerifyMode enum for possible values.",
        type=_convert_verify_mode,
        default=sentinel,
    )
    parser.add_argument(
        "--websocket-ping-interval",
        help="""If set this is the time in seconds between pings sent to the client.
        This can be used to keep the websocket connection alive.""",
        default=sentinel,
        type=int,
    )
    parser.add_argument(
        "-w",
        "--workers",
        dest="workers",
        help="The number of workers to spawn and use",
        default=sentinel,
        type=int,
    )
    args = parser.parse_args(sys.argv[1:])
    config = Config.from_toml(args.config)
    config.application_path = args.application

    if args.log_level is not sentinel:
        config.loglevel = args.log_level
    if args.access_logformat is not sentinel:
        config.access_log_format = args.access_logformat
    if args.access_log is not sentinel:
        warnings.warn(
            "The --access-log argument is deprecated, use `--access-logfile` instead",
            DeprecationWarning,
        )
        config.accesslog = args.access_log
    if args.access_logfile is not sentinel:
        config.accesslog = args.access_logfile
    if args.backlog is not sentinel:
        config.backlog = args.backlog
    if args.ca_certs is not sentinel:
        config.ca_certs = args.ca_certs
    if args.certfile is not sentinel:
        config.certfile = args.certfile
    if args.cert_reqs is not sentinel:
        config.cert_reqs = args.cert_reqs
    if args.ciphers is not sentinel:
        config.ciphers = args.ciphers
    if args.debug is not sentinel:
        config.debug = args.debug
    if args.error_log is not sentinel:
        warnings.warn(
            "The --error-log argument is deprecated, use `--error-logfile` instead",
            DeprecationWarning,
        )
        config.errorlog = args.error_log
    if args.error_logfile is not sentinel:
        config.errorlog = args.error_logfile
    if args.graceful_timeout is not sentinel:
        config.graceful_timeout = args.graceful_timeout
    if args.read_timeout is not sentinel:
        config.read_timeout = args.read_timeout
    if args.group is not sentinel:
        config.group = args.group
    if args.keep_alive is not sentinel:
        config.keep_alive_timeout = args.keep_alive
    if args.keyfile is not sentinel:
        config.keyfile = args.keyfile
    if args.keyfile_password is not sentinel:
        config.keyfile_password = args.keyfile_password
    if args.log_config is not sentinel:
        config.logconfig = args.log_config
    if args.max_requests is not sentinel:
        config.max_requests = args.max_requests
    if args.max_requests_jitter is not sentinel:
        config.max_requests_jitter = args.max_requests
    if args.pid is not sentinel:
        config.pid_path = args.pid
    if args.root_path is not sentinel:
        config.root_path = args.root_path
    if args.reload is not sentinel:
        config.use_reloader = args.reload
    if args.statsd_host is not sentinel:
        config.statsd_host = args.statsd_host
    if args.statsd_prefix is not sentinel:
        config.statsd_prefix = args.statsd_prefix
    if args.umask is not sentinel:
        config.umask = args.umask
    if args.user is not sentinel:
        config.user = args.user
    if args.worker_class is not sentinel:
        config.worker_class = args.worker_class
    if args.verify_mode is not sentinel:
        config.verify_mode = args.verify_mode
    if args.websocket_ping_interval is not sentinel:
        config.websocket_ping_interval = args.websocket_ping_interval
    if args.workers is not sentinel:
        config.workers = args.workers

    if len(args.binds) > 0:
        config.bind = args.binds
    if len(args.insecure_binds) > 0:
        config.insecure_bind = args.insecure_binds
    if len(args.quic_binds) > 0:
        config.quic_bind = args.quic_binds
    if len(args.server_names) > 0:
        config.server_names = args.server_names

    return run(config)


def main():
    sys.argv = sys.argv[1:]
    if len(sys.argv) == 0:
        print("You must provide a command to run:")
        print(commands)
        sys.exit(1)

    match sys.argv[0]:
        case "hyper":
            if len(sys.argv) == 1:
                print("Running Hypercorn with default settings")
                default_params = "main:app --config hypercorn_config.toml"
                print(f">{default_params}")
                sys.argv = ["hyper"] + default_params.split(" ")
            hypercorn_main()
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
            asyncio.run(health_check(args.type, args.space, args.schemas))
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
        case "set_password":
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
        case "json_to_db":
            asyncio.run(json_to_db_migration())
        case "db_to_json":
            db_to_json_migration()
        case "help":
            print("Available commands:")
            print(commands)
        case "version":
            info_json_path = Path(__file__).resolve().parent / "info.json"
            if info_json_path.exists():
                with open(info_json_path) as info:
                    print(json.load(info).get("tag"))
            else:
                tag_cmd = "git describe --tags"
                result, _ = subprocess.Popen(tag_cmd.split(" "), stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE).communicate()
                tag = None if result is None or len(result) == 0 else result.decode().strip()
                print(tag)
        case "info":
            info_json_path = Path(__file__).resolve().parent / "info.json"
            if info_json_path.exists():
                with open(info_json_path) as info:
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

if __name__ == "__main__":
    main()
