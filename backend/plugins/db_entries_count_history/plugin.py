import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.logger import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from utils.settings import settings

router = APIRouter()

CONFIG_PATH = Path(__file__).parent / "config.json"


def _load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"db_entries_count_history: Failed to load config.json: {e}")
        return {}


def _build_engine():
    driver = settings.database_driver
    user = settings.database_username
    password = settings.database_password
    host = settings.database_host
    port = settings.database_port
    name = settings.database_name

    url = f"{driver}://{user}:{password}@{host}:{port}/{name}"
    return create_async_engine(url, pool_pre_ping=True)


_config = _load_config()
_engine = _build_engine()
_async_session: Any = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore


@asynccontextmanager
async def get_session():
    async with _async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def background_task() -> None:
    try:
        async with get_session() as session:
            await session.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS count_history ("
                    "id SERIAL PRIMARY KEY, "
                    "spacename VARCHAR(255) NOT NULL, "
                    "entries_count BIGINT NOT NULL, "
                    "recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            await session.execute(text("CREATE INDEX IF NOT EXISTS idx_count_history_spacename ON count_history(spacename)"))
    except Exception as e:
        logger.error(f"db_entries_count_history: Failed to create table: {e}")
        return


print("Starting db_entries_count_history background task")
asyncio.create_task(background_task())


@router.get("/")
async def get_db_entries_count_history() -> dict[str, Any]:
    try:
        async with get_session() as session:
            tables_query = text(
                "SELECT table_name FROM information_schema.columns WHERE column_name = 'space_name' AND table_schema = 'public'"
            )
            tables_result = await session.execute(tables_query)
            tables = [row[0] for row in tables_result.fetchall()]

            spaces_counts: dict[str, int] = {}
            for table in tables:
                if table == "count_history" or "log" in table or "history" in table:
                    continue
                try:
                    # Validate table name to prevent SQL injection (only allow identifier chars)
                    import re as _re

                    if not _re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table):
                        continue
                    count_res = await session.execute(text(f"SELECT space_name, count(*) FROM {table} GROUP BY space_name"))
                    for row in count_res.fetchall():
                        space_name, count = row[0], row[1]
                        if space_name:
                            spaces_counts[space_name] = spaces_counts.get(space_name, 0) + count
                except Exception as _:
                    pass  # Ignore tables that cannot be counted

            for space_name, current_count in spaces_counts.items():
                last_row = (
                    await session.execute(
                        text(
                            "SELECT entries_count FROM count_history "
                            "WHERE spacename = :space_name ORDER BY recorded_at DESC LIMIT 1"
                        ),
                        {"space_name": space_name},
                    )
                ).fetchone()
                print(space_name, current_count)
                if not last_row or last_row[0] != current_count:
                    await session.execute(
                        text("INSERT INTO count_history (spacename, entries_count) VALUES (:space_name, :count)"),
                        {"space_name": space_name, "count": current_count},
                    )

    except Exception as e:
        logger.error(f"db_entries_count_history: Background task error: {e}")

    query = "SELECT spacename, entries_count, recorded_at FROM count_history ORDER BY spacename, recorded_at ASC"
    try:
        async with get_session() as session:
            result = await session.execute(text(query))
            rows = result.fetchall()

        grouped: dict[str, list] = {}
        for row in rows:
            spacename = row[0]
            recorded_at = row[2]
            if hasattr(recorded_at, "strftime"):
                recorded_at_str = recorded_at.strftime("%Y-%m-%dT%H:%M")
            else:
                recorded_at_str = str(recorded_at)[:16]

            grouped.setdefault(spacename, []).append({"entries_count": row[1], "recorded_at": recorded_at_str})

        data = [{"spacename": sn, "data": entries} for sn, entries in grouped.items()]
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"db_entries_count_history: query error: {e}")
        return {"status": "failed", "error": str(e)}
