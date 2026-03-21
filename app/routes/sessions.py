"""
app/routes/sessions.py — Legacy compatibility endpoint.

POST /api/{tenant_id}/sessions

This provides a lightweight compatibility route for older clients that
address tenant in the path. It validates the authenticated tenant
from `ctx_tenant` and then creates an `agent_sessions` row (same as
`/api/v1/agents/launch`).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.context import ctx_tenant
from app.db import get_conn, release_conn
from app.models import LaunchAgentRequest

router = APIRouter(prefix="/api")


@router.post("/{tenant_id}/sessions", status_code=201)
async def create_session(tenant_id: str, body: LaunchAgentRequest) -> JSONResponse:
    """Create a new session for the given tenant (legacy path-style API).

    Validates that the request's authenticated tenant (from middleware)
    matches the path `tenant_id` to avoid cross-tenant surprises.
    """
    auth_tenant = ctx_tenant.get()
    if auth_tenant != tenant_id:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "code": "TENANT_MISMATCH"})

    session_id = str(uuid.uuid4())

    conn = await get_conn(tenant_id)
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO agent_sessions
                    (session_id, tenant_id, agent_type, status, task_plan, context)
                VALUES (%s, %s, %s, 'planning', %s, %s)
                """,
                (
                    session_id,
                    tenant_id,
                    body.agent_type,
                    json.dumps(body.task_plan),
                    json.dumps(body.context),
                ),
            )
            await cur.execute(
                "SELECT created_at FROM agent_sessions WHERE session_id = %s AND tenant_id = %s",
                (session_id, tenant_id),
            )
            row = await cur.fetchone()
            created_at: str = (
                row[0].isoformat() if (row and row[0]) else datetime.now(timezone.utc).isoformat()
            )
    finally:
        await release_conn(tenant_id, conn)

    return JSONResponse(
        status_code=201,
        content={
            "session_id": session_id,
            "tenant_id": tenant_id,
            "status": "planning",
            "created_at": created_at,
        },
    )
