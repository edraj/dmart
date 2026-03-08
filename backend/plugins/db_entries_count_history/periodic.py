#!/usr/bin/env -S BACKEND_ENV=config.env python3
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from utils.settings import settings

CONFIG_PATH = Path(__file__).parent / "config.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("db_entries_count_history.periodic")


def _load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def _build_engine():
    driver   = settings.database_driver
    user     = settings.database_username
    password = settings.database_password
    host     = settings.database_host
    port     = settings.database_port
    name     = settings.database_name
    url = f"{driver}://{user}:{password}@{host}:{port}/{name}"
    return create_async_engine(url, pool_pre_ping=True)


async def ensure_table(session: AsyncSession) -> None:
    await session.execute(text(
        "CREATE TABLE IF NOT EXISTS count_history ("
        "id SERIAL PRIMARY KEY, "
        "spacename VARCHAR(255) NOT NULL, "
        "entries_count BIGINT NOT NULL, "
        "recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
        ")"
    ))
    await session.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_count_history_spacename "
        "ON count_history(spacename)"
    ))
    await session.commit()
    log.info("count_history table ready")


async def snapshot(session: AsyncSession) -> None:
    """Count entries per space and insert a row only when the count changed."""
    tables_result = await session.execute(text(
        "SELECT table_name FROM information_schema.columns "
        "WHERE column_name = 'space_name' AND table_schema = 'public'"
    ))
    tables = [row[0] for row in tables_result.fetchall()]

    spaces_counts: dict[str, int] = {}
    for table in tables:
        if table in ("count_history",) or "log" in table or "history" in table:
            continue
        try:
            count_res = await session.execute(
                text(f"SELECT space_name, count(*) FROM {table} GROUP BY space_name")
            )
            for row in count_res.fetchall():
                space_name, count = row[0], row[1]
                if space_name:
                    spaces_counts[space_name] = spaces_counts.get(space_name, 0) + count
        except Exception:
            pass  # skip tables/views that can't be counted

    inserted = 0
    for space_name, current_count in spaces_counts.items():
        last_row = (await session.execute(
            text(
                "SELECT entries_count FROM count_history "
                "WHERE spacename = :sn ORDER BY recorded_at DESC LIMIT 1"
            ),
            {"sn": space_name},
        )).fetchone()

        if not last_row or last_row[0] != current_count:
            await session.execute(
                text(
                    "INSERT INTO count_history (spacename, entries_count) "
                    "VALUES (:sn, :cnt)"
                ),
                {"sn": space_name, "cnt": current_count},
            )
            inserted += 1

    await session.commit()
    log.info(f"Snapshot done — {len(spaces_counts)} spaces checked, {inserted} rows inserted")


async def run() -> None:
    engine = _build_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) # type: ignore

    @asynccontextmanager
    async def get_session():
        yield async_session()

    # ensure the table exists once at startup
    async with get_session() as session:
        await ensure_table(session) # type: ignore

    try:
        async with get_session() as session:
            await snapshot(session) # type: ignore
    except Exception as e:
        log.error(f"Snapshot failed: {e}")



if __name__ == "__main__":
    asyncio.run(run())
