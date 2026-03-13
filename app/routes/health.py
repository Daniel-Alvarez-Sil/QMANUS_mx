"""
app/routes/health.py — GET /health

Opens a dedicated short-lived probe pool on every call so the check
reflects live reachability without touching tenant pools.
Returns 200 {"status":"ok","tidb":"connected"} or 503 on failure.
"""

from __future__ import annotations

import logging
from pathlib import Path
import asyncio

import aiomysql
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.config import TIDB_DB, TIDB_HOST, TIDB_PASS, TIDB_PORT, TIDB_USER

log = logging.getLogger("agentnexus.health")
router = APIRouter()

_INDEX = Path(__file__).parent.parent.parent / "index.html"


def _sync_health_check():
    """Synchronous health check using mysql-connector-python."""
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=TIDB_HOST,
            port=TIDB_PORT,
            user=TIDB_USER,
            password=TIDB_PASS,
            database=TIDB_DB,
            ssl_disabled=False,
            ssl_ca=None,
            connection_timeout=5,
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()  # Actually fetch the result
        cursor.close()
        conn.close()
        return True, None
    except Exception as exc:
        return False, str(exc)


@router.get("/")
async def index() -> FileResponse:
    return FileResponse(_INDEX, media_type="text/html")


@router.get("/health")
async def health() -> JSONResponse:
    try:
        # Use synchronous MySQL connector in thread pool to avoid Windows SSL issues
        loop = asyncio.get_event_loop()
        success, error = await loop.run_in_executor(None, _sync_health_check)
        
        if not success:
            log.error("Health probe failed: %s", error)
            return JSONResponse(
                status_code=503,
                content={"status": "degraded", "tidb": error},
            )
        
        return JSONResponse(content={"status": "ok", "tidb": "connected"})
        
    except Exception as exc:
        log.error("Health probe failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "tidb": str(exc)},
        )
