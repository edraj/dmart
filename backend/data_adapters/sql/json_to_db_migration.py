import asyncio
import hashlib
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from uuid import uuid4
from sqlmodel import Session, create_engine, text

from utils.query_policies_helper import generate_query_policies
from .health_check_sql import save_health_check_entry
from models.enums import ResourceType
from data_adapters.sql.create_tables import Entries, Users, generate_tables, Attachments, Roles, Permissions, Spaces
from utils.settings import settings

logging.basicConfig()
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
logging.disable(logging.ERROR)

def subpath_checker(subpath: str):
    if subpath.endswith("/"):
        subpath = subpath[:-1]
    if not subpath.startswith("/"):
        subpath = '/' + subpath
    return subpath

folders_report: Any = {}
invalid_entries: Any = []

def save_issue(resource_type, entry, e):
    entry_uuid = None
    entry_shortname = None
    if isinstance(entry, dict):
        entry_uuid = str(entry["uuid"])
        entry_shortname = entry["shortname"]
    else:
        entry_uuid = str(entry.uuid)
        entry_shortname = entry.shortname

    return {
        "issues": ["entry"],
        "uuid": entry_uuid,
        "shortname": entry_shortname,
        "resource_type": resource_type,
        "exception": str(e),
    }

def save_report(isubpath: str, issue):
    if folders_report.get(isubpath, False):
        if folders_report[isubpath].get("invalid_entries", False):
            folders_report[isubpath]["invalid_entries"] = [
                *folders_report[isubpath]["invalid_entries"],
                issue
            ]
        else:
            folders_report[isubpath]["invalid_entries"] = [
                issue
            ]
    else:
        folders_report[isubpath] = {
            "invalid_entries": [
                issue
            ]
        }

