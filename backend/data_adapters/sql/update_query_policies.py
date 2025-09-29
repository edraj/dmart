#!/usr/bin/env -S BACKEND_ENV=config.env python3
from __future__ import annotations

import argparse
import asyncio
from typing import Sequence

from sqlalchemy import URL, select, update as sa_update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
# AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import col

from utils.settings import settings
from utils.query_policies_helper import generate_query_policies
from data_adapters.sql.create_tables import Entries


async def update_all_entries(batch_size: int = 1000) -> int:
    postgresql_url = URL.create(
        drivername=settings.database_driver.replace('+asyncpg', '+psycopg'),
        host=settings.database_host,
        port=settings.database_port,
        username=settings.database_username,
        password=settings.database_password,
        database=settings.database_name,
    )

    engine = create_async_engine(
            postgresql_url,
            echo=False,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout,
            pool_recycle=settings.database_pool_recycle,
        )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) # type: ignore

    updated = 0
    offset = 0

    async with async_session() as session: # type: ignore
        while True:
            result = await session.execute(
                select(Entries).order_by(Entries.space_name, Entries.subpath, Entries.shortname).offset(offset).limit(batch_size)
            )
            rows: Sequence[Entries] = [row[0] if not isinstance(row, Entries) else row for row in result.fetchall()]
            if not rows:
                break
            print(f"Processing {len(rows)} entries...")
            for row in rows:
                try:
                    new_policies = generate_query_policies(
                        space_name=row.space_name,
                        subpath=row.subpath,
                        resource_type=row.resource_type,
                        is_active=row.is_active,
                        owner_shortname=getattr(row, 'owner_shortname', 'dmart') or 'dmart',
                        owner_group_shortname=getattr(row, 'owner_group_shortname', None),
                        entry_shortname=row.shortname if row.resource_type == 'folder' else None,
                    )
                except Exception as e:
                    print(f"Error while computing query_policies for {row.space_name}/{row.subpath}/{row.shortname}")
                    print(f"| {e}\n")
                    continue

                if row.query_policies != new_policies:
                    await session.execute(
                        sa_update(Entries)
                        .where(col(Entries.space_name) == row.space_name)
                        .where(col(Entries.subpath) == row.subpath)
                        .where(col(Entries.shortname) == row.shortname)
                        .values(query_policies=new_policies)
                    )
                    updated += 1
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                raise

            offset += len(rows)

    await engine.dispose()
    return updated


async def amain(batch_size: int) -> None:
    updated = await update_all_entries(batch_size=batch_size)
    print(f"Updated query_policies for {updated} entries.")


def main():
    parser = argparse.ArgumentParser(description="Recompute query_policies for all Entries")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for processing entries")
    args = parser.parse_args()
    asyncio.run(amain(args.batch_size))


if __name__ == "__main__":
    main()
