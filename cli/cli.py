#!/usr/bin/env python3

import os
from prompt_toolkit import PromptSession
import sys
from rich import pretty
from rich import print
from rich.console import Console
from pydantic import BaseSettings
import requests
import re

# from rich.tree import Tree
from rich.table import Table
from dataclasses import dataclass
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import Completer, Completion  # , FuzzyCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.cursor_shapes import CursorShape
from rich.traceback import install
import json
import pathlib
from enum import Enum
import termios, tty


install(show_locals=False)

KEYWORDS = [
    "ls",
    "switch",
    "mv",
    "cat",
    "cd",
    "rm",
    "print",
    "pwd",
    "help",
    "mkdir",
    "schema",
    "create",
    "attach",
    "request",
    "csv",
    "progress",
]

style = Style.from_dict(
    {
        "completion-menu.completion": "bg:#008888 #ffffff",
        "completion-menu.completion.current": "bg:#00aaaa #000000",
        "scrollbar.background": "bg:#88aaaa",
        "scrollbar.button": "bg:#222222",
        "prompt": "#dddd22 bold",
    }
)

console = Console()
pretty.install()


class Settings(BaseSettings):
    url: str = "http://localhost:8282"
    shortname: str = "dmart"
    password: str = "password"
    query_limit: int = 100
    retrieve_json_payload: bool = True
    default_space: str = "management"
    pagination: int = 5

    class Config:
        env_file = os.getenv("CONFIG_ENV", "config.ini")  # ~/.dm/config.ini"
        env_file_encoding = "utf-8"


settings = Settings()


class CLI_MODE(str, Enum):
    REPL = "REPL"
    CMD = "CMD"
    SCRIPT = "SCRIPT"


mode = CLI_MODE.REPL


