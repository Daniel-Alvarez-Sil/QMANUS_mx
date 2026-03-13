"""
app/routes/health.py — GET /health

Opens a dedicated short-lived probe pool on every call so the check
reflects live reachability without touching tenant pools.
Returns 200 {"status":"ok","tidb":"connected"} or 503 on failure.
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiomysql
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.config import TIDB_DB, TIDB_HOST, TIDB_PASS, TIDB_PORT, TIDB_USER

log = logging.getLogger("agentnexus.health")
router = APIRouter()

_INDEX = Path(__file__).parent.parent.parent / "index.html"


@router.get("/")
async def index() -> FileResponse:
    return FileResponse(_INDEX, media_type="text/html")


@router.get("/health")
async def health() -> JSONResponse:
    try:
        probe = await aiomysql.create_pool(
            host=TIDB_HOST, port=TIDB_PORT,
            user=TIDB_USER, password=TIDB_PASS,
            db=TIDB_DB, maxsize=1, autocommit=True,
        )
        async with probe.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
        probe.close()
        await probe.wait_closed()
    except Exception as exc:
        log.error("Health probe failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "tidb": str(exc)},
        )

    return JSONResponse(content={"status": "ok", "tidb": "connected"})
