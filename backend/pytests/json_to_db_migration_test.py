import time
from uuid import uuid4
import pytest
import os
import json
from pathlib import Path
from sqlmodel import Session, create_engine, text, SQLModel
from data_adapters.sql.create_tables import Attachments, Entries, Spaces, Histories
from sqlalchemy.exc import OperationalError
from utils.settings import settings


def subpath_checker(subpath: str):
    if subpath.endswith("/"):
        subpath = subpath[:-1]
    if not subpath.startswith("/"):
        subpath = '/' + subpath
    return subpath


def connect_with_retry(engine, retries=5, delay=2):
    """
    Try to connect to the database with retries.
    """
    for attempt in range(retries):
        try:
            with engine.connect() as _:
                print(f"Connected to the database on attempt {attempt + 1}")
                return
        except OperationalError as e:
            print(f"Connection attempt {attempt + 1} failed: {e}")
            time.sleep(delay)
    raise Exception("Could not connect to the database after multiple attempts")


@pytest.fixture(scope="module")
def setup_database():
    if settings.active_data_db == "file":
        pytest.skip("Skipping test for file-based database")
        return

    # Use the settings to connect with the main `postgres` user
    postgresql_url = f"{settings.database_driver.replace('+asyncpg','+psycopg')}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}"
    engine = create_engine(f"{postgresql_url}/postgres", echo=False, isolation_level="AUTOCOMMIT")

    # Create the database
    with Session(engine) as session:
        try:
            session.exec(text(f"DROP DATABASE IF EXISTS {settings.database_name}"))
            session.commit()
            session.exec(text(f"CREATE DATABASE {settings.database_name}"))
            session.commit()  # Ensure the transaction is fully committed
            print(f"Database {settings.database_name} created successfully")
        except Exception as e:
            print(f"Database creation failed: {e}")

    # Add a small delay to ensure the database is fully ready
    time.sleep(2)

    yield

    # Drop the database after tests
    with Session(engine) as session:
        try:
            session.exec(text(f"DROP DATABASE IF EXISTS {settings.database_name}"))
            session.commit()
            print(f"Database {settings.database_name} dropped successfully")
        except Exception as e:
            print(f"Database deletion failed: {e}")

    engine.dispose()


@pytest.fixture(scope="module")
def setup_environment(setup_database):
    if settings.active_data_db == "file":
        pytest.skip("Skipping test for file-based database")
        return

    # Set the database name from settings
    driver = settings.database_driver.replace('+asyncpg', '+psycopg')
    postgresql_url = f"{driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}"
    engine = create_engine(f"{postgresql_url}/{settings.database_name}", echo=False)

    # Retry connecting to the newly created database
    connect_with_retry(engine)

    # Generate tables after ensuring connection
    postgresql_url = f"{driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}/{settings.database_name}"
    engine = create_engine(postgresql_url, echo=False)
    SQLModel.metadata.create_all(engine)

    yield engine

    engine.dispose()


