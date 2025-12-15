from datetime import datetime
from data_adapters.sql.adapter import SQLAdapter
from utils.settings import settings
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4
from utils.query_policies_helper import generate_query_policies
from models.enums import ResourceType, ContentType
from data_adapters.sql.create_tables import Entries, Users, Attachments, Roles, Permissions, Spaces, generate_tables, \
    Histories

async def save_health_check_entry():
    health_check_entry = {
        "space_name": "management",
        "resource_type": "content",
        "shortname": "migration_json_to_db",
        "subpath": "/health_check",
        "is_active": True,
        "payload": {
            "schema_shortname": "health_check",
            "content_type": ContentType.json,
            "body": {"folders_report": folders_report}
        }
    }

    try:
        async with SQLAdapter().get_session() as session:
            session.add(Spaces.model_validate(health_check_entry))
            await session.commit()
    except Exception as e:
        print(e)

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

async def bulk_insert_in_batches(model, records, batch_size=2000):
    async with SQLAdapter().get_session() as session:
        try:
            for i in range(0, len(records), batch_size):
                batch = []
                try:
                    batch = records[i:i + batch_size]
                    for record in batch:
                        if isinstance(record.get('created_at'), str):
                            record['created_at'] = datetime.fromisoformat(record['created_at'])
                        if isinstance(record.get('updated_at'), str):
                            record['updated_at'] = datetime.fromisoformat(record['updated_at'])
                    await session.run_sync(lambda ses: ses.bulk_insert_mappings(model, batch))
                    await session.commit()
                except Exception as e:
                    print("[!bulk_insert_in_batches]", e)
                    await session.rollback()
                    for _batch in batch:
                        try:
                            session.add(model.model_validate(_batch))
                            await session.commit()
                        except Exception as e:
                            await session.rollback()
                            print(
                                "[!bulk_insert_in_batches_single]",
                                e,
                                f"* {_batch['subpath']}/{_batch['shortname']}"
                            )
                            save_report('/', save_issue(_batch['resource_type'], _batch, e))
        except Exception as e:
            print("[!fatal_bulk_insert_in_batches]", e)


async def _process_directory(root, dirs, space_name, subpath):
    # asyncio.run()
    await process_directory(root, dirs, space_name, subpath)

async def process_directory(root, dirs, space_name, subpath):
    histories = []
    attachments = []
    entries = []
    users = []
    roles = []
    permissions = []

    for dir in dirs:
        for file in os.listdir(os.path.join(root, dir)):
            if not file.startswith('meta'):
                if file == 'history.jsonl':
                    lines = open(os.path.join(root, dir, file), 'r').readlines()
                    for line in lines:
                        history = None
                        try:
                            history = json.loads(line.replace('\n', ''))
                            history['shortname'] = dir
                            history['space_name'] = space_name
                            history['subpath'] = subpath_checker(subpath)
                            history['timestamp'] = datetime.strptime(history['timestamp'], '%Y-%m-%dT%H:%M:%S.%f')

                            histories.append(history)

                        except Exception as e:
                            print(f"Error processing Histories {space_name}/{subpath}/{dir}/{history} ... ")
                            print(e)

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
                                if not _attachment.get('payload', {}).get('content_type', False):
                                    _attachment['media'] = None
                                else:
                                    try:
                                        _attachment['media'] = open(os.path.join(root, dir, _body), 'rb').read()
                                    except Exception as e:
                                        print(f"Error reading media file {os.path.join(root, dir, _body)}: {e}")
                                        _attachment['media'] = None
                            if _attachment.get('payload', None) is None:
                                _attachment['payload'] = {}
                        try:
                            _attachment['resource_type'] = dir.replace('attachments.', '')
                            attachments.append(_attachment)
                        except Exception as e:
                            print(f"Error processing Attachments {space_name}/{subpath}/{dir}/{file} ... ")
                            print("!!", e)
                            save_report('/', save_issue(_attachment['resource_type'], _attachment, e))
                elif file.startswith('meta.') and file.endswith('.json'):
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
                                    save_report('/', save_issue(ResourceType.json, entry, e))
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
                            users.append(entry)
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
                            roles.append(entry)
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
                            permissions.append(entry)
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
                                entries.append(entry)
                                continue
                            entry["subpath"] = subpath_checker(entry["subpath"])

                            entries.append(entry)
                    except Exception as e:
                        save_report('/', save_issue(entry['resource_type'], entry, e))

    await bulk_insert_in_batches(Users, users)
    await bulk_insert_in_batches(Roles, roles)
    await bulk_insert_in_batches(Permissions, permissions)
    await bulk_insert_in_batches(Entries, entries)
    await bulk_insert_in_batches(Attachments, attachments)
    await bulk_insert_in_batches(Histories, histories)


async def main():
    generate_tables()

    target_path = settings.spaces_folder

    if len(sys.argv) == 2 and sys.argv[1] != 'json_to_db':
        target_path = target_path.joinpath(sys.argv[1])

    if not target_path.exists():
        print(f"Space '{str(target_path).replace('/', '')}' does not exist")
        sys.exit(1)

    all_dirs = []
    user_dirs = []
    for root, dirs, _ in os.walk(str(target_path)):
        if root.startswith(os.path.join(str(target_path), 'management/users')):
            user_dirs.append((root, sorted(dirs, key=lambda d: d != 'dmart')))
        else:
            all_dirs.append((root, dirs))

    user_dirs.sort(key=lambda x: (
        not x[0].startswith(os.path.join(str(target_path), 'management/users/.dm')),
        x[0]
    ))


    for root, dirs in user_dirs:
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

        subpath = subpath.replace('.dm', '')
        if subpath != '/' and subpath.endswith('/'):
            subpath = subpath[:-1]

        if subpath == '':
            subpath = '/'

        await process_directory(root, dirs, space_name, subpath)

    # with ThreadPoolExecutor() as executor:
        # futures = []
    for root, dirs in all_dirs:
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

        print(".", end='')
        if subpath == '' or subpath == '/':
            subpath = '/'
            p = os.path.join(root, '.dm', 'meta.space.json')
            entry = {}
            if Path(p).is_file():
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

                    async with SQLAdapter().get_session() as session:
                        session.add(Spaces.model_validate(entry))
                        await session.commit()
                except Exception as e:
                    save_report('/', save_issue(ResourceType.space, entry, e))
            continue

        subpath = subpath.replace('.dm', '')
        if subpath != '/' and subpath.endswith('/'):
            subpath = subpath[:-1]

        if subpath == '':
            subpath = '/'

        await _process_directory(root, dirs, space_name, subpath)
        # futures.append(executor.submit(_process_directory, root, dirs, space_name, subpath))
        # as_completed(futures)

    # for future in as_completed(futures):
    #     future.result()

    if settings.active_data_db == 'file':
        print("[Warning] you are using active_data_db='file', please don't forget to set it to active_data_db='sql' in your config.env")

    await save_health_check_entry()

    # await SQLAdapter().ensure_authz_materialized_views_fresh()


if __name__ == "__main__":
    asyncio.run(main())
