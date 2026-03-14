#!/usr/bin/env python3
import os
import argparse
import json
from sqlalchemy import create_engine, Column, Integer, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

Base = declarative_base()

class Attachment(Base):
    __tablename__ = "attachments"
    uuid = Column(Integer, primary_key=True)
    payload = Column(Text, nullable=True)  # stored as JSON string (or JSONB deserialized to dict)

def normalize_content_type(ct_val):
    if not ct_val:
        return ct_val
    ct = str(ct_val).lower().strip()

    # text/html; charset=... -> html
    if ct.startswith("text/html"):
        return "html"

    # text/plain; charset=... -> plain
    if ct.startswith("text/plain"):
        return "plain"

    # image/png; ... OR image/jpeg; ... -> image
    if ct.startswith("image/"):
        return "image"

    # otherwise leave as-is
    return ct_val

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

    # Normalize only content_type per your rules
    if "content_type" in data:
        new_ct = normalize_content_type(data.get("content_type"))
        if new_ct != data.get("content_type"):
            data["content_type"] = new_ct

    # Always save back as JSON string in DB
    return json.dumps(data, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser(
        description="Normalize attachments.payload content_type: html/plain/image."
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
        attachments = session.query(Attachment).all()
        print(f"Found {len(attachments)} attachments.")

        updated_count = 0
        skipped_count = 0

        for att in attachments:
            if not att.payload:
                skipped_count += 1
                continue

            new_payload = normalize_payload(att.payload)
            if new_payload != att.payload:
                print(f"- Updating attachment uuid={att.uuid}")
                att.payload = new_payload
                updated_count += 1

        if updated_count > 0:
            session.commit()
            print(f"✅ Updated {updated_count} attachments. Skipped {skipped_count}.")
        else:
            print(f"No changes needed. Skipped {skipped_count} attachments with empty/invalid payload.")

    except SQLAlchemyError as e:
        session.rollback()
        print("❌ Database error, rolled back.")
        print(e)
    finally:
        session.close()

if __name__ == "__main__":
    main()