def test_json_to_db_migration(setup_environment):
    if settings.active_data_db == "file":
        pytest.skip("Skipping test for file-based database")
        return

    engine = setup_environment

    # Create a complex mock directory structure and files for different entry types
    os.makedirs('/tmp/test_space/.dm', exist_ok=True)
    with open('/tmp/test_space/.dm/meta.space.json', 'w') as f:
        json.dump({"key": "value"}, f)

    # Create more directories and files for the migration
    os.makedirs('/tmp/test_space/dir1', exist_ok=True)
    with open('/tmp/test_space/dir1/history.jsonl', 'w') as f:
        f.write(json.dumps({"key": "history"}) + '\n')

    # Create attachments folder and files
    os.makedirs('/tmp/test_space/dir1/attachments', exist_ok=True)
    with open('/tmp/test_space/dir1/attachments/meta.attachments.json', 'w') as f:
        json.dump({
            "uuid": str(uuid4()),
            "space_name": "test_space",
            "subpath": "/dir1",
            "acl": [],
            "relationships": [],
            "payload": {"body": "attachment content"}
        }, f)

    # Create ticket-related file
    with open('/tmp/test_space/dir1/meta.ticket.json', 'w') as f:
        json.dump({
            "state": "open",
            "is_open": True,
            "reporter": "user1",
            "subpath": "/dir1/ticket"
        }, f)

    # Create user meta file
    with open('/tmp/test_space/.dm/meta.user.json', 'w') as f:
        json.dump({
            "resource_type": "user",
            "firebase_token": "firebase_token",
            "language": "en"
        }, f)

    # Create role meta file
    with open('/tmp/test_space/.dm/meta.role.json', 'w') as f:
        json.dump({
            "resource_type": "role",
            "permissions": ["read", "write"]
        }, f)

    # Create permission meta file
    with open('/tmp/test_space/.dm/meta.permission.json', 'w') as f:
        json.dump({
            "resource_type": "permission",
            "subpaths": {"read": "/read", "write": "/write"},
            "resource_types": ["user", "role"]
        }, f)

    # Run the migration script
    try:
        with Session(engine) as session:
            for root, dirs, _ in os.walk('/tmp/test_space'):
                tmp = root.replace('/tmp/test_space', '')
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

                if subpath == '' or subpath == '/':
                    subpath = '/'
                    p = os.path.join(root, '.dm', 'meta.space.json')
                    entry = {}
                    if Path(p).is_file():
                        entry = json.load(open(p))
                        entry['space_name'] = space_name
                        entry['subpath'] = '/'
                        session.add(Spaces.model_validate(entry))
                    continue

                subpath = subpath.replace('.dm', '')
                if subpath != '/' and subpath.endswith('/'):
                    subpath = subpath[:-1]

                if subpath == '':
                    subpath = '/'

                for dir in dirs:
                    for file in os.listdir(os.path.join(root, dir)):
                        if not file.startswith('meta'):
                            if file == 'history.jsonl':
                                lines = open(os.path.join(root, dir, file), 'r').readlines()
                                for line in lines:
                                    history = json.loads(line)
                                    history['shortname'] = dir
                                    history['space_name'] = space_name
                                    history['subpath'] = subpath_checker(subpath)
                                    session.add(Histories.model_validate(history))
                            continue

                        p = os.path.join(root, dir, file)
                        if Path(p).is_file():
                            if 'attachments' in p:
                                _attachment = json.load(open(os.path.join(root, dir, file)))
                                _attachment['space_name'] = space_name
                                _attachment['uuid'] = _attachment.get('uuid', uuid4())
                                _attachment['subpath'] = subpath_checker(_attachment['subpath'])
                                session.add(Attachments.model_validate(_attachment))
                            elif file.endswith('.json'):
                                entry = json.load(open(p))
                                entry['space_name'] = space_name
                                entry['subpath'] = subpath_checker(subpath)
                                session.add(Entries.model_validate(entry))
            session.commit()
        assert True  # Assert that the migration completes without error
    except Exception as e:
        print(f"Migration failed: {e}")
        assert False  # Fail the test if there is any exception

    # Clean up the mock directory structure
    os.remove('/tmp/test_space/.dm/meta.space.json')
    os.remove('/tmp/test_space/dir1/history.jsonl')
    os.remove('/tmp/test_space/dir1/attachments/meta.attachments.json')
    os.remove('/tmp/test_space/dir1/meta.ticket.json')
    os.remove('/tmp/test_space/.dm/meta.user.json')
    os.remove('/tmp/test_space/.dm/meta.role.json')
    os.remove('/tmp/test_space/.dm/meta.permission.json')
    os.rmdir('/tmp/test_space/dir1/attachments')
    os.rmdir('/tmp/test_space/.dm')
    os.rmdir('/tmp/test_space/dir1')
    os.rmdir('/tmp/test_space')
