"""
AgentNexus — Qwen Optimization Report Generator
Connects to TiDB, runs TiFlash analytical query, sends results to Qwen,
prints a formatted optimization report and saves raw JSON output.
Dependencies: aiomysql, httpx  (stdlib: asyncio, json, os, datetime)
"""

import asyncio
import json
import os
from datetime import datetime, timezone

import httpx

from db import pool_manager

# ---------------------------------------------------------------------------
# Mock Qwen response used when DASHSCOPE_API_KEY is not set
# ---------------------------------------------------------------------------
MOCK_QWEN_RESPONSE = {
    "failure_patterns": [
        "api_call upstream timeouts (83% failure rate)",
        "code_exec memory exceeded on large datasets",
    ],
    "tool_optimizations": {
        "api_call": "Reduce timeout threshold from 10s to 3s, add circuit breaker",
        "code_exec": "Add memory limit of 512MB, stream results instead of batch",
    },
    "efficiency_score": 38,
    "top_3_recommendations": [
        "Implement exponential backoff for api_call tool (saves ~40% retry cost)",
        "Cache web_search results with 5min TTL (42% of queries are duplicates)",
        "Parallelize research agent steps 2+3 (currently sequential, saves 60% time)",
    ],
    "estimated_improvement_pct": 61,
}

# ---------------------------------------------------------------------------
# TiFlash analytical query (Query A from tiflash_query.sql)
# ---------------------------------------------------------------------------
TIFLASH_QUERY = """
SELECT /*+ READ_FROM_STORAGE(tiflash[agent_sessions, tool_call_history]) */
    s.agent_type,
    t.tool_name,
    t.status,
    COUNT(*)                                                                   AS total_calls,
    AVG(t.latency_ms)                                                          AS avg_latency_ms,
    MAX(t.latency_ms)                                                          AS max_latency_ms,
    SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END)                      AS failure_count,
    ROUND(
        SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    )                                                                          AS failure_rate_pct
FROM agent_sessions s
JOIN tool_call_history t
    ON  s.session_id = t.session_id
    AND s.tenant_id  = t.tenant_id
WHERE s.tenant_id  = %s
  AND s.created_at > NOW() - INTERVAL 24 HOUR
GROUP BY s.agent_type, t.tool_name, t.status
ORDER BY failure_count DESC
"""

SESSION_COUNT_QUERY = """
SELECT COUNT(*) AS cnt
FROM agent_sessions
WHERE tenant_id = %s
  AND created_at > NOW() - INTERVAL 24 HOUR
"""


async def fetch_query_data(tenant_id: str) -> tuple[list[dict], int]:
    """Run the TiFlash analytical query and return rows + session count."""
    rows = await pool_manager.execute(tenant_id, TIFLASH_QUERY, args=(tenant_id,))
    session_rows = await pool_manager.execute(tenant_id, SESSION_COUNT_QUERY, args=(tenant_id,))
    session_count = int(session_rows[0]["cnt"]) if session_rows else 0
    return rows, session_count


def build_summary(rows: list[dict], session_count: int, tenant_id: str) -> dict:
    """Format raw query rows into the structured summary for Qwen."""
    breakdown = []
    for row in rows:
        breakdown.append(
            {
                "agent_type": row["agent_type"],
                "tool_name": row["tool_name"],
                "status": row["status"],
                "total_calls": int(row["total_calls"]),
                "avg_latency_ms": round(float(row["avg_latency_ms"] or 0), 2),
                "max_latency_ms": int(row["max_latency_ms"] or 0),
                "failure_count": int(row["failure_count"]),
                "failure_rate_pct": float(row["failure_rate_pct"] or 0),
            }
        )

    critical_failures = [b for b in breakdown if b["failure_rate_pct"] > 50]

    highest_latency_tool = (
        max(breakdown, key=lambda x: x["avg_latency_ms"])["tool_name"]
        if breakdown
        else "N/A"
    )

    return {
        "tenant_id": tenant_id,
        "analysis_period": "last_24h",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_sessions": session_count,
        "agent_breakdown": breakdown,
        "critical_failures": critical_failures,
        "highest_latency_tool": highest_latency_tool,
    }


