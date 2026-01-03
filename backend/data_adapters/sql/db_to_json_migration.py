#!/usr/bin/env -S BACKEND_ENV=config.env python3

import os
import json
from datetime import datetime
from sqlmodel import Session, create_engine, select, col
from data_adapters.sql.create_tables import (
    Entries,
    Users,
    Attachments,
    Roles,
    Permissions,
    Histories,
    Spaces,
)
from models.core import Payload
from utils.settings import settings
from models import core
import base64

postgresql_url = f"{settings.database_driver.replace('+asyncpg','+psycopg')}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}/{settings.database_name}"
engine = create_engine(postgresql_url, echo=False)

def subpath_checker(subpath: str):
    if subpath.endswith("/"):
        subpath = subpath[:-1]
    if not subpath.startswith("/"):
        subpath = "/" + subpath
    return subpath

def ensure_directory_exists(path: str):
    os.makedirs(path, exist_ok=True)

def clean_json(data: dict):
    if not isinstance(data, dict):
        return data

    for key, value in list(data.items()):
        if key in ["tags", "mirrors", "active_plugins", "roles", "groups"]:
            continue
        if not value:
            del data[key]
        elif isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, dict):
            clean_json(value)

    return data

def write_json_file(path, data):
    with open(path, "w") as f:
        if data.get("query_policies", False):
            del data["query_policies"]
        clean = clean_json(data)
        json.dump(clean, f, indent=2, default=str)

def write_file(path, data):
    with open(path, "w") as f:
        f.write(data)

def write_binary_file(path, data):
    with open(path, "wb") as f:
        f.write(data)

def process_attachments(session, space_folder):
    attachments = session.exec(select(Attachments)).all()
    for attachment in attachments:
        subpath = subpath_checker(attachment.subpath)

        parts = subpath.split('/')
        parts.insert(-1, '.dm')
        new_path = '/'.join(parts)

        dir_path = f"{space_folder}/{attachment.space_name}{new_path}"
        ensure_directory_exists(dir_path)

        media_path = f"{dir_path}/attachments.{attachment.resource_type}"
        ensure_directory_exists(media_path)
        if attachment.payload.get("body", None) is not None:
            if attachment.payload["content_type"] == 'json':
                write_json_file(f"{media_path}/{attachment.shortname}.json", attachment.payload.get("body", {}))
                attachment.payload["body"] = f"{attachment.shortname}.json"
            else:
                if attachment.media is None:
                    print(f"Warning: empty media for @{attachment.space_name}:{attachment.subpath}/{attachment.shortname}")
                    continue
                write_binary_file(f"{media_path}/{attachment.payload['body']}", attachment.media)
        _attachment = attachment.model_dump()

        del _attachment["media"]
        del _attachment["resource_type"]
        write_json_file(f"{media_path}/meta.{attachment.shortname}.json", _attachment)