class SpaceManagmentType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class DMart:
    session = requests.Session()
    headers = {"Content-Type": "application/json"}
    dmart_spaces = []
    space_names = []
    current_space: str = settings.default_space
    current_subpath: str = "/"
    current_subpath_entries = []

    def __dmart_api(self, endpoint, json=None):
        url = f"{settings.url}{endpoint}"

        if json:
            response = self.session.post(url, headers=self.headers, json=json)
        else:
            response = self.session.get(url)

        response_body = response.json()
        if response.status_code != 200:
            print(f"[red]{endpoint}", end="\r")
        return response_body

    def create_content(self, endpoint, json):
        url = f"{settings.url}{endpoint}"

        response = self.session.post(url, headers=self.headers, json=json)

        if response.status_code != 200:
            print(endpoint, response.json())
        return response.json()

    def delete(self, spacename, subpath, shortname, resource_type):
        endpoint = "/managed/request"
        json = {
            "space_name": spacename,
            "request_type": "delete",
            "records": [
                {
                    "resource_type": resource_type,
                    "subpath": subpath,
                    "shortname": shortname,
                    "attributes": {},
                }
            ],
        }
        return self.__dmart_api(endpoint, json)

    def register(self, invitation):
        json = {
            "resource_type": "user",
            "spacename": "management",
            "subpath": "/users",
            "shortname": settings.shortname,
            "attributes": {"invitation": invitation, "password": settings.password},
        }
        self.__dmart_api("/user/create", json)

    def login(self):
        json = {"shortname": settings.shortname, "password": settings.password}
        response = self.__dmart_api("/user/login", json)
        if response["status"] == "success":
            self.headers = {
                **self.headers,
                "Authorization": f'Bearer {response["records"][0]["attributes"]["access_token"]}',
            }
        return response

    def profile(self):
        self.__dmart_api("/user/profile")

    def spaces(self):
        if not self.dmart_spaces:
            json = {
                "type": "spaces",
                "space_name": "management",
                "subpath": "/",
            }

            response = self.__dmart_api("/managed/query", json)
            self.dmart_spaces = response["records"]
            self.space_names = [one["shortname"] for one in self.dmart_spaces]
        return self.dmart_spaces

    def query(self, json):
        json["limit"] = settings.query_limit
        json["retrieve_json_payload"] = settings.retrieve_json_payload
        return self.__dmart_api("/managed/query", json)

    def meta(self, resource_type, space_name, subpath, shortname):
        endpoint = "managed/meta"
        url = f"{settings.url}/{endpoint}/{resource_type}/{space_name}/{subpath}/{shortname}"
        response = self.session.get(url)

        if response.status_code != 200:
            print(endpoint, response.json())
        return response.json()

    def payload(self, resource_type, space_name, subpath, shortname):
        endpoint = "managed/payload"
        url = f"{settings.url}/{endpoint}/{resource_type}/{space_name}/{subpath}/{shortname}.json"
        response = self.session.get(url)

        # if response.status_code != 200:
        #    print(endpoint, response.json())
        return response.status_code, response.json()

    def print_spaces(self):
        print_spaces = "Available spaces: "
        for one in self.space_names:
            if self.current_space == one:
                one = f" [bold yellow]{one}[/] "
            else:
                one = f" [blue]{one}[/] "
            print_spaces += one
        print(print_spaces)

    def list(self, folder_shortname):
        json = {
            "space_name": dmart.current_space,
            "type": "subpath",
            "subpath": f"{dmart.current_subpath}/{folder_shortname}",
            "retrieve_json_payload": True,
            "limit": 100,
        }
        ret = self.query(json)
        if (
            not folder_shortname
        ):  # Only update list of we are acting against current_subpath
            self.current_subpath_entries.clear()
            if "records" in ret:
                for one in ret["records"]:
                    self.current_subpath_entries.append(one)

    def get_mime_type(self, ext):
        match ext:
            case ".jfif" | ".jfif-tbnl" | ".jpe" | ".jpeg" | ".jpg":
                return "image/jpeg"
            case ".png":
                return "image/png"
            case ".json":
                return "application/json"

    def create_folder(self, shortname):
        json = {
            "space_name": self.current_space,
            "request_type": "create",
            "records": [
                {
                    "resource_type": "folder",
                    "subpath": self.current_subpath,
                    "shortname": shortname,
                    "attributes": {"is_active": True},
                }
            ],
        }
        endpoint = "/managed/request"
        return self.__dmart_api(endpoint, json)

    def manage_space(self, spacename, mode: SpaceManagmentType):
        endpoint = "/managed/space"
        json = {
            "space_name": spacename,
            "request_type": mode.value,
            "records": [
                {
                    "resource_type": "space",
                    "subpath": "/",
                    "shortname": spacename,
                    "attributes": {},
                }
            ],
        }
        return self.__dmart_api(endpoint, json)

    def create_entry(self, shortname, resource_type):
        endpoint = "/managed/request"
        json = {
            "space_name": self.current_space,
            "request_type": "create",
            "records": [
                {
                    "resource_type": resource_type,
                    "subpath": self.current_subpath,
                    "shortname": shortname,
                    "attributes": {"is_active": True},
                }
            ],
        }
        return self.__dmart_api(endpoint, json)

    def create_attachments(self, request_record: dict, payload_file):
        endpoint = f"{settings.url}/managed/resource_with_payload"
        with open("temp.json", "w") as request_record_file:
            json.dump(request_record, request_record_file)

        with open("temp.json", "rb") as request_file:
            with open(payload_file, "rb") as media_file:
                request_file.seek(0)
                data = [
                    (
                        "request_record",
                        ("record.json", request_file, "application/json"),
                    ),
                    (
                        "payload_file",
                        (
                            media_file.name.split("/")[-1],
                            media_file,
                            self.get_mime_type(pathlib.Path(payload_file).suffix),
                        ),
                    ),
                ]
                response = self.session.post(
                    endpoint,
                    data={"space_name": self.current_space},
                    files=data,
                    headers=self.headers,
                )
                if response.status_code != 200:
                    print(endpoint, response.json())

                os.remove("temp.json")
                return response.json()

    def upload_csv(self, subpath, schema_shortname, payload_file):
        with open(payload_file, "rb") as media_file:
            endpoint = f"{settings.url}/managed/resources_from_csv/content/{dmart.current_space}/{subpath}/{schema_shortname}"
            response = self.session.post(
                endpoint,
                files={"resources_file": media_file},
                headers=self.headers,
            )
            if response.status_code != 200:
                print(endpoint, response.json())

            return response.json()

    def upload_schema(self, shortname, payload_file_path):
        data = {
            "resource_type": "schema",
            "subpath": "schema",
            "shortname": shortname,
            "attributes": {"schema_shortname": "meta_schema", "is_active": True},
        }
        endpoint = f"{settings.url}/managed/resource_with_payload"

        with open("temp.json", "w") as request_record_file:
            json.dump(data, request_record_file)

        with open("temp.json", "rb") as request_record:
            with open(payload_file_path, "rb") as payload_file:
                files = {
                    "space_name": (None, self.current_space),
                    "request_record": request_record,
                    "payload_file": payload_file,
                }
                headers = {**self.headers}
                del headers["Content-Type"]
                response = self.session.post(
                    endpoint,
                    files=files,
                    headers=headers,
                )

                if response.status_code != 200:
                    print(endpoint, response.json())

                return response.json()

    def upload_folder(self, folder_schema_path):
        endpoint = f"{settings.url}/managed/request"
        with open(folder_schema_path, "r") as folder_schema:
            response = self.session.post(
                url=endpoint,
                data=folder_schema,
                headers=self.headers,
            )
            if response.status_code != 200:
                print(endpoint, response.json())
            else:
                print(response.json())
        return response.json()

    def move(
        self,
        resource_type,
        source_path,
        source_shortname,
        destination_path,
        destination_shortname,
    ):
        endpoint = "/managed/request"
        data = {
            "space_name": self.current_space,
            "request_type": "move",
            "records": [
                {
                    "resource_type": resource_type,
                    "subpath": self.current_subpath,
                    "shortname": source_shortname,
                    "attributes": {
                        "src_subpath": source_path,
                        "src_shortname": source_shortname,
                        "dest_subpath": destination_path,
                        "dest_shortname": destination_shortname,
                    },
                }
            ],
        }
        return self.__dmart_api(endpoint, data)


