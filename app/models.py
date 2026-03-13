"""
app/models.py — Pydantic request models.

No local imports — safe to import from any route or test without
pulling in database or HTTP machinery.
"""

from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel, field_validator

_VALID_AGENT_TYPES = frozenset({"research", "codegen", "data", "web"})
_VALID_TOOLS       = frozenset({"web_search", "code_exec", "db_query", "file_read", "api_call"})


class LaunchAgentRequest(BaseModel):
    agent_type: str
    task_plan:  dict[str, Any]
    context:    dict[str, Any]

    @field_validator("agent_type")
    @classmethod
    def _check_agent_type(cls, v: str) -> str:
        if v not in _VALID_AGENT_TYPES:
            raise ValueError(f"agent_type must be one of {sorted(_VALID_AGENT_TYPES)}")
        return v


class ToolCallRequest(BaseModel):
    tool_name:    str
    input_params: dict[str, Any]

    @field_validator("tool_name")
    @classmethod
    def _check_tool_name(cls, v: str) -> str:
        if v not in _VALID_TOOLS:
            raise ValueError(f"tool_name must be one of {sorted(_VALID_TOOLS)}")
        return v


class ToolUsageStats(BaseModel):
    tool_name: str
    call_count: int
    avg_latency_ms: float
    success_count: int
    failure_count: int


class ErrorPattern(BaseModel):
    error_type: str
    error_count: int
    last_occurrence: str


class SessionStatistics(BaseModel):
    total_sessions: int
    unique_agent_types: int
    avg_session_duration_sec: float
    completion_rate: float
    completed_sessions: int
    failed_sessions: int


class ToolUsage(BaseModel):
    total_calls: int
    overall_success_rate: float
    tool_breakdown: List[ToolUsageStats]


class ErrorAnalysis(BaseModel):
    total_errors: int
    error_patterns: List[ErrorPattern]


class PerformanceMetrics(BaseModel):
    avg_tool_latency_ms: float


class InsightsResponse(BaseModel):
    tenant_id: str
    period: str
    session_statistics: SessionStatistics
    tool_usage: ToolUsage
    error_analysis: ErrorAnalysis
    performance_metrics: PerformanceMetrics
