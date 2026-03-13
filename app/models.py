"""
app/models.py — Pydantic request models.

No local imports — safe to import from any route or test without
pulling in database or HTTP machinery.
"""

from __future__ import annotations

from typing import Any

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
