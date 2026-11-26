from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import get_settings

_pool: AsyncConnectionPool | None = None


async def init_db() -> None:
    global _pool
    settings = get_settings()
    _pool = AsyncConnectionPool(
        settings.database_url,
        min_size=2,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    await _pool.open()
    await _pool.wait()


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection():
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    async with _pool.connection() as conn:
        yield conn


@asynccontextmanager
async def get_transaction():
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    async with _pool.connection() as conn, conn.transaction():
        yield conn


async def fetchone(conn, query: str, params: tuple | None = None):
    async with conn.cursor() as cur:
        await cur.execute(query, params)
        return await cur.fetchone()