def process_entries(session, space_folder):
    entries = session.exec(select(Entries)).all()
    for entry in entries:
        subpath = subpath_checker(entry.subpath)
        dir_path = f"{space_folder}/{entry.space_name}{subpath}".replace("//", "/")  # Ensure absolute path
        ensure_directory_exists(dir_path)

        if entry.resource_type == "folder":
            dir_meta_path = f"{dir_path}/{entry.shortname}/.dm/".replace("//", "/")
            ensure_directory_exists(dir_meta_path)
            _entry = entry.model_dump()
            body = None
            if _entry.get("payload", None) is not None:
                if _entry.get("payload", None).get("body", None) is not None:
                    body = _entry.get("payload", None)["body"]
                _entry["payload"]["body"] = f"{entry.shortname}.json"
            del _entry["space_name"]
            del _entry["subpath"]
            del _entry["resource_type"]

            write_json_file(f"{dir_meta_path}/meta.folder.json", _entry)
            if body is not None:
                write_json_file(f"{dir_path}/{entry.shortname}.json", body)
            continue

        dir_meta_path = f"{dir_path}/.dm/{entry.shortname}".replace("//", "/")
        ensure_directory_exists(dir_meta_path)

        _entry = entry.model_dump()
        del _entry["space_name"]
        del _entry["subpath"]
        del _entry["resource_type"]

        if entry.payload:
            if "content_type" not in entry.payload:
                print(f"Warning : empty content type for @{entry.space_name}:{entry.subpath}/{entry.shortname}")
            elif entry.payload["content_type"] == core.ContentType.json:

                if _entry["payload"].get("body", None) is not None:
                    if isinstance(_entry["payload"].get("body", None), dict):
                        write_json_file(f"{dir_path}/{entry.shortname}.json", _entry["payload"].get("body", None))

                    _entry["payload"]["body"] = f"{entry.shortname}.json"
                    
            elif entry.payload["content_type"] == core.ContentType.html:
                if _entry["payload"].get("body", None) is not None:
                    with open(f"{dir_path}/{entry.shortname}.html", "w", encoding="utf-8") as f:
                        f.write(_entry["payload"]["body"])
                    _entry["payload"]["body"] = f"{entry.shortname}.html"
                    
            elif entry.payload["content_type"] == core.ContentType.image:
                if _entry["payload"].get("body", None) is not None:
                    body_data = _entry["payload"]["body"]
                    
                    if isinstance(body_data, str):
                        if "." in body_data and any(body_data.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp']):
                            _entry["payload"]["body"] = body_data
                            print(f"Image reference: @{entry.space_name}:{entry.subpath}/{entry.shortname} -> {body_data}")
                        else:
                            try:
                                if len(body_data) % 4 == 0:
                                    decoded_data = base64.b64decode(body_data, validate=True)
                                    
                                    extension = "png"
                                    if "content_sub_type" in entry.payload:
                                        extension = entry.payload["content_sub_type"].lower()
                                    
                                    filename = f"{entry.shortname}.{extension}"
                                    with open(f"{dir_path}/{filename}", "wb") as f:
                                        f.write(decoded_data)
                                    _entry["payload"]["body"] = filename
                                else:
                                    print(f"Warning: Invalid image data for @{entry.space_name}:{entry.subpath}/{entry.shortname}")
                                    _entry["payload"]["body"] = body_data
                            except Exception as e:
                                print(f"Error processing image @{entry.space_name}:{entry.subpath}/{entry.shortname}: {e}")
                                _entry["payload"]["body"] = body_data
                    else:
                        extension = "png" 
                        if "content_sub_type" in entry.payload:
                            extension = entry.payload["content_sub_type"].lower()
                        
                        filename = f"{entry.shortname}.{extension}"
                        with open(f"{dir_path}/{filename}", "wb") as f:
                            f.write(body_data)
                        _entry["payload"]["body"] = filename


            else:
                print(f"Unprocessed content type({entry.payload['content_type']}): @{entry.space_name}:{entry.subpath}/{entry.shortname}")

        if entry.resource_type != "ticket":
            del _entry["state"]
            del _entry["is_open"]
            del _entry["reporter"]
            del _entry["workflow_shortname"]
            del _entry["collaborators"]
            del _entry["resolution_reason"]

        write_json_file(f"{dir_meta_path}/meta.{entry.resource_type}.json", _entry)

def process_users(session, space_folder):
    users = session.exec(select(Users)).all()
    dir_path = f"{space_folder}/management/users" # Ensure absolute path
    for user in users:
        dir_meta_path = f"{dir_path}/.dm/{user.shortname}"
        ensure_directory_exists(dir_meta_path)

        _user = user.model_dump()
        del _user["space_name"]
        del _user["resource_type"]
        if _user.get("payload", None) and _user["payload"].get("body" , None):
            write_json_file(
                f"{dir_path}/{user.shortname}.json",
                _user["payload"]["body"]
            )
            _user["payload"]["body"] = f"{user.shortname}.json"

        write_json_file(f"{dir_meta_path}/meta.user.json", _user)

def process_roles(session, space_folder):
    roles = session.exec(select(Roles)).all()
    dir_path = f"{space_folder}/management/roles/.dm"  # Ensure absolute path
    for role in roles:
        ensure_directory_exists(f"{dir_path}/{role.shortname}")

        _role = role.model_dump()
        del _role["space_name"]
        del _role["subpath"]
        del _role["resource_type"]

        write_json_file(f"{dir_path}/{role.shortname}/meta.role.json", _role)

def process_permissions(session, space_folder):
    permissions = session.exec(select(Permissions)).all()
    dir_path = f"{space_folder}/management/permissions/.dm"
    for permission in permissions:
        ensure_directory_exists(f"{dir_path}/{permission.shortname}")

        _permission = permission.model_dump()
        del _permission["space_name"]
        del _permission["subpath"]
        del _permission["resource_type"]

        write_json_file(f"{dir_path}/{permission.shortname}/meta.permission.json", _permission)

def process_histories(session, space_folder):
    histories = session.exec(select(Histories)).all()
    for history in histories:
        dir_path = f"{space_folder}/{history.space_name}"  # Ensure absolute path
        ensure_directory_exists(dir_path)

        file_path = f"{dir_path}{history.subpath}/.dm/{history.shortname}"
        ensure_directory_exists(file_path)

        _history_one: str = history.model_dump_json()
        _history: dict = json.loads(_history_one)
        _history["shortname"] = "history"

        del _history["space_name"]
        del _history["subpath"]
        if _history.get("resource_type", None):
            del _history["resource_type"]
        with open(f"{file_path}/history.jsonl", "a+") as f:
            f.write(json.dumps(_history) + "\n")

def process_spaces(session, space_folder):
    spaces = session.exec(select(Spaces)).all()
    for space in spaces:
        dir_path = f"{space_folder}/{space.space_name}/.dm/"
        ensure_directory_exists(dir_path)

        _space = space.model_dump()
        del _space["space_name"]
        del _space["resource_type"]

        write_json_file(f"{dir_path}/meta.space.json", _space)

async def export_data_with_query(query, user_shortname):
    from utils.repository import serve_query

    space_folder = os.path.relpath(str(settings.spaces_folder))

    total, records = await serve_query(query, user_shortname)

    with (Session(engine) as session):
        space = session.exec(select(Spaces).where(col(Spaces.space_name) == query.space_name)).first()
        if space:
            dir_path = f"{space_folder}/{space.space_name}/.dm/"
            ensure_directory_exists(dir_path)

            _space = space.model_dump()
            del _space["space_name"]
            del _space["resource_type"]

            write_json_file(f"{dir_path}/meta.space.json", _space)
        if query.subpath and query.subpath != "/":
            path_parts = query.subpath.strip("/").split("/")
            current_path = ""

            for part in path_parts:
                current_path += f"/{part}"

                folder = session.exec(select(Entries).where(
                    (Entries.space_name == query.space_name) &
                    (Entries.subpath == str(current_path.rsplit("/", 1)[0] or "/")) &
                    (Entries.shortname == part) &
                    (Entries.resource_type == "folder")
                )).first()

                if folder:
                    folder_subpath = subpath_checker(folder.subpath)
                    folder_dir_path = f"{space_folder}/{folder.space_name}{folder_subpath}".replace("//", "/")
                    ensure_directory_exists(folder_dir_path)

                    dir_meta_path = f"{folder_dir_path}/{folder.shortname}/.dm/".replace("//", "/")
                    ensure_directory_exists(dir_meta_path)

                    _folder = folder.model_dump()
                    _folder = {
                        **_folder,
                        **_folder.get("attributes", {})
                    }
                    if "attributes" in _folder:
                        del _folder["attributes"]
                    body = None
                    if _folder and _folder.get("payload", None) is not None:
                        if _folder and _folder.get("payload", {}).get("body", None) is not None:
                            body = _folder.get("payload", {}).get("body", None)
                        _folder["payload"]["body"] = f"{folder.shortname}.json"

                    del _folder["space_name"]
                    del _folder["subpath"]
                    del _folder["resource_type"]

                    write_json_file(f"{dir_meta_path}/meta.folder.json", _folder)
                    if body is not None:
                        write_json_file(f"{folder_dir_path}/{folder.shortname}.json", body)

        for entry in records:
            subpath = subpath_checker(entry.subpath)
            dir_path = f"{space_folder}/{query.space_name}{subpath}".replace("//", "/")  # Ensure absolute path
            ensure_directory_exists(dir_path)

            if entry.resource_type == "folder":
                dir_meta_path = f"{dir_path}/{entry.shortname}/.dm/".replace("//", "/")
                ensure_directory_exists(dir_meta_path)
                _entry = entry.model_dump()
                body = None
                if _entry.get("payload", None) is not None:
                    if _entry.get("payload", {}).get("body", None) is not None:
                        body = _entry.get("payload",{}).get("body", None)
                    _entry["payload"]["body"] = f"{entry.shortname}.json"

                del _entry["subpath"]
                del _entry["resource_type"]

                _entry = {
                    **_entry,
                    **_entry.get("attributes", {})
                }
                if "attributes" in _entry:
                    del _entry["attributes"]

                write_json_file(f"{dir_meta_path}/meta.folder.json", _entry)
                if body is not None:
                    write_json_file(f"{dir_path}/{entry.shortname}.json", body)
                continue

            dir_meta_path = f"{dir_path}/.dm/{entry.shortname}".replace("//", "/")
            ensure_directory_exists(dir_meta_path)

            _entry = entry.model_dump()
            del _entry["subpath"]
            del _entry["resource_type"]

            if entry.attributes.get("payload"):
                if entry.attributes.get("payload", {}).get("content_type") == core.ContentType.json:
                    if _entry.get("attributes",{}).get("payload",{}).get("body", None) is not None:
                        if isinstance( _entry.get("attributes",{}).get("payload").get("body", None), dict):
                            write_json_file(f"{dir_path}/{entry.shortname}.json",  _entry.get("attributes",{}).get("payload").get("body", None))
                        _entry.get("attributes",{}).get("payload")["body"] = f"{entry.shortname}.json"

            _entry = {
                **_entry,
                **_entry.get("attributes",{})
            }
            if "attributes" in _entry:
                del _entry["attributes"]
            if "attachments" in _entry:
                del _entry["attachments"]

            write_json_file(f"{dir_meta_path}/meta.{entry.resource_type}.json", _entry)

            histories = session.exec(select(Histories).where(
                (Histories.space_name == query.space_name) &
                (Histories.subpath == entry.subpath) &
                (Histories.shortname == entry.shortname)
            )).all()

            for history in histories:
                file_path = f"{dir_path}/.dm/{entry.shortname}"
                ensure_directory_exists(file_path)

                _history_one: str = history.model_dump_json()
                _history: dict = json.loads(_history_one)
                _history["shortname"] = "history"

                del _history["space_name"]
                del _history["subpath"]
                if _history.get("resource_type", None):
                    del _history["resource_type"]
                with open(f"{file_path}/history.jsonl", "a+") as f:
                    f.write(json.dumps(_history) + "\n")

            attachments = session.exec(select(Attachments).where(
                (Attachments.space_name == query.space_name) &
                (Attachments.subpath == f"/{entry.subpath}/{entry.shortname}")
            )).all()

            __attachment = None
            for attachment in attachments:
                __attachment = attachment
                subpath = subpath_checker(attachment.subpath)

                parts = subpath.split('/')
                parts.insert(-1, '.dm')
                new_path = '/'.join(parts)

                dir_path = f"{space_folder}/{query.space_name}{new_path}"
                ensure_directory_exists(dir_path)

                media_path = f"{dir_path}/attachments.{attachment.resource_type}"
                ensure_directory_exists(media_path)

                attachment_body = None
                if attachment.payload is not None:
                    if isinstance(attachment.payload, Payload):
                        attachment_body = attachment.payload.body
                    else:
                        attachment_body = attachment.payload["body"]

                if attachment_body is not None:
                    if isinstance(attachment.payload, dict) and attachment.payload.get("content_type") == 'json':
                        write_json_file(f"{media_path}/{attachment.shortname}.json", attachment_body)
                        attachment.payload["body"] = f"{attachment.shortname}.json"
                    elif isinstance(attachment.payload, dict) and attachment.payload.get("content_type") == 'comment':
                        write_json_file(f"{media_path}/{attachment.shortname}.json", attachment_body)
                        attachment.payload["body"] = f"{attachment.shortname}.json"
                    else:
                        if attachment.media:
                            write_binary_file(f"{media_path}/{attachment_body}", attachment.media)

                    _attachment = attachment.model_dump()

                    del _attachment["media"]
                    del _attachment["resource_type"]
                    write_json_file(f"{media_path}/meta.{attachment.shortname}.json", _attachment)
            else:
                with open(f"{dir_meta_path}/meta.{entry.resource_type}.json", "r") as f:
                    entry_data = json.load(f)
                    if __attachment is not None:
                        if "payload" in entry_data:
                            entry_data["payload"] = __attachment.payload

    return space_folder

def main():
    space_folder = os.path.relpath(str(settings.spaces_folder))

    with Session(engine) as session:
        print("Processing spaces...")
        process_spaces(session, space_folder)
        print("Processing entries...")
        process_entries(session, space_folder)
        print("Processing users...")
        process_users(session, space_folder)
        print("Processing roles...")
        process_roles(session, space_folder)
        print("Processing permissions...")
        process_permissions(session, space_folder)
        print("Processing attachments...")
        process_attachments(session, space_folder)
        print("Processing histories...")
        process_histories(session, space_folder)


if __name__ == "__main__":
    main()
