#!/usr/bin/env -S BACKEND_ENV=config.env python3

import os
import json
from datetime import datetime
from sqlmodel import Session, create_engine, select
from utils.database.create_tables import (
    Entries,
    Users,
    Attachments,
    Roles,
    Permissions,
    Histories,
    Spaces,
)
from utils.settings import settings
from models import core

postgresql_url = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}/{settings.database_name}"
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
        clean = clean_json(data)
        json.dump(clean, f, indent=2, default=str)

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
        if attachment.payload.get("body", None):
            if attachment.payload["content_type"] == 'json':
                write_json_file(f"{media_path}/{attachment.shortname}.json", attachment.payload.get("body", {}))
                attachment.payload["body"] = f"{attachment.shortname}.json"
            else:
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
            if payload := _entry.get("payload", {}):
                if payload.get("body", None):
                    body = payload["body"]
                _entry["payload"]["body"] = f"{entry.shortname}.json"
            del _entry["space_name"]
            del _entry["subpath"]
            del _entry["resource_type"]

            write_json_file(f"{dir_meta_path}/meta.folder.json", _entry)
            if body:
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
                if _entry["payload"]["body"]:
                    write_json_file(
                        f"{dir_path}/{entry.shortname}.json",
                        _entry["payload"]["body"]
                    )
                    _entry["payload"]["body"] = f"{entry.shortname}.json"
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