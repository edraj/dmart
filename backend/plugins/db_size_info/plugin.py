from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter
from fastapi.logger import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from data_adapters.adapter import data_adapter as _db

router = APIRouter()


_async_session: Any = sessionmaker(_db.engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore[attr-defined]


@asynccontextmanager
async def get_session():
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

        data = [{"table_name": str(row[0]), "pretty_size": str(row[1])} for row in rows]
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"db_size_info: query error: {e}")
        return {"status": "failed", "error": str(e)}
