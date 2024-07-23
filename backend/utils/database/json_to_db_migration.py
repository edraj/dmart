#!/usr/bin/env -S BACKEND_ENV=config.env python3
# type: ignore
import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, create_engine, text

from create_tables import Entries, Users, generate_tables, Attachments, \
    Roles, Permissions, Histories, Spaces, Tickets
from utils.settings import settings

logging.basicConfig()
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
logging.disable(logging.ERROR)

# postgresql_url = "postgresql://postgres:tenno1515@localhost:5432/postgres"
postgresql_url = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}"
engine = create_engine(f"{postgresql_url}/postgres")


try:
    s = Session(engine)
    s.connection().connection.set_isolation_level(0)  # type: ignore
    sql = f"CREATE DATABASE {settings.database_name}"  # type: ignore
    s.exec(text(sql))  # type: ignore
    engine = create_engine(f"{postgresql_url}/{settings.database_name}", echo=True)
    generate_tables()
except Exception as e:
    print(e)

with Session(engine) as session:
    for root, dirs, _ in os.walk(str(settings.spaces_folder)):
        tmp = root.replace(str(settings.spaces_folder), '')
        if tmp == '':
            continue
        if tmp[0] == '/':
            tmp = tmp[1:]
        space_name = tmp.split('/')[0]
        subpath = '/'.join(tmp.split('/')[1:])
        if space_name == '..':
            continue

        print(f"Processing {space_name}/{subpath} ... ")
        if subpath == '' or subpath == '/':
            subpath = '/'
            p = os.path.join(root, '.dm', 'meta.space.json')
            entry = {}
            if Path(p).is_file():
                try:
                    entry = json.load(open(p))
                    entry['space_name'] = space_name
                    if payload := entry.get('payload', {}).get('body', None):
                        if entry.get('payload', {}).get('content_type', None) == 'json':
                            body = json.load(open(
                                os.path.join(root, dir, '../..', payload) # type: ignore
                            ))
                        else:
                            body = payload
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
                except Exception as e:
                    print(f"Error processing {space_name}/{subpath}/{dir}/{entry} ... ")
                    print(e)
            continue

        # if subpath.endswith('.dm'):
        subpath = subpath.replace('.dm', '')
        if subpath != '/' and subpath.endswith('/'):
            subpath = subpath[:-1]

        if subpath == '':
            subpath = '/'

        for dir in dirs:
            for file in os.listdir(os.path.join(root, dir)):
                p = os.path.join(root, dir, file)
                if Path(p).is_file():
                    if 'attachments' in p:
                        if file.startswith("meta") and file.endswith(".json"):
                            _attachment = json.load(open(os.path.join(root, dir, file)))
                            _attachment['space_name'] = space_name
                            _attachment['uuid'] = _attachment.get('uuid', uuid4())
                            _attachment['subpath'] = f"{subpath}/{dir}".replace('//', '/')
                            _attachment['acl'] = _attachment.get('acl', [])
                            _attachment['relationships'] = _attachment.get('relationships', [])
                            _attachment['tags'] = _attachment.get('relationships', [])
                            _attachment['owner_shortname'] = _attachment.get('owner_shortname', '')
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
                                if _attachment.get('payload', None) is None:
                                    _attachment['payload'] = {}
                            try:
                                print(f"{dir=}")
                                _attachment['resource_type'] = dir.replace('attachments.', '') #file.replace('.json', '').replace('meta.', '')
                                session.add(Attachments.model_validate(_attachment))
                            except Exception as e:
                                print(f"Error processing {space_name}/{subpath}/{dir}/{file} ... ")
                                print(e)
                    elif file.endswith('.json'):
                        entry = json.load(open(p))
                        entry['space_name'] = space_name
                        body = None
                        if payload := entry.get('payload', {}).get('body', None):
                            if entry.get('payload', {}).get('content_type', None) == 'json':
                                try:
                                    body = json.load(open(
                                        os.path.join(root, dir, '../..', payload)
                                    ))
                                except Exception as e:
                                    print(f"Error processing {space_name}/{subpath}/{dir}/{entry} ... ")
                                    print(e)
                            else:
                                body = payload
                            entry['payload']['body'] = body
                        else:
                            entry['payload'] = None
                        entry['subpath'] = subpath
                        entry['acl'] = entry.get('acl', [])
                        entry['relationships'] = entry.get('relationships', [])
                        try:
                            match subpath:
                                case 'users':
                                    entry['resource_type'] = 'user'
                                    entry['firebase_token'] = entry.get('firebase_token', '')
                                    entry['language'] = entry.get('language', '')
                                    entry['google_id'] = entry.get('google_id', '')
                                    entry['facebook_id'] = entry.get('facebook_id', '')
                                    entry['social_avatar_url'] = entry.get('social_avatar_url', '')
                                    session.add(Users.model_validate(entry))
                                case 'roles':
                                    entry['resource_type'] = 'role'
                                    entry['permissions'] = entry.get('permissions', [])
                                    session.add(Roles.model_validate(entry))
                                case 'permissions':
                                    entry['resource_type'] = 'permission'
                                    entry['subpaths'] = entry.get('subpaths', {})
                                    entry['resource_types'] = entry.get('resource_types', [])
                                    entry['actions'] = entry.get('actions', [])
                                    entry['conditions'] = entry.get('conditions', [])
                                    entry['restricted_fields'] = entry.get('restricted_fields', [])
                                    entry['allowed_fields_values'] = entry.get('allowed_fields_values', {})
                                    session.add(Permissions.model_validate(entry))
                                case _:
                                    entry['resource_type'] = file.replace('.json', '').replace('meta.', '')
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
                                        session.add(Tickets.model_validate(entry))
                                        continue

                                    session.add(Entries.model_validate(entry))
                        except Exception as e:
                            print(f"Error processing {space_name}/{subpath}/{dir}/{entry} ... ")
                            print(e)
                    elif file == 'history.jsonl':
                        lines = open(p, 'r').readlines()
                        for line in lines:
                            history = json.loads(line)
                            history['shortname'] = dir
                            history['space_name'] = space_name
                            history['subpath'] = subpath
                            try:
                                session.add(Histories.model_validate(history))
                            except Exception as e:
                                print(f"Error processing {space_name}/{subpath}/{dir}/{history} ... ")
                                print(e)

            try:
                session.commit()
            except Exception as e:
                print(e)
                session.reset()