def call_qwen(summary: dict) -> dict:
    """
    POST to Qwen (DashScope) text-generation endpoint.
    Falls back to mock response if DASHSCOPE_API_KEY is unset.
    """
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("[INFO] DASHSCOPE_API_KEY not set — using mock Qwen response.\n")
        return MOCK_QWEN_RESPONSE

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    system_prompt = (
        "You are an AI agent orchestration optimizer for an enterprise SaaS platform. "
        "Analyze the agent execution data provided and return ONLY a valid JSON object "
        "with these exact keys:\n"
        "- failure_patterns: list of strings describing recurring failure causes\n"
        "- tool_optimizations: dict mapping tool_name to suggested improvement\n"
        "- efficiency_score: integer 0-100 representing overall tenant efficiency\n"
        "- top_3_recommendations: list of 3 actionable strings ranked by impact\n"
        "- estimated_improvement_pct: integer, expected efficiency gain if applied"
    )
    user_message = f"Analyze this execution data:\n{json.dumps(summary, indent=2)}"

    payload = {
        "model": "qwen-max",
        "input": {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
        },
        "parameters": {"result_format": "message"},
    }

    response = httpx.post(url, headers=headers, json=payload, timeout=60.0)
    response.raise_for_status()

    data = response.json()
    raw_text = data["output"]["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if Qwen wraps JSON in ```json ... ```
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    return json.loads(raw_text.strip())


def print_report(qwen: dict, tenant_id: str) -> None:
    """Print a formatted box report to stdout."""
    score = qwen.get("efficiency_score", "?")
    patterns = qwen.get("failure_patterns", [])
    recs = qwen.get("top_3_recommendations", [])
    opts = qwen.get("tool_optimizations", {})
    improvement = qwen.get("estimated_improvement_pct", "?")

    width = 55
    border = "─" * width

    def box_line(text: str = "") -> None:
        print(f"│  {text:<{width - 2}}│")

    print(f"┌{border}┐")
    box_line("AgentNexus — Qwen Optimization Report")
    box_line(f"Tenant: {tenant_id}  |  Score: {score}/100  |  Est. gain: +{improvement}%")
    print(f"├{border}┤")
    box_line("Failure Patterns:")
    for p in patterns:
        box_line(f"  • {p[:width - 6]}")
    print(f"├{border}┤")
    box_line("Tool Optimizations:")
    for tool, suggestion in opts.items():
        box_line(f"  [{tool}]")
        words = suggestion.split()
        line = "    "
        for word in words:
            if len(line) + len(word) + 1 > width - 4:
                box_line(line)
                line = "    " + word + " "
            else:
                line += word + " "
        if line.strip():
            box_line(line)
    print(f"├{border}┤")
    box_line("Top Recommendations:")
    for i, rec in enumerate(recs, 1):
        box_line(f"  {i}. {rec[:width - 7]}")
    print(f"└{border}┘")


def save_report(qwen: dict, summary: dict, path: str) -> None:
    """Save the full Qwen JSON response + summary context to a file."""
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": summary["tenant_id"],
        "analysis_summary": summary,
        "qwen_analysis": qwen,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, default=str)
    print(f"\n[INFO] Full report saved → {path}")


async def main() -> None:
    tenant_id = "ent-A"
    print("AgentNexus — connecting to TiDB …")
    try:
        print(f"Running TiFlash analytical query for tenant {tenant_id} …")
        rows, session_count = await fetch_query_data(tenant_id)
        print(f"  ↳ {len(rows)} result rows, {session_count} sessions in last 24h")
    finally:
        await pool_manager.close_all()

    summary = build_summary(rows, session_count, tenant_id)
    print("\nSending execution summary to Qwen for analysis …")
    qwen_result = call_qwen(summary)

    print()
    print_report(qwen_result, tenant_id=tenant_id)

    report_path = "qwen_report_ent_A.json"
    save_report(qwen_result, summary, report_path)


if __name__ == "__main__":
    asyncio.run(main())
