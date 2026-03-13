#!/usr/bin/env bash
# =================================================================
# AgentNexus — Live Demo Script
# Demonstrates: multi-tenant agent lifecycle + isolation proof
#               + Qwen meta-agent optimization report
# Usage: bash demo_script.sh
# =================================================================
set -e

BASE_URL="http://localhost:8000"

# JWT tokens — replace with real tokens from your auth provider
JWT_A="${JWT_A:-eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlbnQtQSIsInN1YiI6ImRlbW8ifQ.placeholder_a}"
JWT_B="${JWT_B:-eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlbnQtQiIsInN1YiI6ImRlbW8ifQ.placeholder_b}"

echo ""
echo "================================================================="
echo "  AgentNexus — Live Demo"
echo "  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "================================================================="
echo ""

# -----------------------------------------------------------------
# Step 1 — Health check
# -----------------------------------------------------------------
echo ">>> STEP 1: Health check"
echo "    GET $BASE_URL/health"
curl --silent --show-error --fail \
     -w "\n    HTTP %{http_code} | %{time_total}s\n" \
     "$BASE_URL/health"
echo ""
sleep 1

# -----------------------------------------------------------------
# Step 2 — Launch a research agent for Tenant A
# -----------------------------------------------------------------
echo ">>> STEP 2: Launch research agent for Tenant A (ent-A)"
echo "    POST $BASE_URL/api/v1/agents/launch"
LAUNCH_RESPONSE=$(
  curl --silent --show-error --fail \
       -X POST "$BASE_URL/api/v1/agents/launch" \
       -H "X-Tenant-ID: ent-A" \
       -H "Authorization: Bearer $JWT_A" \
       -H "Content-Type: application/json" \
       -d '{
         "agent_type": "research",
         "task_plan": {
           "steps": ["search", "analyze", "report"],
           "priority": "high"
         },
         "context": {}
       }'
)
echo "    Response: $LAUNCH_RESPONSE"

# Extract session_id from JSON response  (requires jq or python fallback)
if command -v jq &>/dev/null; then
    SESSION_ID=$(echo "$LAUNCH_RESPONSE" | jq -r '.session_id')
else
    SESSION_ID=$(echo "$LAUNCH_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
fi
echo "    Captured SESSION_ID: $SESSION_ID"
echo ""
sleep 1

# -----------------------------------------------------------------
# Step 3 — Simulate a tool call (agent performing web search)
# -----------------------------------------------------------------
echo ">>> STEP 3: Simulate tool call — web_search (agent working)"
echo "    POST $BASE_URL/api/v1/agents/$SESSION_ID/tools/call"
curl --silent --show-error --fail \
     -X POST "$BASE_URL/api/v1/agents/$SESSION_ID/tools/call" \
     -H "X-Tenant-ID: ent-A" \
     -H "Authorization: Bearer $JWT_A" \
     -H "Content-Type: application/json" \
     -d '{
       "tool_name": "web_search",
       "input_params": {
         "query": "TiDB multi-tenant architecture"
       }
     }' | (command -v jq &>/dev/null && jq . || cat)
echo ""
sleep 1

# -----------------------------------------------------------------
# Step 4 — Get current agent state
# -----------------------------------------------------------------
echo ">>> STEP 4: Fetch agent state (Tenant A)"
echo "    GET $BASE_URL/api/v1/agents/$SESSION_ID/state"
curl --silent --show-error --fail \
     "$BASE_URL/api/v1/agents/$SESSION_ID/state" \
     -H "X-Tenant-ID: ent-A" \
     -H "Authorization: Bearer $JWT_A" \
     | (command -v jq &>/dev/null && jq . || cat)
echo ""
sleep 1

# -----------------------------------------------------------------
# Step 5 — ISOLATION PROOF
#          Tenant B attempts to access Tenant A's session
# -----------------------------------------------------------------
echo ">>> STEP 5: *** ISOLATION PROOF ***"
echo "=== ISOLATION PROOF: Tenant B tries to access Tenant A session ==="
echo "    GET $BASE_URL/api/v1/agents/$SESSION_ID/state  [X-Tenant-ID: ent-B]"
HTTP_STATUS=$(
  curl --silent \
       -o /dev/null \
       -w "%{http_code}" \
       "$BASE_URL/api/v1/agents/$SESSION_ID/state" \
       -H "X-Tenant-ID: ent-B" \
       -H "Authorization: Bearer $JWT_B"
)
echo ""
echo "HTTP STATUS: $HTTP_STATUS"
if [ "$HTTP_STATUS" = "404" ]; then
    echo "✓ Expected: 404 Not Found — ISOLATION CONFIRMED"
    echo "  Tenant B cannot see Tenant A's session — partition key enforced."
else
    echo "✗ WARNING: Expected 404 but got $HTTP_STATUS — check tenant isolation middleware!"
    exit 1
fi
echo ""
sleep 1

# -----------------------------------------------------------------
# Step 6 — Run Qwen meta-agent optimization report for Tenant A
# -----------------------------------------------------------------
echo ">>> STEP 6: Run Qwen meta-agent report for Tenant A"
echo "    GET $BASE_URL/api/v1/meta-agent/report"
curl --silent --show-error --fail \
     "$BASE_URL/api/v1/meta-agent/report" \
     -H "X-Tenant-ID: ent-A" \
     -H "Authorization: Bearer $JWT_A" \
     | (command -v jq &>/dev/null && jq . || cat)
echo ""

# -----------------------------------------------------------------
# Done
# -----------------------------------------------------------------
echo "================================================================="
echo "✓ Demo complete. AgentNexus isolation + Qwen AI verified."
echo "================================================================="
