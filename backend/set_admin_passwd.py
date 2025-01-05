#!/usr/bin/env -S BACKEND_ENV=config.env python3
from data_adapters.sql.sql_adapter import SQLAdapter
from data_adapters.sql.create_tables import Users
from utils.password_hashing import hash_password
from utils.settings import settings
import json
import getpass
import subprocess
import utils.regex as regex
import re
from sqlmodel import select


users : dict[str, dict]= {"dmart":{}, "alibaba": {}}

while True:
    password = getpass.getpass("Enter the admin/testuser password then hit enter: ")
    if re.match(regex.PASSWORD, password):
        break
    else:
        print("Password didn't match the rules: >= 8 chars that are Alphanumeric mix cap/small with _#@%*!?$^- ")

print("Generating and storing the password for admin and testuser")
hashed = hash_password(password)

if settings.active_data_db == "file":
    for key in users.keys():
        file_name = settings.spaces_folder / f"management/users/.dm/{key}/meta.user.json"
        with open(file_name, 'r') as read_file:
            data = json.load(read_file)
            data["password"] = hashed
            with open(file_name, 'w') as write_file:
                write_file.write(json.dumps(data))
else:
    with SQLAdapter().get_session() as session:
        for key in users.keys():
            statement = select(Users).where(Users.shortname == key)
            user = session.exec(statement).one()
            user.password=hashed
            user.is_active=True
            session.add(user)
            session.commit()



with open("./login_creds.sh", 'w') as creds:
    subprocess.run( [ "sed", f"s/xxxx/{password}/g", "login_creds.sh.sample" ], stdout=creds)
print("Done")

