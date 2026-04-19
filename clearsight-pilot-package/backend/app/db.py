"""Postgres connection pool."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import psycopg
from psycopg_pool import AsyncConnectionPool

from .config import settings

pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    global pool
    if pool is None:
        pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=10,
            kwargs={"autocommit": True},
            open=False,
        )
        await pool.open()


async def close_pool() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


@asynccontextmanager
async def get_conn() -> AsyncIterator[psycopg.AsyncConnection]:
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    async with pool.connection() as conn:
        yield conn