dmart = DMart()


class CustomCompleter(Completer):
    def get_completions(self, document, _):  # complete_event):
        # cmd = document.get_word_before_cursor()
        cmd = document.text
        arg = document.get_word_under_cursor()
        if len(cmd) < 2 or re.match(r"^\s*$", cmd):
            for one in KEYWORDS:
                if one.startswith(arg):
                    yield Completion(one, start_position=-len(arg))
        elif re.match(r"^\s*\w+\s+", cmd):
            if cmd.startswith("s"):
                for one in dmart.space_names:
                    if one.startswith(arg):
                        yield Completion(one, start_position=-len(arg))
            else:
                for one in dmart.current_subpath_entries:
                    if one["shortname"].startswith(
                        arg
                    ):  #  and (("cd" in cmd and one["resource_type"]=="folder") or one["resource_type"] != "folder"):
                        if "cd" in cmd and one["resource_type"] == "folder":
                            yield Completion(
                                one["shortname"],
                                start_position=-len(arg),
                                display_meta=one["resource_type"],
                            )
                        elif "cd" not in cmd:
                            yield Completion(
                                one["shortname"],
                                start_position=-len(arg),
                                display_meta=one["resource_type"],
                            )


def bottom_toolbar():
    return HTML(
        f'<b>{dmart.current_space}</b> : <b><style bg="ansired">{dmart.current_subpath}</style></b>'
    )


def check_update_space(space, subpath=None):
    for one in dmart.space_names:
        if one.startswith(space) and not one.startswith(dmart.current_space):
            dmart.current_space = one
            print("Current space switched to:", dmart.current_space)
            if subpath is not None:
                dmart.current_subpath = subpath
            dmart.list("")
            dmart.print_spaces()
            break


