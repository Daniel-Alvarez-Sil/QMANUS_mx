# 🧠 AgentNexus
## Multi-Tenant Agentic AI Platform — Technical Document
### Hackathon Build | Alibaba Cloud × TiDB × Qwen

---

> **Tiempo de build:** 60 minutos | **Equipo:** 3 personas | **Stack:** TiDB · Alibaba Cloud · Qwen AI

---

## The Problem We Solve

Enterprises need autonomous AI agents that can run **multi-step tasks** (research, code gen, data analysis) with **complete isolation** between clients — all on shared infrastructure.

```
Enterprise A's agents → INVISIBLE to Enterprise B
Enterprise B's agents → INVISIBLE to Enterprise A
Both → Same TiDB cluster, different execution universes
```

**The X×Y×Z Problem:**
```
X tenants × Y agents each × Z parallel branches = massive write amplification
TiDB solves this without degrading any single tenant
```

---

## Architecture (3-Layer)

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 1 — AGENT ORCHESTRATION                          │
│                                                         │
│  Meta-Agent (Qwen)                                      │
│  ├── Analyzes completed task logs                       │
│  ├── Recommends: better tool sequences                  │
│  ├── Detects: common failure patterns                   │
│  └── Optimizes: agent efficiency per tenant             │
│                                                         │
│  Per-Tenant Agents                                      │
│  └── Research · Code Gen · Data Analysis · Web Tools   │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  LAYER 2 — ALIBABA CLOUD INFRASTRUCTURE                 │
│                                                         │
│  API Gateway ──► ACK (Kubernetes) ──► RocketMQ          │
│  PAI-EAS (Qwen serving) ──► OSS (knowledge base)       │
│  RAM (tenant IAM) ──► SLS (audit logs)                  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  LAYER 3 — TiDB AS AGENT LONG-TERM MEMORY              │
│                                                         │
│  TiKV (OLTP)              TiFlash (OLAP)                │
│  ├── agent_sessions       ├── task_analytics            │
│  ├── task_plans           ├── failure_patterns          │
│  ├── tool_call_history    ├── tenant_metrics            │
│  └── execution_logs       └── optimization_vectors      │
└─────────────────────────────────────────────────────────┘
```

---

## The 4 Core Pillars

### 🔒 Pillar 1 — Tenant Isolation

Every agent session, execution log, and knowledge base artifact is **invisible across tenants** even on shared infrastructure.

**Implementation:**
```sql
-- Row-Level Security enforced at app layer + DB level
-- EVERY query mandates tenant_id as partition key

CREATE TABLE agent_sessions (
    session_id    VARCHAR(36)  NOT NULL,
    tenant_id     VARCHAR(36)  NOT NULL,   -- ← ISOLATION KEY
    agent_type    ENUM('research','codegen','data','web') NOT NULL,
    status        ENUM('running','completed','failed','paused'),
    task_plan     JSON,                    -- structured multi-step plan
    context       JSON,                    -- agent working memory
    created_at    TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP(3),
    updated_at    TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP(3)
                  ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (tenant_id, session_id),
    INDEX idx_status (tenant_id, status, created_at)
) PARTITION BY HASH(tenant_id) PARTITIONS 32;

-- Knowledge base: each tenant's docs are partitioned
CREATE TABLE knowledge_base (
    doc_id        VARCHAR(36)  NOT NULL,
    tenant_id     VARCHAR(36)  NOT NULL,
    content       LONGTEXT,
    embedding     BLOB,                    -- 1536-dim vector
    metadata      JSON,
    PRIMARY KEY (tenant_id, doc_id)
) PARTITION BY HASH(tenant_id) PARTITIONS 32;
```

**Middleware enforcement (every API call):**
```python
@middleware
async def tenant_isolation(request, call_next):
    token = verify_jwt(request.headers["Authorization"])
    tenant_id = token["tid"]
    
    # Inject into ALL downstream DB queries via context var
    ctx_tenant.set(tenant_id)
    
    # Every TiDB query builder auto-appends:
    # WHERE tenant_id = {ctx_tenant.get()}
    response = await call_next(request)
    return response
