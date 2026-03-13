"""
app/routes/meta_agent.py — GET /api/v1/meta-agent/report

1. Queries TiFlash (columnar engine) for 24-hour execution stats.
2. Sends a compact summary to Qwen-Max for optimisation analysis.
3. Returns combined JSON with raw_stats + qwen_analysis.

Falls back to _MOCK_QWEN_ANALYSIS when DASHSCOPE_API_KEY is not set.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import DASHSCOPE_API_KEY
from app.context import ctx_tenant
from app.db import get_conn, release_conn

log = logging.getLogger("agentnexus.meta_agent")
router = APIRouter(prefix="/api/v1/meta-agent")

# ── Mock fallback — realistic enough to be useful during development ──────────

_MOCK_QWEN_ANALYSIS: dict[str, Any] = {
    "failure_patterns": [
        "web_search error rate exceeds 15 % after 22:00 UTC (external API timeouts)",
        "code_exec latency spikes when task_plan depth > 4 (recursive sub-tasks)",
        "db_query failures correlate with context payloads > 8 KB (query plan exhaustion)",
    ],
    "tool_optimizations": {
        "web_search": (
            "Add retry with exponential back-off (max 3 attempts, base 500 ms); "
            "cache identical queries for 5 min using a tenant-scoped Redis key"
        ),
        "code_exec": (
            "Cap task_plan.depth at 3; pre-warm sandbox containers during idle periods"
        ),
        "db_query": (
            "Enforce max context payload of 4 KB before issuing; "
            "route SELECT-only queries to a TiFlash replica"
        ),
        "file_read": "Stream large files in 64 KB chunks instead of buffering in memory",
        "api_call":  "Implement circuit breaker: 5 failures → 10-second open window",
    },
    "efficiency_score": 73,
    "top_3_recommendations": [
        "Parallelise independent tool calls within a session to cut average latency by ~22 %",
        "Checkpoint agent state every 5 tool calls to enable mid-session recovery without replay",
        "Route 'data' agent sessions to dedicated TiFlash replicas to eliminate OLTP contention",
    ],
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_qwen_text(raw: str) -> dict[str, Any]:
    """Strip optional markdown code fences and parse the JSON payload."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        inner = parts[1]
        if inner.lstrip().startswith("json"):
            inner = inner.lstrip()[4:]
        raw = inner.strip()
    return json.loads(raw)


async def _call_qwen(summary_str: str) -> dict[str, Any]:
    """
    POST the execution summary to Qwen-Max and return parsed JSON analysis.
    Returns _MOCK_QWEN_ANALYSIS on any HTTP or parse error.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://dashscope.aliyuncs.com/api/v1/services/"
                "aigc/text-generation/generation",
                headers={
                    "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model": "qwen-max",
                    "input": {
                        "messages": [
                            {
                                "role":    "system",
                                "content": (
                                    "You are an AI agent optimizer. "
                                    "Return ONLY valid JSON with keys: "
                                    "failure_patterns (list of strings), "
                                    "tool_optimizations (dict), "
                                    "efficiency_score (int 0-100), "
                                    "top_3_recommendations (list of strings)"
                                ),
                            },
                            {
                                "role":    "user",
                                "content": (
                                    "Analyze this agent execution data for tenant "
                                    f"and return optimization JSON:\n{summary_str}"
                                ),
                            },
                        ]
                    },
                },
            )

        if resp.status_code != 200:
            log.error("Qwen API HTTP %s: %s", resp.status_code, resp.text[:300])
            return _MOCK_QWEN_ANALYSIS

        # Qwen response: {"output": {"choices": [{"message": {"content": "..."}}]}}
        content_text: str = (
            resp.json()["output"]["choices"][0]["message"]["content"]
        )
        return _parse_qwen_text(content_text)

    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        log.error("Qwen call failed: %s", exc)
        return _MOCK_QWEN_ANALYSIS


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get("/report")
async def meta_agent_report() -> JSONResponse:
    tenant_id = ctx_tenant.get()

    conn = await get_conn(tenant_id)
    try:
        async with conn.cursor() as cur:
            # TiFlash hint pushes both tables to the columnar storage engine
            await cur.execute(
                """
                SELECT /*+ READ_FROM_STORAGE(tiflash[agent_sessions, tool_call_history]) */
                       s.agent_type,
                       t.tool_name,
                       t.status,
                       t.latency_ms,
                       COUNT(*) AS cnt
                FROM   agent_sessions s
                JOIN   tool_call_history t ON s.session_id = t.session_id
                WHERE  s.tenant_id  = %s
                  AND  s.created_at > NOW() - INTERVAL 24 HOUR
                GROUP  BY s.agent_type, t.tool_name, t.status, t.latency_ms
                """,
                (tenant_id,),
            )
            columns   = [d[0] for d in cur.description]
            raw_stats = [dict(zip(columns, row)) for row in await cur.fetchall()]
    finally:
        await release_conn(tenant_id, conn)

    summary_str = json.dumps(raw_stats, separators=(",", ":"))

    if not DASHSCOPE_API_KEY:
        log.warning("DASHSCOPE_API_KEY not set — returning mock Qwen analysis")
        qwen_analysis: dict[str, Any] = _MOCK_QWEN_ANALYSIS
    else:
        qwen_analysis = await _call_qwen(summary_str)

    return JSONResponse(content={
        "tenant_id":     tenant_id,
        "period":        "last_24h",
        "raw_stats":     raw_stats,
        "qwen_analysis": qwen_analysis,
    })
