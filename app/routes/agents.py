"""
app/routes/agents.py — Core agent endpoints.

POST /api/v1/agents/launch
POST /api/v1/agents/{session_id}/tools/call
GET  /api/v1/agents/{session_id}/state

tenant_id is sourced exclusively from ctx_tenant.get() — never from the
request body or path parameters.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import aiomysql
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.context import ctx_tenant
from app.db import get_conn, release_conn
from app.models import LaunchAgentRequest, ToolCallRequest

router = APIRouter(prefix="/api/v1/agents")


# ── POST /api/v1/agents/launch ────────────────────────────────────────────────

@router.post("/launch", status_code=201)
async def launch_agent(body: LaunchAgentRequest) -> JSONResponse:
    """
    Create a new agent session.
    Inserts into agent_sessions and returns the server-generated created_at.
    """
    tenant_id  = ctx_tenant.get()
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
                "SELECT created_at FROM agent_sessions "
                "WHERE session_id = %s AND tenant_id = %s",
                (session_id, tenant_id),
            )
            row = await cur.fetchone()
            created_at: str = (
                row[0].isoformat()
                if (row and row[0])
                else datetime.now(timezone.utc).isoformat()
            )
    finally:
        await release_conn(tenant_id, conn)

    return JSONResponse(
        status_code=201,
        content={
            "session_id": session_id,
            "tenant_id":  tenant_id,
            "status":     "planning",
            "created_at": created_at,
        },
    )


# ── POST /api/v1/agents/{session_id}/tools/call ───────────────────────────────

@router.post("/{session_id}/tools/call")
async def call_tool(session_id: str, body: ToolCallRequest) -> JSONResponse:
    """
    Record a tool invocation, simulate 50 ms execution, persist the result.
    Both INSERT and UPDATE are scoped to the authenticated tenant.
    """
    tenant_id = ctx_tenant.get()
    call_id   = str(uuid.uuid4())

    conn = await get_conn(tenant_id)
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO tool_call_history
                    (call_id, session_id, tenant_id, tool_name,
                     input_params, status, called_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', NOW(3))
                """,
                (call_id, session_id, tenant_id, body.tool_name,
                 json.dumps(body.input_params)),
            )

        # Simulate tool execution — timing wraps the sleep for accuracy
        t_start = time.monotonic()
        await asyncio.sleep(0.05)
        latency_ms    = int((time.monotonic() - t_start) * 1000)
        output_result = {"simulated": True}

        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE tool_call_history
                SET    status        = 'success',
                       output_result = %s,
                       latency_ms    = %s
                WHERE  call_id   = %s
                  AND  tenant_id = %s
                """,
                (json.dumps(output_result), latency_ms, call_id, tenant_id),
            )
    finally:
        await release_conn(tenant_id, conn)

    return JSONResponse(content={
        "call_id":    call_id,
        "tool_name":  body.tool_name,
        "status":     "success",
        "latency_ms": latency_ms,
    })


# ── GET /api/v1/agents ───────────────────────────────────────────────────────

@router.get("/")
async def get_all_agents() -> JSONResponse:
    """
    Return all agent sessions for the current tenant.
    Results are ordered by creation date (newest first).
    """
    tenant_id = ctx_tenant.get()

    conn = await get_conn(tenant_id)
    try:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT session_id, agent_type, status, created_at, updated_at
                FROM   agent_sessions
                WHERE  tenant_id = %s
                ORDER  BY created_at DESC
                """,
                (tenant_id,),
            )
            agent_rows = await cur.fetchall()
    finally:
        await release_conn(tenant_id, conn)

    agents: list[dict[str, Any]] = []
    for row in agent_rows:
        agent = dict(row)
        if isinstance(agent.get("created_at"), datetime):
            agent["created_at"] = agent["created_at"].isoformat()
        if isinstance(agent.get("updated_at"), datetime):
            agent["updated_at"] = agent["updated_at"].isoformat()
        agents.append(agent)

    return JSONResponse(content={
        "agents": agents,
        "count": len(agents),
    })


# ── GET /api/v1/agents/{session_id}/state ────────────────────────────────────

@router.get("/{session_id}/state")
async def get_agent_state(session_id: str) -> JSONResponse:
    """
    Return session data + last 5 tool calls.
    Both queries filter on tenant_id = ctx_tenant — cross-tenant access
    returns 404 (not a security leak, not a 403).
    """
    tenant_id = ctx_tenant.get()

    conn = await get_conn(tenant_id)
    try:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT session_id, tenant_id, agent_type, status,
                       task_plan, context, created_at
                FROM   agent_sessions
                WHERE  session_id = %s AND tenant_id = %s
                """,
                (session_id, tenant_id),
            )
            session_row = await cur.fetchone()

        if session_row is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found",
                        "detail": "session not found for this tenant"},
            )

        session_data: dict[str, Any] = dict(session_row)
        if isinstance(session_data.get("created_at"), datetime):
            session_data["created_at"] = session_data["created_at"].isoformat()
        for field in ("task_plan", "context"):
            val = session_data.get(field)
            if isinstance(val, str):
                session_data[field] = json.loads(val)

        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT call_id, tool_name, input_params, output_result,
                       status, latency_ms, called_at
                FROM   tool_call_history
                WHERE  session_id = %s AND tenant_id = %s
                ORDER  BY called_at DESC
                LIMIT  5
                """,
                (session_id, tenant_id),
            )
            tool_rows = await cur.fetchall()
    finally:
        await release_conn(tenant_id, conn)

    recent_tool_calls: list[dict[str, Any]] = []
    for row in tool_rows:
        r = dict(row)
        if isinstance(r.get("called_at"), datetime):
            r["called_at"] = r["called_at"].isoformat()
        for field in ("input_params", "output_result"):
            if isinstance(r.get(field), str):
                r[field] = json.loads(r[field])
        recent_tool_calls.append(r)

    return JSONResponse(content={
        "session":           session_data,
        "recent_tool_calls": recent_tool_calls,
    })
