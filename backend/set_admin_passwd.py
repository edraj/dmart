#!/usr/bin/env -S BACKEND_ENV=config.env python3
import asyncio
import getpass
import re
from pathlib import Path

from sqlmodel import select

import utils.regex as regex
from data_adapters.sql.adapter import SQLAdapter
from data_adapters.sql.create_tables import Users
from utils.password_hashing import hash_password

users: dict[str, dict] = {"dmart": {}, "alibaba": {}}

while True:
    password = getpass.getpass("Type the new password for admin/testuser then hit enter: ")
    if re.match(regex.PASSWORD, password):
        break
    else:
        print("Password didn't match the rules: >= 8 chars that are Alphanumeric mix cap/small with _#@%*!?$^- ")

print("Generating and storing the password for dmart and alibaba")
hashed = hash_password(password)


async def main():
    async with SQLAdapter().get_session() as session:
        for key in users:
            statement = select(Users).where(Users.shortname == key)
            user = (await session.execute(statement)).one()[0]
            user.password = hashed
            user.is_active = True
            session.add(user)
            await session.commit()


asyncio.run(main())

login_creds_sample = Path(__file__).resolve().parent / "login_creds.sh.sample"
if login_creds_sample.exists():
    home_dmart = Path.home() / ".dmart"
    home_dmart.mkdir(parents=True, exist_ok=True)

    login_creds_path = home_dmart / "login_creds.sh"
    with open(login_creds_sample) as sample_f:
        sample_content = sample_f.read()

    with open(login_creds_path, "w") as creds:
        creds.write(sample_content.replace("xxxx", password))

    cli_ini_path = home_dmart / "cli.ini"
    if cli_ini_path.exists():
        try:
            with open(cli_ini_path) as f:
                content = f.read()

            new_content = re.sub(r'password\s*=\s*".*"', f'password = "{password}"', content)

            with open(cli_ini_path, "w") as f:
                f.write(new_content)
            print(f"Updated password in {cli_ini_path}")
        except Exception as e:
            print(f"Warning: Failed to update cli.ini: {e}")

print("Done")
