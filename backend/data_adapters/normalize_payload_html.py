#!/usr/bin/env python3
import os
import argparse
import json
from sqlalchemy import create_engine, Column, Integer, Text, String
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

Base = declarative_base()

class Entry(Base):
    __tablename__ = "entries"
    uuid = Column(Integer, primary_key=True)
    space_name = Column(String, nullable=True)
    payload = Column(Text, nullable=True)  # stored as JSON string

def normalize_payload(payload_val):
    print(f"Normalizing payload ------------------- : {str(payload_val)[:120]}...")

    if not payload_val:  # skip None or empty
        return payload_val

    # If DB gave us a string, parse it; if already dict, keep as is
    if isinstance(payload_val, str):
        try:
            data = json.loads(payload_val)
        except json.JSONDecodeError:
            return payload_val  # skip invalid JSON
    elif isinstance(payload_val, dict):
        data = payload_val
    else:
        return payload_val  # unknown type, skip

    # Normalize content_type
    if data.get("content_type") == "text/html; charset=utf-8" or data.get("content_type") == "text/html; charset=utf8":
        data["content_type"] = "html"

    # Flatten body if it has {"embedded": "..."}
    body = data.get("body")
    if isinstance(body, dict) and "embedded" in body:
        data["body"] = body["embedded"]

    # Always save back as JSON string in DB
    return json.dumps(data, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="Normalize entries.payload for space_name='wwwimx': simplify content_type and flatten body.embedded."
    )
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL"),
        help="SQLAlchemy DB URL (e.g. postgresql://user:pass@host/dbname)"
    )
    args = parser.parse_args()

    if not args.db_url:
        parser.error("Provide a database URL via --db-url or set DATABASE_URL env var.")

    engine = create_engine(args.db_url, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # ✅ Only fetch entries with space_name = 'wwwimx'
        entries = session.query(Entry).filter(Entry.space_name == "wwwimx").all()
        print(f"Found {len(entries)} entries with space_name='wwwimx'.")

        updated_count = 0
        skipped_count = 0

        for entry in entries:
            if not entry.payload:
                skipped_count += 1
                continue

            new_payload = normalize_payload(entry.payload)
            if new_payload != entry.payload:
                print(f"- Updating entry uuid={entry.uuid}")
                entry.payload = new_payload
                updated_count += 1

        if updated_count > 0:
            session.commit()
            print(f"✅ Updated {updated_count} entries. Skipped {skipped_count}.")
        else:
            print(f"No changes needed. Skipped {skipped_count} entries with empty/invalid payload.")

    except SQLAlchemyError as e:
        session.rollback()
        print("❌ Database error, rolled back.")
        print(e)
    finally:
        session.close()

if __name__ == "__main__":
    main()
