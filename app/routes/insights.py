from __future__ import annotations

"""
app/routes/insights.py — GET /api/{tenant_id}/insights

Provides tenant-specific insights and analytics.
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.context import ctx_tenant
from app.db import get_conn, release_conn

log = logging.getLogger("agentnexus.insights")
router = APIRouter()


@router.get("/api/{tenant_id}/insights")
async def get_tenant_insights(tenant_id: str) -> JSONResponse:
    """
    Get insights and analytics for a specific tenant.
    
    Args:
        tenant_id: The tenant identifier
        
    Returns:
        JSON response with tenant insights including:
        - Session statistics
        - Tool usage patterns
        - Performance metrics
        - Error analysis
    """
    # Validate tenant matches context
    current_tenant = ctx_tenant.get()
    if tenant_id != current_tenant:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "code": "TENANT_MISMATCH",
                "message": f"Tenant {tenant_id} does not match authenticated tenant {current_tenant}"
            }
        )
    
    conn = await get_conn(tenant_id)
    try:
        async with conn.cursor() as cur:
            # Get session statistics
            await cur.execute(
                """
                SELECT 
                    COUNT(*) as total_sessions,
                    COUNT(DISTINCT agent_type) as unique_agent_types,
                    AVG(TIMESTAMPDIFF(SECOND, created_at, COALESCE(updated_at, NOW()))) as avg_session_duration_sec,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_sessions,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_sessions
                FROM agent_sessions 
                WHERE tenant_id = %s 
                AND created_at > NOW() - INTERVAL 24 HOUR
                """,
                (tenant_id,)
            )
            session_stats = dict(zip([d[0] for d in cur.description], await cur.fetchone()))
            
            # Get agent performance by type
            await cur.execute(
                """
                SELECT 
                    agent_type,
                    COUNT(*) as session_count,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
                    AVG(TIMESTAMPDIFF(SECOND, created_at, COALESCE(updated_at, NOW()))) as avg_duration_sec
                FROM agent_sessions 
                WHERE tenant_id = %s 
                AND created_at > NOW() - INTERVAL 24 HOUR
                GROUP BY agent_type
                ORDER BY session_count DESC
                """,
                (tenant_id,)
            )
            agent_performance = [dict(zip([d[0] for d in cur.description], row)) for row in await cur.fetchall()]
            
            # Get tool usage patterns
            await cur.execute(
                """
                SELECT 
                    tool_name,
                    COUNT(*) as call_count,
                    AVG(latency_ms) as avg_latency_ms,
                    COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failure_count
                FROM tool_call_history t
                JOIN agent_sessions s ON t.session_id = s.session_id
                WHERE s.tenant_id = %s 
                AND s.created_at > NOW() - INTERVAL 24 HOUR
                GROUP BY tool_name
                ORDER BY call_count DESC
                """,
                (tenant_id,)
            )
            tool_stats = [dict(zip([d[0] for d in cur.description], row)) for row in await cur.fetchall()]
            
            # Get daily sessions trend (last 7 days)
            await cur.execute(
                """
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as session_count,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count
                FROM agent_sessions 
                WHERE tenant_id = %s 
                AND created_at > NOW() - INTERVAL 7 DAY
                GROUP BY DATE(created_at)
                ORDER BY date ASC
                """,
                (tenant_id,)
            )
            daily_trend = [dict(zip([d[0] for d in cur.description], row)) for row in await cur.fetchall()]
            
            # Get error patterns
            await cur.execute(
                """
                SELECT 
                    error_type,
                    COUNT(*) as error_count,
                    MAX(created_at) as last_occurrence
                FROM agent_sessions 
                WHERE tenant_id = %s 
                AND status = 'failed'
                AND created_at > NOW() - INTERVAL 24 HOUR
                GROUP BY error_type
                ORDER BY error_count DESC
                LIMIT 5
                """,
                (tenant_id,)
            )
            error_patterns = [dict(zip([d[0] for d in cur.description], row)) for row in await cur.fetchall()]
            
    finally:
        await release_conn(tenant_id, conn)
    
    # Calculate derived metrics
    total_calls = sum(stat['call_count'] for stat in tool_stats)
    success_rate = (sum(stat['success_count'] for stat in tool_stats) / total_calls * 100) if total_calls > 0 else 0
    
    insights = {
        "tenant_id": tenant_id,
        "period": "last_24h",
        "session_statistics": {
            "total_sessions": session_stats['total_sessions'],
            "unique_agent_types": session_stats['unique_agent_types'],
            "avg_session_duration_sec": round(session_stats['avg_session_duration_sec'] or 0, 2),
            "completion_rate": round((session_stats['completed_sessions'] / session_stats['total_sessions'] * 100) if session_stats['total_sessions'] > 0 else 0, 2),
            "completed_sessions": session_stats['completed_sessions'],
            "failed_sessions": session_stats['failed_sessions']
        },
        "agent_performance_by_type": agent_performance,
        "tool_usage": {
            "total_calls": total_calls,
            "overall_success_rate": round(success_rate, 2),
            "tool_breakdown": tool_stats
        },
        "daily_sessions_trend": daily_trend,
        "error_analysis": {
            "total_errors": session_stats['failed_sessions'],
            "error_patterns": error_patterns
        },
        "performance_metrics": {
            "avg_tool_latency_ms": round(sum(stat['avg_latency_ms'] * stat['call_count'] for stat in tool_stats) / total_calls, 2) if total_calls > 0 else 0
        }
    }
    
    return JSONResponse(content=insights)