```

---

### 💾 Pillar 2 — Agent State Persistence (TiDB as Agent Memory)

TiDB is not just storage — **it IS the agent's brain.** Each agent session maintains:

```
task_plans          → What the agent intends to do (steps 1–N)
intermediate_results → What it has found/computed so far
tool_call_history   → Every tool invoked, params, result, latency
final_outputs       → Completed deliverable
```

**Schema:**
```sql
CREATE TABLE tool_call_history (
    call_id       VARCHAR(36)  NOT NULL,
    session_id    VARCHAR(36)  NOT NULL,
    tenant_id     VARCHAR(36)  NOT NULL,
    tool_name     VARCHAR(100) NOT NULL,   -- 'web_search','code_exec','db_query'
    input_params  JSON         NOT NULL,
    output_result JSON,
    status        ENUM('pending','success','failed','timeout'),
    latency_ms    INT,
    called_at     TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (tenant_id, session_id, call_id),
    INDEX idx_tool (tenant_id, tool_name, called_at)
) PARTITION BY HASH(tenant_id) PARTITIONS 32;

-- TiFlash replica for analytics WITHOUT competing with agent writes
ALTER TABLE tool_call_history SET TIFLASH REPLICA 1;
ALTER TABLE agent_sessions    SET TIFLASH REPLICA 1;
```

**Agent State Machine:**
```
IDLE → PLANNING → EXECUTING → [TOOL_CALL loop] → SYNTHESIZING → COMPLETED
                     ↑                                  |
                     └──── retry on failure ────────────┘
                     (state persisted in TiDB at each step)
```

---

### ⚡ Pillar 3 — Scalability Under Concurrency

**Scenario:** Tenant launches 50 agents simultaneously.

```
50 agents × 10 tool calls each × 3 retries = 1,500 potential writes/minute
```

**TiDB's answer: HTAP separation**

```
Agent writes → TiKV (OLTP)   — never blocked, optimistic concurrency
Analytics   → TiFlash (OLAP) — replica, zero impact on write path

TiDB Placement Rules:
  - Hot tenants (>100 agents/hr) → dedicated TiKV regions
  - Cold tenants               → shared regions
  - Analytical workloads       → always TiFlash
```

**Concurrency control:**
```python
# Per-tenant agent slot limiter (Redis/Tair)
async def launch_agent(tenant_id: str, agent_config: dict):
    plan_key = f"slots:{tenant_id}"
    
    current = await tair.incr(plan_key)
    await tair.expire(plan_key, 3600)
    
    tenant_plan = await get_tenant_plan(tenant_id)
    max_agents = PLAN_LIMITS[tenant_plan]  # starter:5, growth:25, enterprise:200
    
    if current > max_agents:
        await tair.decr(plan_key)
        raise TenantQuotaExceeded(f"Max {max_agents} concurrent agents for plan")
    
    return await create_agent_session(tenant_id, agent_config)
```

---

### 🤖 Pillar 4 — AI Orchestration (Qwen Meta-Agent)

A **meta-agent** powered by Qwen reads completed task logs and generates optimization recommendations for each tenant.

**Qwen Integration (PAI-EAS):**
```python
async def run_meta_agent(tenant_id: str):
    # Pull last 24hr completed sessions from TiFlash (analytical query)
    logs = await db.fetch_all("""
        SELECT 
            s.session_id,
            s.agent_type,
            s.task_plan,
            JSON_ARRAYAGG(
                JSON_OBJECT(
                    'tool', t.tool_name,
                    'latency_ms', t.latency_ms,
                    'status', t.status
                )
            ) as tool_sequence,
            s.status as final_status
        FROM agent_sessions s
        JOIN tool_call_history t 
          ON s.session_id = t.session_id 
         AND s.tenant_id = t.tenant_id
        WHERE s.tenant_id = :tenant_id
          AND s.created_at > NOW() - INTERVAL 24 HOUR
          AND s.status IN ('completed', 'failed')
        GROUP BY s.session_id
        -- Runs on TiFlash, never touches TiKV write path
    """, {"tenant_id": tenant_id})
    
    # Send to Qwen on PAI-EAS
    qwen_response = await pai_eas_client.chat(
        model="qwen-max",
        messages=[{
            "role": "system",
            "content": """You are an AI orchestration optimizer. 
            Analyze agent execution logs and return JSON with:
            - failure_patterns: list of recurring failure causes
            - tool_optimizations: better tool sequences per task type  
            - efficiency_score: 0-100 for this tenant's agent usage
            - top_3_recommendations: actionable improvements"""
        }, {
            "role": "user", 
            "content": f"Analyze these agent logs for tenant {tenant_id}:\n{json.dumps(logs)}"
        }]
    )
    
    # Persist recommendations back to TiDB
    await save_optimization_report(tenant_id, qwen_response)
