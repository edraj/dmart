#!/usr/bin/env -S BACKEND_ENV=config.env python3
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import ssl
import subprocess
import sys
import os
import secrets
sys.path.append(os.path.dirname(__file__))

from utils.settings import settings, get_env_file
import time
import warnings
import webbrowser
import re
# from multiprocessing import freeze_support
from pathlib import Path

from hypercorn.config import Config
from hypercorn.run import run

# freeze_support()

commands = """
    serve
    hyper
    cli
    health-check
    create-index
    export
    settings
    set_password
    archive
    json_to_db
    db_to_json
    update_query_policies
    help
    version 
    info
    init
    migrate
    test
    apply_plugin_config
"""

sentinel = object()

def ensure_dmart_home():
    dmart_home = Path.home() / ".dmart"
    dmart_home.mkdir(parents=True, exist_ok=True)

    config_env = dmart_home / "config.env"
    if not config_env.exists():
        try:
            (dmart_home / "logs").mkdir(parents=True, exist_ok=True)
            (dmart_home / "spaces").mkdir(parents=True, exist_ok=True)
            (dmart_home / "spaces" / "custom_plugins").mkdir(parents=True, exist_ok=True)
            
            jwt_secret = secrets.token_urlsafe(32)
            
            config_content = f"""# dmart configuration
JWT_SECRET="{jwt_secret}"
JWT_ALGORITHM="HS256"
LOG_FILE="{dmart_home / 'logs' / 'dmart.ljson.log'}"
WS_LOG_FILE="{dmart_home / 'logs' / 'websocket.ljson.log'}"

# Database configuration
ACTIVE_DATA_DB="file"
SPACES_FOLDER="{dmart_home / 'spaces'}"
DATABASE_DRIVER="sqlite+pysqlite"
DATABASE_NAME="{dmart_home / 'dmart.db'}"

# Server configuration
LISTENING_HOST="0.0.0.0"
LISTENING_PORT=8282
"""
            config_env.write_text(config_content)
            print(f"Created default config.env at {config_env}")
        except Exception as e:
            print(f"Warning: Failed to create default config.env at {config_env}: {e}")

    cli_ini = dmart_home / "cli.ini"
    if not cli_ini.exists():
        try:
            default_config = ""
            sample_path = Path(__file__).resolve().parent / "config.ini.sample"
            if sample_path.exists():
                with open(sample_path, "r") as f:
                    default_config = f.read()
            else:
                default_config = (
                    'url = "http://localhost:8282"\n'
                    'shortname = "dmart"\n'
                    'password = "xxxx"\n'
                    'query_limit = 50\n'
                    'retrieve_json_payload = True\n'
                    'default_space = "management"\n'
                    'pagination = 50\n'
                )

            login_creds_path = dmart_home / "login_creds.sh"
            if login_creds_path.exists():
                try:
                    with open(login_creds_path, "r") as f:
                        creds_content = f.read()
                    
                    match = re.search(r"export SUPERMAN='(.*?)'", creds_content)
                    if match:
                        creds_json = match.group(1)
                        creds = json.loads(creds_json)
                        if "shortname" in creds:
                            default_config = re.sub(r'shortname = ".*"', f'shortname = "{creds["shortname"]}"', default_config)
                        if "password" in creds:
                            default_config = re.sub(r'password = ".*"', f'password = "{creds["password"]}"', default_config)
                except Exception as e:
                    print(f"Warning: Failed to parse login_creds.sh: {e}")

            with open(cli_ini, "w") as f:
                f.write(default_config)
            print(f"Created default cli.ini at {cli_ini}")
        except Exception as e:
            print(f"Warning: Failed to create default cli.ini at {cli_ini}: {e}")

    cxb_config = dmart_home / "config.json"
    if not cxb_config.exists():
        try:
            sample_cxb_path = Path(__file__).resolve().parent / "cxb" / "config.sample.json"
            if sample_cxb_path.exists():
                shutil.copy2(sample_cxb_path, cxb_config)
                print(f"Created default config.json at {cxb_config}")
            else:
                default_cxb_config = {
                  "title": "DMART Unified Data Platform",
                  "footer": "dmart.cc unified data platform",
                  "short_name": "dmart",
                  "display_name": "dmart",
                  "description": "dmart unified data platform",
                  "default_language": "en",
                  "languages": { "ar": "العربية", "en": "English" },
                  "backend": "http://localhost:8282",
                  "websocket": "ws://0.0.0.0:8484/ws",
                  "cxb_url": "/cxb"
                }
                with open(cxb_config, "w") as f:
                    json.dump(default_cxb_config, f, indent=2)
                print(f"Created default config.json at {cxb_config}")
        except Exception as e:
            print(f"Warning: Failed to create default config.json at {cxb_config}: {e}")

