#!/usr/bin/env -S BACKEND_ENV=config.env python3
from enum import StrEnum

from sqlalchemy import update

from data_adapters.sql_adapter import SQLAdapter
from utils.database.create_tables import Users, Roles, Permissions, Entries, Spaces, Attachments
from utils.password_hashing import hash_password
from utils.settings import settings
import argparse
import json
import getpass
import subprocess
import utils.regex as regex
import re
from sqlmodel import select


'''
# add new key to the records
## with default value
./schema_modulate.py --space management --subpath users -t +payload.body.xxx -v 123
## default value is None
./schema_modulate.py --space management --subpath users -t +payload.body.xxx

# remove key from the records
./schema_modulate.py --space management --subpath users -t ~payload.body.xxx

# update key in the records
./schema_modulate.py --space management --subpath users -t payload.body.xxx -v yyy
'''

class ResourceType(StrEnum):
    add = "add"
    remove = "remove"
    update = "update"


def handle_sql_modulation(args):
    if args.space:
        if args.space == "management":
            if args.subpath is None:
                spaces = [Users, Roles, Permissions, Spaces, Attachments]
            if args.subpath == "~attachments":
                spaces = [Attachments]
            else:
                if args.subpath == "users":
                    spaces = [Users]
                elif args.subpath == "roles":
                    spaces = [Roles]
                elif args.subpath == "permissions":
                    spaces = [Permissions]
                elif args.subpath == "~spaces":
                    spaces = [Permissions]
                else:
                    spaces = [Entries]
        else:
            spaces = [Entries]
            if args.subpath == "~attachments":
                spaces.append(Attachments)
    else:
        spaces = [Entries, Users, Roles, Permissions, Spaces, Attachments]

    targets = args.target.split(".")

    state = ResourceType.update
    if targets[0].startswith("+"):
        print(f"[info] Adding new key '{targets[0]}' to the records")
        state = ResourceType.add
        targets[0] = targets[0][1:]

        if args.value:
            print(f"[warn] flag -v --value is not required for adding new key")
    if targets[0].startswith("~"):
        print(f"[info] Removing key '{targets[0]}' from the records")
        state = ResourceType.remove
        targets[0] = targets[0][1:]

        if args.value:
            print(f"[warn] flag -v --value is not required for removing key")
    else:
        print(f"[info] Altering the key '{targets[0]}' fo records")\

    if targets[0] not in ["description", "displayname", "payload"]:
        raise Exception("target must be either 'description', 'displayname' or 'payload'")

    with SQLAdapter().get_session() as session:
        for space in spaces:
            print("[info] Processing...", space)

            statement = select(space)

            if space not in [Users, Roles, Permissions, Spaces, Attachments]:
                statement = statement.where(space.shortname == args.space)

            records = session.exec(statement).all()
            print("[info] # Records found:", len(records))
            print("[info] state:", state)
            for record in records:
                if hasattr(record, targets[0]):
                    if state == ResourceType.update:
                        obj = getattr(record, targets[0])
                        if obj:
                            keys = targets
                            sub_obj = obj
                            for key in keys[1:-1]:
                                if not bool(sub_obj):
                                    break
                                sub_obj = sub_obj.get(key, {})

                            if not bool(sub_obj):
                                continue

                            if keys[-1] in sub_obj:
                                sub_obj[args.value] = sub_obj.pop(keys[-1])

                    elif state == ResourceType.add:
                        obj = getattr(record, targets[0])
                        if obj is None:
                            setattr(record, targets[0], {})
                        keys = targets
                        sub_obj = obj
                        for key in keys[1:-1]:
                            if not bool(sub_obj):
                                break
                            sub_obj = sub_obj.get(key, {})

                        if not bool(sub_obj):
                            continue

                        if keys[-1] not in sub_obj:
                            sub_obj[keys[-1]] = args.value

                    elif state == ResourceType.remove:
                        obj = getattr(record, targets[0])
                        if obj:
                            keys = targets
                            sub_obj = obj
                            for key in keys[1:-1]:
                                sub_obj = sub_obj.get(key, {})
                            if not bool(sub_obj):
                                continue
                            if keys[-1] in sub_obj:
                                sub_obj.pop(keys[-1])

                            print(obj)
                            setattr(record, targets[0], obj)

                stmt = update(space).where(space.uuid == record.uuid).values(
                    **{targets[0]: getattr(record, targets[0])})
                session.exec(stmt)
            session.commit()



def handle_file_modulation(args):
    pass



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Modulate schema field type",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--space",
        default=None
    )
    parser.add_argument(
        "--subpath",
        default=None
    )
    parser.add_argument(
        "-t", "--target"
    )
    parser.add_argument(
        "-v", "--value",
        default=None
    )

    args = parser.parse_args()

    if settings.active_data_db == "sql":
        handle_sql_modulation(args)
    else:
        handle_file_modulation(args)