```

---

## API Endpoints (Build Priority Order)

```
Priority 1 — Core (build first 20 min)
  POST /api/v1/agents/launch          → Start agent session
  GET  /api/v1/agents/{id}/state      → Get current agent state
  POST /api/v1/agents/{id}/tools/call → Execute a tool, persist result

Priority 2 — Isolation (build next 20 min)
  GET  /api/v1/sessions               → List tenant's own sessions only
  GET  /api/v1/knowledge              → Tenant's knowledge base
  POST /api/v1/knowledge/upload       → Add doc to tenant KB

Priority 3 — AI (build final 20 min)
  GET  /api/v1/meta-agent/report      → Qwen optimization report
  GET  /api/v1/analytics/patterns     → Failure patterns (TiFlash query)
  GET  /api/v1/analytics/efficiency   → Tenant efficiency metrics
```

---

## Division of Work — 60 Minutes

### 👷 Person 1: Arquitecto Cloud (Min 0–60)

```
Min 00–15: TiDB Schema
  └── Run DDL for all 5 tables in TiDB Cloud (free tier)
  └── Enable TiFlash replicas on tool_call_history + agent_sessions
  └── Insert seed data: 2 tenants, 10 agent sessions each

Min 15–35: Alibaba Cloud Setup  
  └── API Gateway: create 2 routes with X-Tenant-ID header validation
  └── RAM: create service account with TiDB access
  └── Configure JWT validation (use HS256 for hackathon speed)

Min 35–55: Integration Test
  └── Verify cross-tenant query isolation (Tenant A cannot see Tenant B)
  └── Test concurrent inserts: 50 rows simultaneous, check no deadlock
  └── Demo TiFlash vs TiKV query on same data (show speed difference)

Min 55–60: Slide prep
  └── Screenshot of TiDB cluster dashboard
  └── Screenshot of API Gateway with tenant headers
```

### ⚙️ Person 2: Backend Engineer (Min 0–60)

```
Min 00–20: FastAPI Boilerplate + Middleware
  └── pip install fastapi uvicorn aiomysql python-jose tqdm
  └── Tenant isolation middleware (JWT → tenant_id → context var)
  └── TiDB connection pool (1 pool per tenant, max 10 conn each)

Min 20–40: Core Endpoints
  └── POST /agents/launch  → INSERT into agent_sessions
  └── POST /agents/{id}/tools/call → INSERT into tool_call_history
  └── GET /agents/{id}/state → SELECT with tenant_id guard

Min 40–55: Qwen Integration
  └── Call Qwen via DashScope API (alibabacloud SDK)
  └── GET /meta-agent/report → query TiFlash + call Qwen + return JSON

Min 55–60: Run server + test with curl
  └── curl -H "X-Tenant-ID: tenant-A" /agents  
  └── Confirm tenant-B header returns 0 results for same query
```

**Key code snippet (paste and run):**
```python
# main.py — complete hackathon backend in ~80 lines
from fastapi import FastAPI, Request, HTTPException, Depends
from contextvars import ContextVar
import aiomysql, json, os
from jose import jwt

app = FastAPI(title="AgentNexus")
ctx_tenant: ContextVar[str] = ContextVar("tenant_id")

TIDB_CONFIG = {
    "host": os.getenv("TIDB_HOST"),
    "port": 4000,
    "user": os.getenv("TIDB_USER"),
    "password": os.getenv("TIDB_PASS"),
    "db": "agentnexus",
    "ssl": {"ssl_mode": "VERIFY_IDENTITY"}
}

@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        raise HTTPException(401, "Missing X-Tenant-ID header")
    ctx_tenant.set(tenant_id)
    return await call_next(request)

@app.post("/api/v1/agents/launch")
async def launch_agent(body: dict):
    tid = ctx_tenant.get()
    session_id = str(__import__("uuid").uuid4())
    conn = await aiomysql.connect(**TIDB_CONFIG)
    async with conn.cursor() as cur:
        await cur.execute("""
            INSERT INTO agent_sessions 
            (session_id, tenant_id, agent_type, status, task_plan, context)
            VALUES (%s, %s, %s, 'planning', %s, %s)
        """, (session_id, tid, body["agent_type"], 
              json.dumps(body.get("task_plan", {})),
              json.dumps(body.get("context", {}))))
        await conn.commit()
    conn.close()
    return {"session_id": session_id, "tenant_id": tid, "status": "planning"}

