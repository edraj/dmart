import os
import json
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

def write_json_file(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4, default=str)

def write_binary_file(path, data):
    with open(path, "wb") as f:
        f.write(data)

def process_attachments(session, space_folder):
    attachments = session.exec(select(Attachments)).all()
    for attachment in attachments:
        subpath = subpath_checker(attachment.subpath)

        parts = subpath.split('/')  # Split the string into a list
        parts.insert(-1, '.dm')  # Insert '.dm' before the last element
        new_path = '/'.join(parts)  # Join the list back into a string

        dir_path = f"{space_folder}/{attachment.space_name}{new_path}"
        ensure_directory_exists(dir_path)

        media_path = os.path.join(dir_path, f"attachments.{attachment.resource_type}")
        ensure_directory_exists(media_path)

        write_binary_file(f"{media_path}/{attachment.payload['body']}", attachment.media)
        _attachment = attachment.model_dump()

        del _attachment["media"]
        write_json_file(os.path.join(media_path, f"meta.{attachment.shortname}.json"), _attachment)


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
            del _entry["space_name"]
            del _entry["subpath"]
            file_path = os.path.join(dir_meta_path, "meta.folder.json")
            write_json_file(file_path, _entry)
            continue

        dir_meta_path = f"{dir_path}/.dm/{entry.shortname}".replace("//", "/")
        ensure_directory_exists(dir_meta_path)

        _entry = entry.model_dump()
        del _entry["space_name"]
        del _entry["subpath"]
        if _entry.get("payload", None) and _entry["payload"].get("body" , None):
            write_json_file(
                f"{dir_path}/{entry.shortname}.json",
                _entry["payload"]["body"]
            )
            _entry["payload"]["body"] = f"{entry.shortname}.json"

        file_path = os.path.join(dir_meta_path, f"meta.{entry.resource_type}.json")
        write_json_file(file_path, _entry)



def process_users(session, space_folder):
    users = session.exec(select(Users)).all()
    dir_path = f"{space_folder}/management/users" # Ensure absolute path
    for user in users:
        dir_meta_path = f"{dir_path}/.dm/{user.shortname}"
        ensure_directory_exists(dir_meta_path)

        _user = user.model_dump()
        del _user["space_name"]
        if _user.get("payload", None) and _user["payload"].get("body" , None):
            write_json_file(
                f"{dir_path}/{user.shortname}.json",
                _user["payload"]["body"]
            )
            _user["payload"]["body"] = f"{user.shortname}.json"

        file_path = os.path.join(dir_meta_path, "meta.user.json")
        write_json_file(file_path, _user)

def process_roles(session, space_folder):
    roles = session.exec(select(Roles)).all()
    dir_path = f"{space_folder}/management/roles/.dm"  # Ensure absolute path
    for role in roles:
        dir_path = f"{dir_path}/{role.shortname}"
        ensure_directory_exists(dir_path)

        _role = role.model_dump()
        del _role["space_name"]
        del _role["subpath"]

        file_path = os.path.join(dir_path, "meta.role.json")
        write_json_file(file_path, _role)

def process_permissions(session, space_folder):
    permissions = session.exec(select(Permissions)).all()
    dir_path = f"{space_folder}/management/permissions/.dm" # Ensure absolute path
    for permission in permissions:
        dir_path = f"{dir_path}/{permission.shortname}"
        ensure_directory_exists(dir_path)

        _permission = permission.model_dump()
        del _permission["space_name"]
        del _permission["subpath"]
        del _permission["shortname"]

        file_path = os.path.join(dir_path, "meta.permission.json")
        write_json_file(file_path, _permission)

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
        with open(f"{file_path}/history.jsonl", "a+") as f:
            f.write(str(_history) + "\n")

def process_spaces(session, space_folder):
    spaces = session.exec(select(Spaces)).all()
    for space in spaces:
        dir_path = f"{space_folder}/{space.space_name}/.dm/" # Ensure absolute path
        ensure_directory_exists(dir_path)

        file_path = os.path.join(dir_path, "meta.space.json")

        _space = space.model_dump()
        del _space["space_name"]
        del _space["shortname"]

        write_json_file(file_path, _space)

def main():
    space_folder = os.path.relpath(str(settings.spaces_folder))

    with Session(engine) as session:
        print("Processing attachments...")
        process_attachments(session, space_folder)
        print("Processing entries...")
        process_entries(session, space_folder)
        print("Processing users...")
        process_users(session, space_folder)
        print("Processing roles...")
        process_roles(session, space_folder)
        print("Processing permissions...")
        process_permissions(session, space_folder)
        print("Processing histories...")
        process_histories(session, space_folder)
        print("Processing spaces...")
        process_spaces(session, space_folder)

if __name__ == "__main__":
    main()
