"""
app/db.py — Per-tenant aiomysql connection pool manager.

Public API
----------
pools       : module-level dict[str, Pool] — iterated by lifespan on shutdown
get_conn    : acquire a READ-COMMITTED connection from the tenant's pool
release_conn: return the connection back to the pool
"""

from __future__ import annotations

import asyncio
import logging

import aiomysql

from app.config import TIDB_DB, TIDB_HOST, TIDB_PASS, TIDB_PORT, TIDB_USER

log = logging.getLogger("agentnexus.db")

# One aiomysql pool per tenant — lazily created on first request
pools: dict[str, aiomysql.Pool] = {}

# Per-tenant asyncio.Lock prevents duplicate pool creation under concurrency
_pool_create_locks: dict[str, asyncio.Lock] = {}
_pool_create_locks_lock = asyncio.Lock()   # guards the lock-dict itself


async def _pool_lock(tenant_id: str) -> asyncio.Lock:
    """Return (creating if necessary) the per-tenant initialisation lock."""
    async with _pool_create_locks_lock:
        if tenant_id not in _pool_create_locks:
            _pool_create_locks[tenant_id] = asyncio.Lock()
        return _pool_create_locks[tenant_id]


async def _get_or_create_pool(tenant_id: str) -> aiomysql.Pool:
    """Lazily initialise a dedicated 10-connection pool for *tenant_id*."""
    if tenant_id in pools:          # fast path — no locking needed post-init
        return pools[tenant_id]

    lock = await _pool_lock(tenant_id)
    async with lock:
        if tenant_id not in pools:  # double-checked locking
            pool = await aiomysql.create_pool(
                host=TIDB_HOST,
                port=TIDB_PORT,
                user=TIDB_USER,
                password=TIDB_PASS,
                db=TIDB_DB,
                maxsize=10,
                autocommit=True,
            )
            pools[tenant_id] = pool
            log.info("Pool created  tenant=%s", tenant_id)
    return pools[tenant_id]


async def get_conn(tenant_id: str) -> aiomysql.Connection:
    """
    Acquire a connection from the tenant-scoped pool.
    Enforces READ-COMMITTED isolation on every connection (TiDB best practice).
    """
    pool = await _get_or_create_pool(tenant_id)
    conn = await pool.acquire()
    async with conn.cursor() as cur:
        await cur.execute("SET SESSION tidb_isolation_level = 'READ-COMMITTED'")
    return conn


async def release_conn(tenant_id: str, conn: aiomysql.Connection) -> None:
    """Return *conn* to its tenant pool."""
    if tenant_id in pools:
        pools[tenant_id].release(conn)
