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
-a --atrb: only with [description, displayname]

# add new key to the records
./schema_modulate.py -a --space management --subpath users  -t +description.pt

# remove key from the records
./schema_modulate.py -a --space management --subpath users  -t ~description.pt

# update key in the records
./schema_modulate.py -a --space management --subpath users  -t description.en -v EN
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

    if args.atrb:
        targets = args.target.split(".")
        if len(targets) != 2:
            raise Exception("target must be in the format 'model.field'")

        state = ResourceType.update
        if targets[0].startswith("+"):
            print(f"Adding new key '{targets[0]}' to the records")
            state = ResourceType.add
            targets[0] = targets[0][1:]

            if args.value:
                print(f"flag -v --value is not required for adding new key")
        if targets[0].startswith("~"):
            print(f"Removing key '{targets[0]}' from the records")
            state = ResourceType.remove
            targets[0] = targets[0][1:]

            if args.value:
                print(f"flag -v --value is not required for removing key")
        else:
            print(f"Altering the key '{targets[0]}' fo records")\

        if targets[0] not in ["description", "displayname"]:
            raise Exception("target must be either 'description' or 'displayname'")

        with SQLAdapter().get_session() as session:
            for space in spaces:
                print("Processing...", space)

                statement = select(space)

                if space not in [Users, Roles, Permissions, Spaces, Attachments]:
                    statement = statement.where(space.shortname == args.space)

                records = session.exec(statement).all()
                print("# Records found:", len(records))
                print("state:", state)
                for record in records:
                    if hasattr(record, targets[0]):
                        if state == ResourceType.update:
                            obj = getattr(record, targets[0])
                            if obj and targets[1] in obj.keys():
                                obj[args.value] = obj.pop(targets[1])
                                # setattr(record, targets[0], obj)
                                record.description = obj
                        elif state == ResourceType.add:
                            obj = getattr(record, targets[0])
                            if obj is None:
                                obj = {targets[1]: None}
                                record.description = obj
                            if obj is not None and targets[1] not in obj.keys():
                                obj[targets[1]] = None
                                record.description = obj
                        elif state == ResourceType.remove:
                            obj = getattr(record, targets[0])
                            if obj is not None and targets[1] in obj.keys():
                                obj.pop(targets[1])
                                record.description = obj

                    # session.add(record)
                    stmt = update(space).where(space.uuid == record.uuid).values(
                        **{targets[0]: getattr(record, targets[0])})
                    session.exec(stmt)
                session.commit()

        return

    if args.atrb:
        print("SQL Modulation", args.payload)

        return

    # print("SQL Modulation", args.atrb)
    # print("SQL Modulation", args.payload)
    # print("SQL Modulation", args.target)
    # print("SQL Modulation", args.value)

    raise NotImplementedError

def handle_file_modulation(args):
    pass



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Modulate schema field type",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-a",
        "--atrb",
        help="Alter attribute",
        action='store_true'
    )
    parser.add_argument(
        "-p",
        "--payload",
        help="Alter Payload",
        action='store_true'
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

    if not (bool(args.atrb) ^ bool(args.payload)):
        parser.error("Please provide either -a or -p flag")

    if settings.active_data_db == "sql":
        handle_sql_modulation(args)
    else:
        handle_file_modulation(args)