def action(text: str):
    old_space, old_subpath = dmart.current_space, dmart.current_subpath
    match text.split():
        case ["h" | "help" | "?"]:
            table = Table(title="Help")
            table.add_column("Command")
            table.add_column("Description")
            table.add_row(
                r"[blue]s[paces][/] [green]\[space_name][/]",
                "List availble spaces or switch to space",
            )
            table.add_row(
                r"[blue]ls[/] [green]\[folder_name][/]",
                "List entries under current subpath",
            )
            table.add_row("[blue]pwd[/]", "Print current subpath")
            table.add_row("[blue]cd[/] [green]folder_name[/]", "Enter the folder")
            table.add_row("[blue]cd ..[/]", "Go one-level up with the subpath")
            table.add_row(
                r"[blue]p\[rint][/blue] [green]shortname[/]",
                "Print meta data for the entry shortname under current subpath",
            )
            table.add_row(
                r"[blue]c\[at][/] [green]shortname[/]",
                "Print the json payload (only) for th entry shortnae under current subpath",
            )
            table.add_row(
                "[blue]rm[/] [green]shortname|*[/]",
                "Delete the shortname (entry or attachment)",
            )
            table.add_row(
                "[blue]create folder <subpath>[/]", "Create folder for current space"
            )
            table.add_row(
                "[blue]upload csv <shortname> <schema_shortname> <csv_file>[/]",
                "Upload data to the current space",
            )
            table.add_row(
                "[blue]upload schema <shortname> <json_file>[/]",
                "Upload schema to the current space",
            )
            table.add_row(
                "[blue]request <resource_type> <json_file>[/]",
                "Add/Manage a resource to/in the space",
            )
            table.add_row(
                "[blue]progress <subpath> <shortname> <action>[/]",
                "Progress a ticket into a new state using an action",
            )
            table.add_row(
                "[blue]move <resource_type> <source> <destination>[/]", "Move resource"
            )
            table.add_row("[blue]exit|Ctrl+d[/]", "Exit the app")
            table.add_row("[blue]help|h|?[/]", "Show this help")
            print(table)
        case ["mkdir", dir_shortname]:
            print(dmart.create_folder(dir_shortname))
        case ["attach", *args]:
            shortname = None
            entry_shortname = None
            payload_file = None
            payload_type = None

            shortname = args[0]
            entry_shortname = args[1]
            payload_type = args[2]
            payload_file = args[3]

            print(
                dmart.create_attachments(
                    {
                        "shortname": shortname,
                        "resource_type": payload_type,
                        "subpath": f"{dmart.current_subpath}/{entry_shortname}",
                        "attributes": {"is_active": True},
                    },
                    payload_file,
                )
            )
        case ["upload", "schema", *args]:
            shortname = None
            payload_file = None

            if len(args) == 3:
                search = re.search(r"@\w+", args[2])
                if not search:
                    print(f"[red]Malformated Command")
                    return
                space = search.group()
                space = space.replace("@", "")
                check_update_space(space)
                dmart.current_subpath = args[2].replace(f"@{space}/", "")
                dmart.list("")
            shortname = args[0]
            payload_file = args[1]

            dmart.upload_schema(shortname, payload_file)
            check_update_space(old_space)
            dmart.current_subpath = old_subpath
            dmart.list("")
        case ["create", *args]:
            shortname = None
            resource_type = None
            if len(args) == 3:
                search = re.search(r"@\w+", args[2])
                if not search:
                    print(f"[red]Malformated Command")
                    return
                space = search.group()
                space = space.replace("@", "")
                check_update_space(space)
                dmart.current_subpath = args[2].replace(f"@{space}", "")
                dmart.list("")
            shortname = args[0]
            resource_type = args[1]

            if args[0] == "space":
                print(dmart.manage_space(args[1], SpaceManagmentType.CREATE))
            else:
                print(dmart.create_entry(resource_type, shortname))

            check_update_space(old_space)
            dmart.current_subpath = old_subpath
            dmart.list("")
        case ["move", type, source, destination]:
            if not source.startswith("/"):
                source += f"{dmart.current_subpath}/{source}"
            if not destination.startswith("/"):
                destination += f"{dmart.current_subpath}/{destination}"
            source_path = "/".join(source.split("/")[:-1])
            source_shortname = source.split("/")[-1]
            destination_path = "/".join(destination.split("/")[:-1])
            destination_shortname = destination.split("/")[-1]
            print(
                dmart.move(
                    type,
                    source_path,
                    source_shortname,
                    destination_path,
                    destination_shortname,
                )
            )

        case ["progress", ticket_subpath, ticket_shortname, new_state]:
            endpoint = f"{settings.url}/managed/progress-ticket/{dmart.current_space}/{ticket_subpath}/{ticket_shortname}/{new_state}"
            response = dmart.session.put(
                url=endpoint,
                data={},
                headers=dmart.headers,
            )
            print(response.json())
        case ["request", *args]:
            folder_schema_path = None

            is_content = args[0] == "content"

            if (len(args) == 3 and is_content) or (len(args) == 2 and not is_content):
                search = re.search(r"@\w+", args[1])
                if not search:
                    print(f"[red]Malformated Command")
                    return
                space = search.group()
                space = space.replace("@", "")
                check_update_space(space)
                dmart.current_subpath = args[1].replace(f"@{space}/", "")
                dmart.list("")

            if is_content:
                with open(args[1]) as f:
                    return print(
                        dmart.create_content("/managed/request", json.load(f)), end="\r"
                    )
            else:
                folder_schema_path = args[0]
                print(dmart.upload_folder(folder_schema_path), end="\r")

            check_update_space(old_space)
            dmart.current_subpath = old_subpath
            dmart.list("")
        case ["query", shortname]:
            action(f"query {shortname}")
            action("ls")
            action("cd ..")
            pass
        case ["upload", "csv", *args]:
            subpath = None
            schema_shortname = None
            payload_file = None

            if len(args) == 4:
                search = re.search(r"@\w+", args[3])
                if not search:
                    print(f"[red]Malformated Command")
                    return
                space = search.group()
                space = space.replace("@", "")
                check_update_space(space)
                dmart.current_subpath = args[3].replace(f"@{space}/", "")
                dmart.list("")
            subpath = args[0]
            schema_shortname = args[1]
            payload_file = args[2]

            print(dmart.upload_csv(subpath, schema_shortname, payload_file))
            check_update_space(old_space)
            dmart.current_subpath = old_subpath
            dmart.list("")
        case ["rm", "*"]:
            dmart.list("")
            for one in dmart.current_subpath_entries:
                shortname = one["shortname"]
                resource_type = one["resource_type"]
                if shortname and resource_type:
                    print(
                        shortname,
                        dmart.delete(
                            dmart.current_space,
                            dmart.current_subpath,
                            shortname,
                            resource_type,
                        ),
                    )
        case ["rm", *content]:
            if content[0] == "space":
                print(dmart.manage_space(content[1], SpaceManagmentType.DELETE))
            else:
                content = content[0]
                if content.startswith("@"):
                    path = content[1]
                    search = re.search(r"@\w+", content)
                    if not search:
                        print(f"[red]Malformated Command")
                        return
                    space = search.group()
                    space = space.replace("@", "")
                    check_update_space(space)
                    dmart.list("")
                    content = content.replace(f"@{space}/", "")
                # print(dmart.current_subpath_entries)
                shortname = ""
                resource_type = ""
                for one in dmart.current_subpath_entries:
                    if one["shortname"] == content:
                        shortname = one["shortname"]
                        resource_type = one["resource_type"]
                if shortname and resource_type:
                    print(
                        dmart.delete(
                            dmart.current_space,
                            dmart.current_subpath,
                            shortname,
                            resource_type,
                        )
                    )
                else:
                    print(f"item not found")
                check_update_space(old_space)
                dmart.list("")
        case "pwd":
            print(f"{dmart.current_space}:{dmart.current_subpath}")
        case ["cd", ".."]:
            if dmart.current_subpath != "/":
                dmart.current_subpath = "/".join(dmart.current_subpath.split("/")[:-1])
            if not dmart.current_subpath:
                dmart.current_subpath = "/"
            dmart.list("")
            print(f"[yellow]Switched subpath to:[/] [green]{dmart.current_subpath}[/]")
        case ["p" | "print", content]:
            shortname = ""
            resource_type = ""
            shortname = content
            for one in dmart.current_subpath_entries:
                if one["shortname"].startswith(shortname):
                    shortname = one["shortname"]
                    resource_type = one["resource_type"]
            if shortname and resource_type:
                print(
                    dmart.meta(
                        resource_type,
                        dmart.current_space,
                        dmart.current_subpath,
                        shortname,
                    )
                )
            else:
                print(f"item not found")
        case ["cd", directory]:
            if directory.startswith("@"):
                search = re.search(r"@\w+", directory)
                if not search:
                    print(f"[red]Malformated Command")
                    return
                space = search.group()
                space = space.replace("@", "")
                check_update_space(space)
                dmart.current_subpath = directory.replace(f"@{space}/", "")
                dmart.list("")
                directory = dmart.current_subpath
            new_subpath = ""
            for one in dmart.current_subpath_entries:
                if (
                    one["shortname"].startswith(directory)
                    and one["resource_type"] == "folder"
                ):
                    new_subpath = (
                        ""
                        if dmart.current_subpath == "/" or dmart.current_subpath == ""
                        else dmart.current_subpath
                    )
                    if new_subpath != "":
                        new_subpath += "/"
                    new_subpath += one["shortname"]
                    dmart.current_subpath = new_subpath
                    dmart.list("")
                    print(
                        f"[yellow]Switched subpath to:[/] [green]{dmart.current_subpath}[/]"
                    )
                    break
        case "cd":
            dmart.current_subpath = "/"
            dmart.list("")
            print(f"[yellow]Switched subpath to:[/] [green]{dmart.current_subpath}[/]")
        case ["c" | "cat", *extra_shortname]:
            dmart.list("")
            shortname = ""
            resource_type = ""
            record = {}
            if extra_shortname[0] == "*":
                for one in dmart.current_subpath_entries:
                    print(one)
            elif len(extra_shortname) > 0:
                shortname = extra_shortname[0]
                for one in dmart.current_subpath_entries:
                    if one["shortname"].startswith(shortname):
                        shortname = one["shortname"]
                        resource_type = one["resource_type"]
                        record = one
            if record is not None:
                print(record)
            else:
                print(f"[yellow]Item is not found[/]")
        case ["ls", *_extra_subpath]:
            extra_subpath = ""
            if len(_extra_subpath) >= 1 and _extra_subpath[0].isnumeric() == False:
                if _extra_subpath[0].startswith("@"):
                    search = re.search(r"@\w+", _extra_subpath[0])
                    if not search:
                        print(f"[red]Malformated Command")
                        return
                    space = search.group()
                    space = space.replace("@", "")
                    check_update_space(space)
                    dmart.current_subpath = _extra_subpath[0].replace(f"@{space}/", "")
                    dmart.list("")
                else:
                    dmart.current_subpath = _extra_subpath[0]
                    dmart.list("")
            elif len(_extra_subpath) > 2:
                print("Too many args passed !")

            if extra_subpath == "":
                for one in dmart.current_subpath_entries:
                    if one["shortname"].startswith(extra_subpath):
                        extra_subpath = one["shortname"]

            path = f"[yellow]{dmart.current_space}[/]:[blue]{dmart.current_subpath}"
            if dmart.current_subpath != "/":
                path = f"{path}/{extra_subpath}"
            else:
                path = f"{path}{extra_subpath}"
            # tree = Tree(path)

            pagination_length = 0
            if len(_extra_subpath) >= 1 and _extra_subpath[-1].isnumeric():
                pagination_length = int(_extra_subpath[-1])
            else:
                pagination_length = settings.pagination

            pagination_bucket = []
            bucket = []
            idx = 0
            for one in dmart.current_subpath_entries:
                icon = ":page_facing_up:"
                extra = ""
                if one["resource_type"] == "folder":
                    icon = ":file_folder:"
                if (
                    "attributes" in one
                    and "payload" in one["attributes"]
                    and "content_type" in one["attributes"]["payload"]
                ):
                    schema = ",schema="
                    if "schema_shortname" in one["attributes"]["payload"]:
                        schema += one["attributes"]["payload"]["schema_shortname"]
                    extra = f"[yellow](payload:type={one['attributes']['payload']['content_type']}{schema})[/]"

                idx += 1
                # tree.add(f"{icon} [green]{one['shortname']}[/] {extra}")
                bucket.append(f"{icon} [green]{one['shortname']}[/] {extra}")
                if idx == pagination_length:
                    idx = 0
                    pagination_bucket.append(bucket)
                    bucket = []

            if len(bucket) != 0:
                pagination_bucket.append(bucket)
            idx = 0
            c = ""
            if len(pagination_bucket) == 1:
                for bucket in pagination_bucket[0]:
                    print(bucket)
            else:
                while True:
                    if len(pagination_bucket) == 0:
                        break

                    for bucket in pagination_bucket[idx]:
                        print(bucket)

                    if idx >= len(pagination_bucket) - 1:
                        break

                    print("q: quite, n: next")
                    fd = sys.stdin.fileno()
                    old_settings = termios.tcgetattr(fd)
                    try:
                        tty.setraw(fd)
                        c = sys.stdin.readline(1)

                        if c == "q":
                            break
                        if c == "n" or c == "\r":
                            idx += 1
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                # c = input("q: quite, b: previous, n: next = ")
            # print(tree)
            dmart.current_space, dmart.current_subpath = old_space, old_subpath
            dmart.list("")
        case ["s" | "switch", *space]:
            if len(space) == 0:
                dmart.print_spaces()
                return
            match = False
            for one in dmart.space_names:
                if one.startswith(space[0]):
                    print(
                        f"Switching current space from {dmart.current_space} to {one} / {space}"
                    )
                    dmart.current_space = one
                    dmart.list("")
                    match = True
                    dmart.print_spaces()
                    break
            if not match:
                print(f"Requested space {space} not found")
        case _:
            print(f"[red]Command[/] [yello]{text}[/] [red]unknown[/]")