ensure_dmart_home()

def hypercorn_main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "application",
        help="The application to dispatch to as path.to.module:instance.path",
        nargs="?",
        default="main:app"
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
        default="hypercorn_config.toml",
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
    parser.add_argument(
        "--open-cxb",
        help="Open CXB page in browser after server starts",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--cxb-config",
        help="Path to CXB config.json",
        default=sentinel,
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
    
    if args.config == "hypercorn_config.toml" and not os.path.exists(args.config):
        config = Config()
        config.backlog = 2000
        config.workers = 1
        config.bind = ["localhost:8282"]
    else:
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
    
    if args.cxb_config is not sentinel:
        os.environ["DMART_CXB_CONFIG"] = args.cxb_config
        settings.load_cxb_config()

    env_file = get_env_file()
    if env_file and os.path.exists(env_file):
        config.bind = [f"{settings.listening_host}:{settings.listening_port}"]

    if len(args.binds) > 0:
        config.bind = args.binds
    if len(args.insecure_binds) > 0:
        config.insecure_bind = args.insecure_binds
    if len(args.quic_binds) > 0:
        config.quic_bind = args.quic_binds
    if len(args.server_names) > 0:
        config.server_names = args.server_names

    if args.open_cxb:
        port = 8282
        host = "127.0.0.1"

        if len(args.binds) > 0:
            try:
                bind_parts = args.binds[0].split(":")
                if len(bind_parts) == 2:
                    host = bind_parts[0]
                    port = int(bind_parts[1])
                elif len(bind_parts) == 1:
                    host = bind_parts[0]
            except Exception as e:
                print(e)
                pass
        
        if host == "0.0.0.0":
            host = "127.0.0.1"

        url = f"http://{host}:{port}{settings.cxb_url}/"
        
        def open_browser():
            time.sleep(2)
            webbrowser.open(url)
            
        import threading
        threading.Thread(target=open_browser, daemon=True).start()

    return run(config)


def patch_plugin_configs():
    dmart_home = Path.home() / ".dmart"
    plugins_config_path = dmart_home / "plugins_config.json"
    
    if not plugins_config_path.exists():
        print(f"No plugins_config.json found at {plugins_config_path}")
        return

    try:
        with open(plugins_config_path, "r") as f:
            patches = json.load(f)
    except Exception as e:
        print(f"Error reading {plugins_config_path}: {e}")
        return

    backend_dir = Path(__file__).resolve().parent
    plugins_dir = backend_dir / "plugins"

    if not plugins_dir.exists():
        print(f"Plugins directory not found at {plugins_dir}")
        return

    def deep_update(source, overrides):
        for key, value in overrides.items():
            if isinstance(value, dict) and value:
                node = source.get(key, {})
                if not isinstance(node, dict):
                    node = {}
                source[key] = deep_update(node, value)
            else:
                source[key] = value
        return source

    for plugin_name, patch_data in patches.items():
        plugin_config_path = plugins_dir / plugin_name / "config.json"
        
        if not plugin_config_path.exists():
            print(f"Warning: Config for plugin '{plugin_name}' not found at {plugin_config_path}")
            continue
            
        try:
            with open(plugin_config_path, "r") as f:
                original_config = json.load(f)
            
            updated_config = deep_update(original_config, patch_data)
            
            with open(plugin_config_path, "w") as f:
                json.dump(updated_config, f, indent=2)
                
            print(f"Patched config for plugin: {plugin_name}")
            
        except Exception as e:
            print(f"Error patching plugin '{plugin_name}': {e}")


def print_formatted(data):
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            pass

    if isinstance(data, (dict, list)):
        output = json.dumps(data, indent=4)
        lexer_name = "json"
    else:
        output = str(data)
        lexer_name = "text"

    if sys.stdout.isatty():
        try:
            from pygments import highlight, lexers, formatters
            lexer = lexers.get_lexer_by_name(lexer_name)
            print(highlight(output, lexer, formatters.TerminalFormatter()).strip())
            return
        except ImportError:
            pass
    
    print(output)


def main():
    sys.argv = sys.argv[1:]
    if len(sys.argv) == 0:
        print("You must provide a command to run:")
        print(commands)
        sys.exit(1)

    match sys.argv[0]:
        case "hyper":
            hypercorn_main()
        case "cli":
            config_file = None
            if "--config" in sys.argv:
                idx = sys.argv.index("--config")
                if idx + 1 < len(sys.argv):
                    config_file = sys.argv[idx + 1]
                    sys.argv.pop(idx + 1)
                    sys.argv.pop(idx)

            if not config_file:
                if os.path.exists("cli.ini"):
                    config_file = "cli.ini"
                else:
                    home_config = Path.home() / ".dmart" / "cli.ini"
                    if home_config.exists():
                        config_file = str(home_config)
            
            if config_file:
                os.environ["BACKEND_ENV"] = config_file
            
            last_import_error = None
            try:
                dmart_dir = Path(__file__).resolve().parent
                if str(dmart_dir) not in sys.path:
                    sys.path.append(str(dmart_dir))
                import cli # type: ignore
                cli.main()
                return
            except ImportError as e:
                last_import_error = e
                if e.name and e.name != 'cli':
                    print(f"Error: Missing dependency for CLI: {e}")
                    sys.exit(1)
            except Exception as e:
                print(f"Error: Failed to start CLI: {e}")
                sys.exit(1)

            cli_path = Path(__file__).resolve().parent.parent / "cli"
            if cli_path.exists():
                sys.path.append(str(cli_path))
                try:
                    import cli # type: ignore
                    cli.main()
                    return
                except ImportError as e:
                    last_import_error = e
                    if e.name and e.name != 'cli':
                        print(f"Error: Missing dependency for CLI: {e}")
                        sys.exit(1)
                except Exception as e:
                    print(f"Error: Failed to start CLI: {e}")
                    sys.exit(1)

            if last_import_error:
                 print(f"Error: Could not load cli.py: {last_import_error}")
            else:
                 print("Error: cli.py not found.")
            sys.exit(1)
        case "serve":
            open_cxb = False
            if "--open-cxb" in sys.argv:
                open_cxb = True
                sys.argv.remove("--open-cxb")
            
            if "--cxb-config" in sys.argv:
                idx = sys.argv.index("--cxb-config")
                if idx + 1 < len(sys.argv):
                    os.environ["DMART_CXB_CONFIG"] = sys.argv[idx + 1]
                    sys.argv.pop(idx + 1)
                sys.argv.pop(idx)
            
            settings.load_cxb_config()
                
            if open_cxb:
                host = settings.listening_host
                if host == "0.0.0.0":
                    host = "127.0.0.1"
                url = f"http://{host}:{settings.listening_port}{settings.cxb_url}/"
                def open_browser():
                    time.sleep(2)
                    webbrowser.open(url)
                
                import threading
                threading.Thread(target=open_browser, daemon=True).start()

            from main import main as server
            asyncio.run(server())
        case "health-check":
            from data_adapters.file.health_check import main as health_check
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
            from data_adapters.file.create_index import main as create_index
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
            from utils.exporter import main as exporter, exit_with_error, OUTPUT_FOLDER_NAME, validate_config, extract
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
            print_formatted(settings.model_dump_json())
        case "set_password":
            import set_admin_passwd  # noqa: F401
        case "archive":
            from data_adapters.file.archive import archive
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
            from data_adapters.sql.json_to_db_migration import main as json_to_db_migration
            asyncio.run(json_to_db_migration())
        case "db_to_json":
            from data_adapters.sql.db_to_json_migration import main as db_to_json_migration
            db_to_json_migration()
        case "update_query_policies":
            from data_adapters.sql.update_query_policies import main as update_query_policies
            update_query_policies()
        case "help":
            print("Available commands:")
            print(commands)
        case "version":
            info_json_path = Path(__file__).resolve().parent / "info.json"
            tag = None
            if info_json_path.exists():
                with open(info_json_path) as info:
                    tag = json.load(info).get("tag")
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
                    data = json.load(info)
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

                data = {
                    "commit_hash": version,
                    "date": version_date,
                    "branch": branch,
                    "tag": tag
                }
            print_formatted(data)
        case "init":
            sample_spaces_path = Path(__file__).resolve().parent / "sample" / "spaces"
            if not sample_spaces_path.exists():
                print("Error: Sample spaces not found in the package.")
                sys.exit(1)

            target_path = Path.home() / ".dmart" / "spaces"

            try:
                if target_path.exists():
                    shutil.rmtree(target_path)
                shutil.copytree(sample_spaces_path, target_path)
                print(f"Initialized sample spaces at {target_path}")
            except Exception as e:
                print(f"Error initializing sample spaces: {e}")
                sys.exit(1)
        case "migrate":
            import configparser
            import tempfile
            
            dmart_root = Path(__file__).resolve().parent
            alembic_ini_path = dmart_root / "alembic.ini"
            
            if not alembic_ini_path.exists():
                print(f"Error: alembic.ini not found at {alembic_ini_path}")
                sys.exit(1)

            config = configparser.ConfigParser()
            config.read(alembic_ini_path)

            if "sqlite" in settings.database_driver:
                db_url = f"{settings.database_driver}:///{settings.database_name}"
            else:
                db_url = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}/{settings.database_name}"

            config.set('alembic', 'sqlalchemy.url', db_url)
            config.set('alembic', 'script_location', str(dmart_root / "alembic"))
            config.set('alembic', 'prepend_sys_path', str(dmart_root))

            temp_config_path = ""
            try:
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".ini") as temp_config_file:
                    config.write(temp_config_file)
                    temp_config_path = temp_config_file.name

                alembic_cli_args = sys.argv[1:]
                if not alembic_cli_args:
                    alembic_cli_args = ["upgrade", "head"]

                command = [sys.executable, "-m", "alembic", "-c", temp_config_path] + alembic_cli_args
                
                result = subprocess.run(command, capture_output=True, text=True, check=False) # type: ignore

                if result.returncode == 0:
                    print("Alembic command finished.")
                    if result.stdout:
                        print(result.stdout)
                    if result.stderr:
                        print(result.stderr)
                else:
                    print(f"Error during alembic command (exit code: {result.returncode}):")
                    if result.stdout:
                        print("--- stdout ---")
                        print(result.stdout)
                    if result.stderr:
                        print("--- stderr ---")
                        print(result.stderr)
                    sys.exit(1)

            finally:
                if temp_config_path and os.path.exists(temp_config_path):
                    os.remove(temp_config_path)
        case "test":
            script_dir = Path(__file__).resolve().parent
            source_script_path = script_dir / "curl.pypi.sh"
            
            if not source_script_path.exists():
                print("Error: curl.sh not found in the package.")
                sys.exit(1)
            
            dmart_home_dir = Path.home() / ".dmart"
            dmart_home_dir.mkdir(parents=True, exist_ok=True)
            
            target_script_path = dmart_home_dir / "curl.sh"
            if not target_script_path.exists():
                shutil.copy2(source_script_path, target_script_path)
            
            source_test_dir = script_dir / "sample" / "test"
            target_test_dir = dmart_home_dir / "test"
            
            if source_test_dir.exists() and not target_test_dir.exists():
                shutil.copytree(source_test_dir, target_test_dir)

            try:
                subprocess.run(["bash", str(target_script_path)], check=True, cwd=dmart_home_dir)
            except subprocess.CalledProcessError as e:
                print(f"Error: The test script failed with exit code {e.returncode}.")
                sys.exit(e.returncode)
        case "apply_plugin_config":
            patch_plugin_configs()

if __name__ == "__main__":
    main()
