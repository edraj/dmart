import json
import os
from pathlib import Path

import sqlalchemy
from sqlmodel import Session, SQLModel, create_engine, text
import psycopg2

from database.create_tables import Entries, Users, generate_tables

target = "../../spaces_db"
if not os.path.exists(target):
    os.makedirs(target)

postgresql_url = "postgresql://postgres:tenno1515@localhost:5432/postgres"
engine = create_engine(postgresql_url, echo=True)

for root, dirs, files in os.walk("../../spacess"):
    tmp = root.replace("../../spacess/", '')
    space_name = tmp.split('/')[0]
    subpath = '/'.join(tmp.split('/')[1:])
    if space_name == '..':
        continue

    try:
        s = Session(engine)
        s.connection().connection.set_isolation_level(0)
        s.exec(text(f"CREATE DATABASE {space_name}"))
        s.close()
    except sqlalchemy.exc.ProgrammingError as e:
        print(e)

    postgresql_url = "postgresql://postgres:tenno1515@localhost:5432/" + space_name
    engine = create_engine(postgresql_url, echo=True)
    with Session(engine) as session:
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
                    if Path(p).is_file() and file.endswith('.json'):
                        entry = json.load(open(p))
                        if payload := entry.get('payload', {}).get('body', None):
                            body = json.load(open(
                                os.path.join(root, dir, '../..', payload)
                            ))
                            entry['payload']['body'] = body
                            entry['subpath'] = subpath
                            entry['resource_type'] = file.replace('.json', '').replace('meta.', '')
                            entry['acl'] = entry.get('acl', [])
                            entry['relationships'] = entry.get('relationships', [])
                            print(entry)
                            if space_name == 'management' and subpath == 'users':
                                session.add(Users.model_validate(entry))
                            else:
                                session.add(Entries.model_validate(entry))
                session.commit()