var = {}


def parsing_variables(sliced_command):
    for i in range(len(sliced_command)):
        search = re.search(r"\$\w*", sliced_command[i])
        if search is not None:
            if v := search[0]:
                sliced_command[i] = sliced_command[i].replace(v, var.get(v, ""))
    return sliced_command


if __name__ == "__main__":
    # print(Panel.fit("For help, type : [bold]?[/]", title="DMart Cli"))
    print("[bold][green]DMART[/] [yellow]Command line interface[/][/]")
    print(
        f"Connecting to [yellow]{settings.url}[/] user: [yellow]{settings.shortname}[/]"
    )

    ret = dmart.login()
    if ret["status"] == "failed":
        print("Login failed")
        exit(1)
    dmart.profile()
    spaces = dmart.spaces()
    dmart.current_space = settings.default_space  # dmart.space_names[0]

    dmart.list("")
    # print("Available spaces:", space_names)
    # print("Current space:",  current_space)
    dmart.print_spaces()
    print("[red]Type [bold]?[/] for help[/]")
    # current_subpath = "/"
    # session = PromptSession(lexer=PygmentsLexer(DmartLexer), completer=dmart_completer, style=style)

    session = PromptSession(
        style=style, completer=CustomCompleter(), history=FileHistory(".cli_history")
    )

    if len(sys.argv) >= 2:
        if sys.argv[1] == "s":
            mode = CLI_MODE.SCRIPT
        elif sys.argv[1] == "c":
            mode = CLI_MODE.CMD
            if sys.argv[3].startswith("/"):
                check_update_space(sys.argv[2], sys.argv[3])
                del sys.argv[2]
                del sys.argv[2]
            else:
                check_update_space(sys.argv[2])
                del sys.argv[2]
        del sys.argv[0]
        del sys.argv[0]

    if mode == CLI_MODE.CMD:
        print(sys.argv)
        action(" ".join(sys.argv))
    elif mode == CLI_MODE.SCRIPT:
        with open(sys.argv[1], "r") as commands:
            is_comment_block = False
            for command in commands:
                if (
                    command.startswith("#")
                    or command.startswith("//")
                    or command == "\n"
                ):
                    continue
                elif command.startswith("/*"):
                    is_comment_block = True
                    continue
                elif command.startswith("*/"):
                    is_comment_block = False
                    continue
                elif is_comment_block:
                    continue

                print("[green]> ", command)
                sliced_command = command.split()

                if sliced_command[0] == "VAR":
                    var[sliced_command[1]] = sliced_command[2]
                    continue

                sliced_command = parsing_variables(sliced_command)

                action(" ".join(sliced_command))
    elif mode == CLI_MODE.REPL:
        while True:
            try:
                text = session.prompt(
                    [("class:prompt", "❯ ")],  # ≻≻
                    # cursor=CursorShape.BLINKING_BLOCK,
                    # cursor=CursorShape.BLINKING_BEAM,
                    cursor=CursorShape.BLINKING_UNDERLINE,
                    bottom_toolbar=bottom_toolbar,
                    complete_in_thread=True,
                    complete_while_typing=True,
                )
                # remove whitespaces
                text = re.sub(r"^\s+", "", text)  # leading
                text = re.sub(r"\s+$", "", text)  # trailing
                text = re.sub(
                    r"\s+", " ", text
                )  # replace multiple inline whitespaces with one
                if text in ["exit", "q", "quit"]:
                    break
                else:
                    if text == "":
                        continue
                    action(text)
            except KeyboardInterrupt as ex:
                print(repr(ex))
                continue
            except EOFError as ex:
                print("[green]Exiting ...[/]")
                break
        # else:
        #    print('You entered:', repr(text))
    print("[yellow]Good bye![/]")
