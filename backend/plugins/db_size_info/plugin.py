from contextlib import asynccontextmanager
from fastapi import APIRouter
from fastapi.logger import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import Any

from utils.settings import settings

router = APIRouter()


def _build_engine():
    driver   = settings.database_driver
    user     = settings.database_username
    password = settings.database_password
    host     = settings.database_host
    port     = settings.database_port
    name     = settings.database_name

    url = f"{driver}://{user}:{password}@{host}:{port}/{name}"
    return create_async_engine(url, pool_pre_ping=True)


_engine = _build_engine()
_async_session: Any = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False) if _engine else None


@asynccontextmanager
async def get_session():
    if _async_session is None:
        raise RuntimeError("db_size_info: database engine is not initialised")
    async with _async_session() as session:
        yield session


@router.get("/")
async def get_db_size_info() -> dict[str, Any]:
    query = """
    select
        table_name,
        pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) as pretty_size
    from information_schema.tables
    where table_schema = 'public'
    order by 2 desc;
    """
    try:
        async with get_session() as session:
            result = await session.execute(text(query))
            rows = result.fetchall()

        data = [
            {
                "table_name": str(row[0]),
                "pretty_size": str(row[1])
            }
            for row in rows
        ]
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"db_size_info: query error: {e}")
        return {"status": "failed", "error": str(e)}
