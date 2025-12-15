import asyncio

from sqlmodel import select

from data_adapters.sql.adapter import SQLAdapter
from data_adapters.sql.create_tables import Users
from models.core import Folder
from data_adapters.adapter import data_adapter as db


async def main() -> None:
    users_processed = 0
    folder_processed = 0

    async with SQLAdapter().get_session() as session:
        statement = select(Users)
        results = list((await session.execute(statement)).all())
        print(f"Found {len(results)} users")
        for entry in results:
            entry_shortname = entry[0].shortname
            folders = [
                ("personal", "people", entry_shortname),
                ("personal", f"people/{entry_shortname}", "notifications"),
                ("personal", f"people/{entry_shortname}", "private"),
                ("personal", f"people/{entry_shortname}", "protected"),
                ("personal", f"people/{entry_shortname}", "public"),
                ("personal", f"people/{entry_shortname}", "inbox"),
            ]
            try:
                for folder in folders:
                    await db.internal_save_model(
                        space_name=folder[0],
                        subpath=folder[1],
                        meta=Folder(
                            shortname=folder[2],
                            is_active=True,
                            owner_shortname=entry_shortname
                        )
                    )
                    print(f"Created folder {folder} for user {entry_shortname}")
                    folder_processed += 1
            except Exception as e:
                print(f"Error creating folders for user {entry_shortname}: {e}")

            users_processed += 1


    print(f"\n===== DONE ====== \nScanned {users_processed} users,\
    Created {folder_processed} missing folders")


if __name__ == "__main__":
    asyncio.run(main())