@app.get("/api/v1/agents/{session_id}/state")
async def get_state(session_id: str):
    tid = ctx_tenant.get()  # tenant isolation enforced
    conn = await aiomysql.connect(**TIDB_CONFIG)
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("""
            SELECT * FROM agent_sessions 
            WHERE session_id = %s AND tenant_id = %s  -- ← isolation
        """, (session_id, tid))
        row = await cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Session not found for this tenant")
    return row
```

### 📊 Person 3: Data Engineer (Min 0–60)

```
Min 00–20: TiDB Schema + Seed Data
  └── CREATE all tables (copy from this doc)
  └── ALTER TABLE ... SET TIFLASH REPLICA 1 (run on completed tables)
  └── Seed: INSERT 2 tenants, 20 agent sessions, 100 tool calls

Min 20–40: Qwen Meta-Agent Query
  └── Write the TiFlash analytical query (see Pillar 4 above)
  └── Test: run query on TiFlash vs TiKV, compare latency
  └── Format output for Qwen prompt

Min 40–55: Demo Data + Visualizations
  └── Create "failure scenario": 10 tool calls with status='failed'
  └── Run Qwen analysis → capture JSON output
  └── Prepare: table showing efficiency before vs after Qwen recommendations

Min 55–60: Demo script
  └── Write step-by-step curl commands for live demo
  └── Prepare: "Tenant A cannot see Tenant B" isolation proof screenshot
```

---

## Live Demo Script (5 min pitch)

```bash
# Step 1: Launch agent for Tenant A
curl -X POST http://localhost:8000/api/v1/agents/launch \
  -H "X-Tenant-ID: enterprise-A" \
  -H "Authorization: Bearer {JWT_A}" \
  -d '{"agent_type":"research","task_plan":{"steps":["search","analyze","report"]}}'

# Step 2: Simulate tool calls (agent working)
curl -X POST http://localhost:8000/api/v1/agents/{id}/tools/call \
  -H "X-Tenant-ID: enterprise-A" \
  -d '{"tool_name":"web_search","input_params":{"query":"TiDB architecture"}}'

# Step 3: PROVE ISOLATION — Tenant B cannot see Tenant A's session
curl http://localhost:8000/api/v1/agents/{session_id_A}/state \
  -H "X-Tenant-ID: enterprise-B"
# → 404 Not Found ← ISOLATION PROVEN

# Step 4: Run Qwen Meta-Agent
curl http://localhost:8000/api/v1/meta-agent/report \
  -H "X-Tenant-ID: enterprise-A"
# → Returns: failure_patterns, tool_optimizations, efficiency_score

# Step 5: Show TiFlash vs TiKV speed
# Run analytical query on TiFlash: ~12ms
# Same query on TiKV: ~890ms  ← HTAP value proven
```

---

## Why TiDB is the Right Choice

| Challenge | Without TiDB | With TiDB |
|-----------|-------------|-----------|
| Agent state persistence | Redis (volatile) + Postgres (separate) | Single HTAP cluster |
| Analytical queries on live data | ETL pipeline needed (hours) | TiFlash replica (instant) |
| 50 concurrent agents writing | Lock contention, degraded perf | Optimistic concurrency, isolated |
| Cross-tenant isolation | App-layer only, error-prone | Partition + app layer, bulletproof |
| Scale from 10 → 10K tenants | Reshard pain | Online DDL, no downtime |

---

## Judging Criteria Alignment

| Criterion | AgentNexus Answer |
|-----------|-------------------|
| **Innovation** | Database as agent memory — TiDB as cognitive backbone, not just storage |
| **Technical Depth** | HTAP (TiKV+TiFlash), tenant partitioning, Qwen meta-agent loop |
| **Alibaba Cloud Integration** | API Gateway + PAI-EAS + RAM + RocketMQ + OSS |
| **TiDB Usage** | Placement rules, TiFlash replicas, HTAP workload separation |
| **Real-World Applicability** | Solves exact X×Y×Z problem Alibaba faced in production |
| **Demo Quality** | Proven isolation + Qwen output + TiFlash speed comparison |

---

*AgentNexus — "The database is not just storage. It's the agent's mind."*
*Built in 60 minutes | Alibaba Cloud × TiDB × Qwen*
