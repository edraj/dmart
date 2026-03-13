import os
import re
from sqlalchemy import create_engine, select, update, MetaData, Table
from sqlalchemy.orm import Session

# --- DB Connection ---
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:root@localhost:5432/catalog_db")
engine = create_engine(DB_URL)
metadata = MetaData()
attachments = Table("attachments", metadata, autoload_with=engine)

def clean_shortname(name: str) -> str:
    if not name:
        return name

    # Step 1: Remove extension if present (last dot + extension)
    name_no_ext = re.sub(r"\.[a-zA-Z0-9]{1,5}$", "", name)

    # Step 2: Remove all other dots
    cleaned = name_no_ext.replace(".", "")

    return cleaned

def main():
    with Session(engine) as session:
        stmt = select(attachments.c.uuid, attachments.c.shortname)
        results = session.execute(stmt).fetchall()

        print(f"Found {len(results)} entries.")

        for row in results:
            att_id, shortname = row
            new_shortname = clean_shortname(shortname)

            if new_shortname != shortname:
                print(f"Updating {shortname} -> {new_shortname}")
                upd = (
                    update(attachments)
                    .where(attachments.c.uuid == att_id)
                    .values(shortname=new_shortname)
                )
                session.execute(upd)

        session.commit()
        print("✅ Done updating shortnames.")

if __name__ == "__main__":
    main()
