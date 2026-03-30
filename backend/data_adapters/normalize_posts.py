#!/usr/bin/env python3
import os
import argparse
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError

Base = declarative_base()

class Entry(Base):
    __tablename__ = 'entries'
    uuid = Column(Integer, primary_key=True)
    shortname = Column(String, unique=True, nullable=False)
    subpath = Column(String, nullable=False)

def normalize_suffix(subpath: str) -> str:
    # remove leading '/posts/' and replace '/' with '_'
    suffix = subpath.removeprefix('/posts/').strip('/')
    return suffix.replace('/', '_') or 'root'

def main():
    parser = argparse.ArgumentParser(
        description="Normalize all /posts/* subpaths to '/posts' and adjust shortnames to avoid collisions."
    )
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL"),
        help="SQLAlchemy DB URL (e.g. postgresql://user:pass@host/dbname)"
    )
    args = parser.parse_args()

    if not args.db_url:
        parser.error("You must supply a database URL via --db-url or DATABASE_URL env var.")

    engine = create_engine(args.db_url, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Track how many times we’ve used the same base new-name, to append counters
    used_names = {}

    try:
        entries = session.query(Entry).filter(Entry.subpath.like('/posts/%')).all()
        print(f"Found {len(entries)} entries with subpath '/posts/*'")

        for e in entries:
            original = e.subpath
            suffix = normalize_suffix(original)
            base_new = f"{e.shortname}_{suffix}"

            # If we've already used this base_new once, append a counter
            count = used_names.get(base_new, 0)
            new_short = f"{base_new}" if count == 0 else f"{base_new}_{count+1}"
            used_names[base_new] = count + 1

            print(f"- Updating uuid={e.uuid}: '{e.shortname}' @ '{e.subpath}' → shortname='{new_short}', subpath='/posts'")

            e.shortname = new_short
            e.subpath = '/posts'

        session.commit()
        print("All done! Changes committed.")

    except IntegrityError as ie:
        session.rollback()
        print("ERROR: Integrity constraint violated (likely a duplicate shortname).")
        print(ie)
    except Exception as ex:
        session.rollback()
        print("Unexpected error, rolled back.")
        print(ex)
    finally:
        session.close()

if __name__ == '__main__':
    main()
