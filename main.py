"""
main.py — Entry point for AgentNexus.

Imports the wired FastAPI instance from app.app and starts Uvicorn.
This file intentionally contains no application logic.
"""

import uvicorn
from app.app import app

# ---------------------------------------------------------------------------
# Curl Test Commands
# ---------------------------------------------------------------------------

"""
====================================================================
 CURL TEST COMMANDS — AgentNexus API
====================================================================

 PRE-REQUISITE: generate HS256 test tokens (Python one-liner)
 ─────────────────────────────────────────────────────────────────
 python -c "
 from jose import jwt
 SECRET = 'changeme-set-a-real-secret'
 print('TOKEN_A:', jwt.encode({'tid':'enterprise-A'}, SECRET, algorithm='HS256'))
 print('TOKEN_B:', jwt.encode({'tid':'enterprise-B'}, SECRET, algorithm='HS256'))
 "

 Export in your shell:
   export TOKEN_A="<value above>"
   export TOKEN_B="<value above>"
   export BASE="http://localhost:8000"

====================================================================
 1. HEALTH CHECK  (no auth required)
====================================================================
curl -s "$BASE/health" | jq .
# → {"status":"ok","tidb":"connected"}

====================================================================
 2. LAUNCH AGENT — enterprise-A
====================================================================
curl -s -X POST "$BASE/api/v1/agents/launch" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: enterprise-A" \
  -H "Authorization: Bearer $TOKEN_A" \
  -d '{
    "agent_type": "research",
    "task_plan":  {"topic": "quantum error correction", "depth": 3},
    "context":    {"user_id": "u-001", "priority": "high"}
  }' | jq .
# → {"session_id":"<uuid>","tenant_id":"enterprise-A","status":"planning","created_at":"..."}
# export SESSION_A="<uuid from above>"

====================================================================
 3. CALL TOOL — enterprise-A
====================================================================
curl -s -X POST "$BASE/api/v1/agents/$SESSION_A/tools/call" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: enterprise-A" \
  -H "Authorization: Bearer $TOKEN_A" \
  -d '{
    "tool_name":    "web_search",
    "input_params": {"query": "quantum error correction 2025", "limit": 5}
  }' | jq .
# → {"call_id":"<uuid>","tool_name":"web_search","status":"success","latency_ms":50}

====================================================================
 4. GET AGENT STATE — enterprise-A (full session + recent tool calls)
====================================================================
curl -s "$BASE/api/v1/agents/$SESSION_A/state" \
  -H "X-Tenant-ID: enterprise-A" \
  -H "Authorization: Bearer $TOKEN_A" | jq .
# → {"session":{...},"recent_tool_calls":[...]}

====================================================================
 5. META-AGENT REPORT — enterprise-A
====================================================================
curl -s "$BASE/api/v1/meta-agent/report" \
  -H "X-Tenant-ID: enterprise-A" \
  -H "Authorization: Bearer $TOKEN_A" | jq .
# → {"tenant_id":"enterprise-A","period":"last_24h","raw_stats":[...],"qwen_analysis":{...}}

====================================================================
 TENANT ISOLATION PROOF — enterprise-B vs enterprise-A data
====================================================================

 — GET STATE: valid TOKEN_B + enterprise-A's session_id → 404
curl -s "$BASE/api/v1/agents/$SESSION_A/state" \
  -H "X-Tenant-ID: enterprise-B" \
  -H "Authorization: Bearer $TOKEN_B" | jq .
# EXPECTED HTTP 404
# {"detail":{"error":"not_found","detail":"session not found for this tenant"}}

 — TOOL CALL: enterprise-B writing into enterprise-A's session
curl -s -X POST "$BASE/api/v1/agents/$SESSION_A/tools/call" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: enterprise-B" \
  -H "Authorization: Bearer $TOKEN_B" \
  -d '{"tool_name":"db_query","input_params":{"sql":"SELECT 1"}}' | jq .
# Row written under enterprise-B's tenant_id — invisible to enterprise-A

 — MISMATCH: TOKEN_A header claims enterprise-B → 401
curl -s -X POST "$BASE/api/v1/agents/launch" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: enterprise-B" \
  -H "Authorization: Bearer $TOKEN_A" \
  -d '{"agent_type":"web","task_plan":{},"context":{}}' | jq .
# EXPECTED HTTP 401
# {"error":"unauthorized","code":"TENANT_MISMATCH"}

 — MISMATCH: TOKEN_B header claims enterprise-A → 401
curl -s "$BASE/api/v1/agents/$SESSION_A/state" \
  -H "X-Tenant-ID: enterprise-A" \
  -H "Authorization: Bearer $TOKEN_B" | jq .
# EXPECTED HTTP 401
# {"error":"unauthorized","code":"TENANT_MISMATCH"}

====================================================================
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
