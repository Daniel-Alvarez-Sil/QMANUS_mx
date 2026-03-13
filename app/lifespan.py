"""
app/lifespan.py — FastAPI application lifespan (startup + shutdown).

Startup : opens a short-lived probe pool to verify TiDB reachability.
Shutdown: iterates db.pools and closes every tenant pool gracefully.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import aiomysql
from fastapi import FastAPI

from app.config import TIDB_DB, TIDB_HOST, TIDB_PASS, TIDB_PORT, TIDB_USER
from app.db import pools
from db import ssl_ctx

log = logging.getLogger("agentnexus.lifespan")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    try:
        # Use synchronous mysql connector in thread pool to avoid Windows SSL issues
        import mysql.connector
        import asyncio
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: mysql.connector.connect(
            host=TIDB_HOST, port=TIDB_PORT,
            user=TIDB_USER, password=TIDB_PASS,
            database=TIDB_DB,
            ssl_disabled=False,
            ssl_ca=None,
            connection_timeout=5,
        ).close())
        
        log.info("TiDB connected")
    except Exception as exc:
        log.warning("TiDB startup probe failed: %s", exc)

    yield  # ← application is running

    # ── Shutdown ──────────────────────────────────────────────────────────────
    for tid, pool in list(pools.items()):
        pool.close()
        await pool.wait_closed()
        log.info("Pool closed  tenant=%s", tid)
    pools.clear()
    log.info("All TiDB pools closed")
