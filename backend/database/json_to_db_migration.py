#!/usr/bin/env -S BACKEND_ENV=config.env python3
import json
import os
from pathlib import Path
import sqlalchemy
from sqlalchemy.log import InstanceLogger
from sqlmodel import Session, create_engine, text
from uuid import uuid4
from database.create_tables import Entries, Users, generate_tables, Attachments, Roles, Permissions, Histories
from utils.settings import settings
import logging

logging.basicConfig()
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
logging.disable(logging.ERROR)

# postgresql_url = "postgresql://postgres:tenno1515@localhost:5432/postgres"
postgresql_url = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}"
engine = create_engine(f"{postgresql_url}/postgres")

spaces = []
print(settings.is_central_db)
if settings.is_central_db:
    try:
        s = Session(engine)
        s.connection().connection.set_isolation_level(0)
        sql = "CREATE DATABASE dmart"
        s.exec(text(sql))
        engine = create_engine(f"{postgresql_url}/dmart", echo=True)
        s = Session(engine)
        generate_tables('dmart')
        # for table in ['permissions', 'entries', 'attachments', 'roles', 'histories', 'users']:
        #     sql = f"ALTER TABLE {table} ADD COLUMN space_name VARCHAR(255);"
        #     s.exec(text(sql))

        s.close()


    except Exception as e:
        print(e)

for root, dirs, files in os.walk("../../spacess"):
    tmp = root.replace("../../spacess/", '')
    space_name = tmp.split('/')[0]
    subpath = '/'.join(tmp.split('/')[1:])
    if space_name == '..':
        continue
    if not settings.is_central_db:
        try:
            if not space_name in spaces:
                print(f"Creating database {space_name}")
                spaces.append(space_name)
                s = Session(engine)
                s.connection().connection.set_isolation_level(0)
                s.exec(text(f"CREATE DATABASE {space_name}"))
                s.close()
        except sqlalchemy.exc.ProgrammingError as e:
            print(e)

    if not settings.is_central_db:
        engine = create_engine(f"{postgresql_url}/{space_name}", echo=False)


    with Session(engine) as session:
        if not settings.is_central_db:
            session.connection().connection.set_isolation_level(0)
            try:
                generate_tables(space_name)
            except sqlalchemy.exc.ProgrammingError as e:
                print(e)

        if subpath.endswith('.dm'):
            subpath = subpath.replace('.dm', '')
            if subpath.endswith('/'):
                subpath = subpath[:-1]
            for dir in dirs:
                for file in os.listdir(os.path.join(root, dir)):
                    p = os.path.join(root, dir, file)
                    if Path(p).is_file():
                        if file.endswith('.json'):
                            entry = json.load(open(p))
                            if settings.is_central_db:
                                entry['space_name'] = space_name
                            if payload := entry.get('payload', {}).get('body', None):
                                if entry.get('payload', {}).get('content_type', None) == 'json':
                                    body = json.load(open(
                                        os.path.join(root, dir, '../..', payload)
                                    ))
                                else:
                                    body = payload
                                entry['payload']['body'] = body
                            else:
                                entry['payload'] = None
                            entry['subpath'] = subpath
                            entry['resource_type'] = file.replace('.json', '').replace('meta.', '')
                            entry['acl'] = entry.get('acl', [])
                            entry['relationships'] = entry.get('relationships', [])
                            try:
                                if space_name == 'management':
                                    match subpath:
                                        case 'users':
                                            entry['firebase_token'] = entry.get('firebase_token', '')
                                            entry['language'] = entry.get('language', '')
                                            entry['google_id'] = entry.get('google_id', '')
                                            entry['facebook_id'] = entry.get('facebook_id', '')
                                            entry['social_avatar_url'] = entry.get('social_avatar_url', '')
                                            session.add(Users.model_validate(entry))
                                        case 'roles':
                                            entry['permissions'] = entry.get('permissions', [])
                                            session.add(Roles.model_validate(entry))
                                        case 'permissions':
                                            entry['subpaths'] = entry.get('subpaths', {})
                                            entry['resource_types'] = entry.get('resource_types', [])
                                            entry['actions'] = entry.get('actions', [])
                                            entry['conditions'] = entry.get('conditions', [])
                                            entry['restricted_fields'] = entry.get('restricted_fields', [])
                                            entry['allowed_fields_values'] = entry.get('allowed_fields_values', {})
                                            session.add(Permissions.model_validate(entry))
                                        case _:
                                            session.add(Entries.model_validate(entry))
                            except Exception as e:
                                print(f"Error processing {space_name}/{subpath}/{dir}/{entry} ... ")
                                print(e)
                        if file == 'history.jsonl':
                            lines = open(p, 'r').readlines()
                            for line in lines:
                                history = json.loads(line)
                                if settings.is_central_db:
                                    history['space_name'] = space_name
                                history['subpath'] = subpath
                                try:
                                    session.add(Histories.model_validate(history))
                                except Exception as e:
                                    print(f"Error processing {space_name}/{subpath}/{dir}/{history} ... ")
                                    print(e)
                        if file.startswith('attachments'):
                            for attachment in os.listdir(os.path.join(root, dir, file)):
                                if attachment.startswith("meta") and attachment.endswith(".json"):
                                    _attachment = json.load(open(os.path.join(root, dir, file, attachment)))
                                    if settings.is_central_db:
                                        _attachment['space_name'] = space_name
                                    _attachment['uuid'] = _attachment.get('uuid', uuid4())
                                    _attachment['subpath'] = f"{subpath}/{dir}"
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
                                    try:
                                        session.add(Attachments.model_validate(_attachment))
                                    except Exception as e:
                                        print(f"Error processing {space_name}/{subpath}/{dir}/{attachment} ... ")
                                        print(e)
                try:
                    session.commit()
                except Exception as e:
                    print(e)
                    session.reset()
