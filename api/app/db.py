from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
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
    async with _pool.connection() as conn:
        async with conn.transaction():
            yield conn
