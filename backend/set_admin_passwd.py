#!/usr/bin/env -S BACKEND_ENV=config.env python3
import asyncio
import json
import getpass
import subprocess
import utils.regex as regex
import re
from pathlib import Path
from sqlmodel import select

from data_adapters.sql.adapter import SQLAdapter
from data_adapters.sql.create_tables import Users
from utils.password_hashing import hash_password
from utils.settings import settings


users : dict[str, dict]= {"dmart":{}, "alibaba": {}}

while True:
    password = getpass.getpass("Type the new password for admin/testuser then hit enter: ")
    if re.match(regex.PASSWORD, password):
        break
    else:
        print("Password didn't match the rules: >= 8 chars that are Alphanumeric mix cap/small with _#@%*!?$^- ")

print("Generating and storing the password for dmart and alibaba")
hashed = hash_password(password)

async def main():
    if settings.active_data_db == "file":
        for key in users.keys():
            file_name = settings.spaces_folder / f"management/users/.dm/{key}/meta.user.json"
            with open(file_name, 'r') as read_file:
                data = json.load(read_file)
                data["password"] = hashed
                with open(file_name, 'w') as write_file:
                    write_file.write(json.dumps(data))
    else:
        async with SQLAdapter().get_session() as session:
            for key in users.keys():
                statement = select(Users).where(Users.shortname == key)
                user = (await session.execute(statement)).one()[0]
                user.password=hashed
                user.is_active=True
                session.add(user)
                await session.commit()


asyncio.run(main())

login_creds_sample = Path(__file__).resolve().parent / "login_creds.sh.sample"
if login_creds_sample.exists():
    with open("./login_creds.sh", 'w') as creds:
        subprocess.run( [ "sed", f"s/xxxx/{password}/g", str(login_creds_sample) ], stdout=creds)
print("Done")