def process_directory(root, dirs, space_name, subpath):
    postgresql_url = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}/{settings.database_name}"
    engine = create_engine(postgresql_url, echo=False)

    with Session(engine) as session:
        for dir in dirs:
            print(f"Processing {subpath}... ")
            for file in os.listdir(os.path.join(root, dir)):
                if not file.startswith('meta'):
                    continue

                p = os.path.join(root, dir, file)
                if Path(p).is_file():
                    if 'attachments' in p:
                        if file.startswith("meta") and file.endswith(".json"):
                            _attachment = json.load(open(os.path.join(root, dir, file)))
                            _attachment['space_name'] = space_name
                            _attachment['uuid'] = _attachment.get('uuid', uuid4())
                            _attachment['subpath'] = subpath.replace('//', '/')
                            _attachment['subpath'] = subpath_checker(_attachment['subpath'])
                            _attachment['acl'] = _attachment.get('acl', [])
                            _attachment['relationships'] = _attachment.get('relationships', [])
                            _attachment['tags'] = _attachment.get('tags', [])
                            _attachment['owner_shortname'] = _attachment.get('owner_shortname', '')
                            _attachment['media'] = None
                            if file.replace("attachments.", "") == 'comment':
                                _attachment['payload'] = {
                                    'body': _attachment.get('body', ''),
                                    'state': _attachment.get('state', '')
                                }
                            elif file.replace("attachments.", "") == 'ticket':
                                _attachment['payload'] = {
                                    'state': _attachment.get('state', ''),
                                    'is_open': _attachment.get('is_open', True),
                                    'reporter': _attachment.get('reporter', ''),
                                    'workflow_shortname': _attachment.get('workflow_shortname', ''),
                                    'collaborators': _attachment.get('collaborators', {})
                                }
                            else:
                                _body: str = _attachment.get('payload', {}).get('body', None)
                                if _body and _body.endswith('.json'):
                                    _attachment_body = json.load(open(os.path.join(root, dir, _body)))
                                    _attachment['payload']['body'] = _attachment_body
                                elif _body:
                                    if _attachment.get('payload', {}).get('content_type', False):
                                        _attachment['media'] = _body
                                    else:
                                        _attachment['media'] = open(os.path.join(root, dir, _body), 'rb').read()
                                if _attachment.get('payload', None) is None:
                                    _attachment['payload'] = {}
                            try:
                                print(f"{dir=}")
                                _attachment['resource_type'] = dir.replace('attachments.', '')
                                session.add(Attachments.model_validate(_attachment))
                            except Exception as e:
                                print(f"Error processing Attachments {subpath}/{file} ... ")
                                print(e)
                                save_report('/', save_issue(_attachment['resource_type'], _attachment, e))
                    elif file.endswith('.json'):
                        entry = json.load(open(p))
                        entry['space_name'] = space_name
                        body = None
                        _payload = entry.get('payload', {})
                        if _payload:
                            if payload := entry.get('payload', {}).get('body', None):
                                if entry.get('payload', {}).get('content_type', None) == 'json':
                                    try:
                                        body = json.load(open(
                                            os.path.join(root, dir, '../..', payload)
                                        ))
                                    except Exception as e:
                                        print(f"Error processing payload {subpath}/{entry} ... ")
                                        save_report('/', save_issue(ResourceType.json, entry, e))
                                        print(e)
                                else:
                                    body = payload

                                sha1 = hashlib.sha1()
                                sha1.update(json.dumps(body).encode())
                                checksum = sha1.hexdigest()
                                entry['payload']['checksum'] = checksum
                                entry['payload']['body'] = body
                        else:
                            entry['payload'] = None
                        entry['subpath'] = subpath_checker(subpath)
                        entry['acl'] = entry.get('acl', [])
                        entry['relationships'] = entry.get('relationships', [])
                        try:
                            if file.startswith("meta.user"):
                                entry['query_policies'] = generate_query_policies(
                                    space_name=space_name,
                                    subpath=subpath,
                                    resource_type=ResourceType.user,
                                    is_active=True,
                                    owner_shortname=entry.get('owner_shortname', 'dmart'),
                                    owner_group_shortname=entry.get('owner_group_shortname', None),
                                )
                                entry['resource_type'] = 'user'
                                entry['firebase_token'] = entry.get('firebase_token', '')
                                entry['type'] = entry.get('type', 'web')
                                entry['language'] = entry.get('language', '')
                                entry['google_id'] = entry.get('google_id', '')
                                entry['facebook_id'] = entry.get('facebook_id', '')
                                entry['social_avatar_url'] = entry.get('social_avatar_url', '')
                                entry['displayname'] = entry.get('displayname', {})
                                entry['description'] = entry.get('description', {})
                                session.add(Users.model_validate(entry))
                            elif file.startswith("meta.role"):
                                entry['query_policies'] = generate_query_policies(
                                    space_name=space_name,
                                    subpath=subpath,
                                    resource_type=ResourceType.role,
                                    is_active=True,
                                    owner_shortname=entry.get('owner_shortname', 'dmart'),
                                    owner_group_shortname=entry.get('owner_group_shortname', None),
                                )
                                entry['resource_type'] = 'role'
                                entry['permissions'] = entry.get('permissions', [])
                                session.add(Roles.model_validate(entry))
                            elif file.startswith("meta.permission"):
                                entry['query_policies'] = generate_query_policies(
                                    space_name=space_name,
                                    subpath=subpath,
                                    resource_type=ResourceType.permission,
                                    is_active=True,
                                    owner_shortname=entry.get('owner_shortname', 'dmart'),
                                    owner_group_shortname=entry.get('owner_group_shortname', None),
                                )
                                entry['resource_type'] = 'permission'
                                entry['subpaths'] = entry.get('subpaths', {})
                                entry['resource_types'] = entry.get('resource_types', [])
                                entry['actions'] = entry.get('actions', [])
                                entry['conditions'] = entry.get('conditions', [])
                                entry['restricted_fields'] = entry.get('restricted_fields', [])
                                entry['allowed_fields_values'] = entry.get('allowed_fields_values', {})
                                session.add(Permissions.model_validate(entry))
                            else:
                                entry['resource_type'] = file.replace('.json', '').replace('meta.', '')

                                entry['query_policies'] = generate_query_policies(
                                    space_name=space_name,
                                    subpath=subpath,
                                    resource_type=entry['resource_type'],
                                    is_active=True,
                                    owner_shortname=entry.get('owner_shortname', 'dmart'),
                                    owner_group_shortname=entry.get('owner_group_shortname', None),
                                )

                                if entry['resource_type'] == 'folder':
                                    new_subpath = entry['subpath'].split('/')
                                    entry['subpath'] = '/'.join(new_subpath[:-1]) + '/'
                                elif entry['resource_type'] == 'ticket':
                                    entry["state"] = entry.get("state", "")
                                    entry["is_open"] = entry.get("is_open", True)
                                    entry["reporter"] = entry.get("reporter", None)
                                    entry["workflow_shortname"] = entry.get("workflow_shortname", "")
                                    entry["collaborators"] = entry.get("collaborators", None)
                                    entry["resolution_reason"] = entry.get("resolution_reason", None)
                                    entry['displayname'] = entry.get('displayname', {})
                                    entry['description'] = entry.get('description', {})
                                    entry["subpath"] = subpath_checker(entry["subpath"])
                                    session.add(Entries.model_validate(entry))
                                    continue
                                entry["subpath"] = subpath_checker(entry["subpath"])

                                session.add(Entries.model_validate(entry))
                        except Exception as e:
                            print(f"Error processing Entries {subpath}/{entry} ... ")
                            save_report('/', save_issue(entry['resource_type'], entry, e))
                            print(e)
        try:
            session.commit()
        except Exception as e:
            print(e)
            session.rollback()

