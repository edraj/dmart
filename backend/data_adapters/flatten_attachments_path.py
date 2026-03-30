#!/usr/bin/env python3
import os
import argparse
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

Base = declarative_base()

class Attachment(Base):
    __tablename__ = 'attachments'
    uuid = Column(Integer, primary_key=True)
    shortname = Column(String, nullable=False)
    subpath = Column(String, nullable=False)

def rewrite_subpath(subpath: str) -> str:
    """
    Convert '/posts/xxx/yyy/ex1' → '/posts/ex1_xxx_yyy'
    """
    parts = subpath.strip('/').split('/')
    if len(parts) < 2 or parts[0] != 'posts':
        return subpath  # skip non-matching or invalid paths

    *folders, filename = parts[1:]
    suffix = '_'.join(folders)
    if suffix:
        new_name = f"{filename}_{suffix}"
    else:
        new_name = filename

    return f"/posts/{new_name}"

def main():
    parser = argparse.ArgumentParser(
        description="Flatten /posts/* attachment subpaths and encode path into filename."
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
        attachments = session.query(Attachment).filter(
            Attachment.subpath.like('/posts/%')
        ).all()

        print(f"Found {len(attachments)} attachments under /posts/...")

        for att in attachments:
            old = att.subpath
            new = rewrite_subpath(old)
            print(f"- uuid={att.uuid}: '{old}' → '{new}'")
            att.subpath = new

        session.commit()
        print("Done! All attachment subpaths rewritten successfully.")

    except SQLAlchemyError as e:
        session.rollback()
        print("ERROR: Database error. Rolled back changes.")
        print(e)
    finally:
        session.close()

if __name__ == '__main__':
    main()