def main():
    postgresql_url = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}"
    engine = create_engine(f"{postgresql_url}/postgres", echo=False, isolation_level="AUTOCOMMIT")

    try:
        with Session(engine) as session:
            sql = f"CREATE DATABASE {settings.database_name}"
            session.execute(text(sql))
    except Exception as e:
        print("Warning : While creating DB: ", str(e))
    finally:
        engine = create_engine(f"{postgresql_url}/{settings.database_name}", echo=False)

    try:
        generate_tables()
    except Exception as e:
        print("Warning: While generating tables: ", str(e))

    with Session(engine) as session:
        target_path = settings.spaces_folder

        if len(sys.argv) == 2 and sys.argv[1] != 'json_to_db':
            target_path = target_path.joinpath(sys.argv[1])

        if not target_path.exists():
            print(f"Space '{str(target_path).replace('/', '')}' does not exist")
            sys.exit(1)

        with ThreadPoolExecutor() as executor:
            futures = []
            for root, dirs, _ in os.walk(str(target_path)):
                tmp = root.replace(str(settings.spaces_folder), '')
                if tmp == '':
                    continue
                if tmp[0] == '/':
                    tmp = tmp[1:]
                space_name = tmp.split('/')[0]
                subpath = '/'.join(tmp.split('/')[1:])
                if space_name == '..':
                    continue

                if space_name.startswith('.git'):
                    continue

                print(f"Processing {space_name}/{subpath} ... ")
                if subpath == '' or subpath == '/':
                    subpath = '/'
                    p = os.path.join(root, '.dm', 'meta.space.json')
                    entry = {}
                    if Path(p).is_file():
                        print(f"Processing {space_name}/{subpath} ... ")
                        try:
                            entry = json.load(open(p))
                            entry['space_name'] = space_name
                            entry['shortname'] = space_name
                            entry['query_policies'] = generate_query_policies(
                                space_name=space_name,
                                subpath=subpath,
                                resource_type=ResourceType.space,
                                is_active=True,
                                owner_shortname=entry.get('owner_shortname', 'dmart'),
                                owner_group_shortname=entry.get('owner_group_shortname', None),
                            )

                            _payload = entry.get('payload', {})
                            if _payload:
                                if payload := _payload.get('body', None):
                                    if entry.get('payload', {}).get('content_type', None) == 'json':
                                        body = json.load(open(
                                            os.path.join(root, '.dm', '../..', str(payload))
                                        ))
                                    else:
                                        body = payload
                                    sha1 = hashlib.sha1()
                                    sha1.update(json.dumps(body).encode())
                                    checksum = sha1.hexdigest()
                                    entry['payload']['checksum'] = checksum
                                    entry['payload']['body'] = body
                            else:
                                entry['payload'] = None
                            entry['subpath'] = '/'
                            entry['resource_type'] = 'space'
                            entry['tags'] = entry.get('tags', [])
                            entry['acl'] = entry.get('acl', [])
                            entry['hide_folders'] = entry.get('hide_folders', [])
                            entry['relationships'] = entry.get('relationships', [])
                            entry['hide_space'] = entry.get('hide_space', False)

                            session.add(Spaces.model_validate(entry))
                            session.commit()
                        except Exception as e:
                            print(f"Error processing Spaces {space_name}/{subpath}/{entry} ...")
                            save_report('/', save_issue(ResourceType.space, entry, e))
                            print(e)
                    continue


                subpath = subpath.replace('.dm', '')
                if subpath != '/' and subpath.endswith('/'):
                    subpath = subpath[:-1]

                if subpath == '':
                    subpath = '/'

                futures.append(executor.submit(process_directory, root, dirs, space_name, subpath))

            for future in as_completed(futures):
                future.result()

    if settings.active_data_db == 'file':
        print("[Warning] you are using active_data_db='file', please don't forget to set it to active_data_db='sql' in your config.env")

    asyncio.run(
        save_health_check_entry(
            {"folders_report": folders_report}, "migration_json_to_db"
        )
    )

if __name__ == "__main__":
    main()