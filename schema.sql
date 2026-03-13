-- =================================================================
-- AgentNexus — TiDB Schema + TiFlash Replicas + Seed Data
-- =================================================================

CREATE DATABASE IF NOT EXISTS agentnexus;
USE agentnexus;

-- -----------------------------------------------------------------
-- Table 1: tenants
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id  VARCHAR(36)                              NOT NULL,
    name       VARCHAR(100)                             NOT NULL,
    plan       ENUM('starter','growth','enterprise')    NOT NULL DEFAULT 'starter',
    status     ENUM('active','suspended')               NOT NULL DEFAULT 'active',
    created_at TIMESTAMP                                NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id)
);

-- -----------------------------------------------------------------
-- Table 2: agent_sessions  (partitioned by tenant_id)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id  VARCHAR(36)                                             NOT NULL,
    tenant_id   VARCHAR(36)                                             NOT NULL,
    agent_type  ENUM('research','codegen','data','web')                 NOT NULL,
    status      ENUM('planning','running','completed','failed','paused') NOT NULL DEFAULT 'planning',
    task_plan   JSON,
    context     JSON,
    created_at  TIMESTAMP(3)                                            NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at  TIMESTAMP(3)                                            NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (tenant_id, session_id),
    INDEX idx_status (tenant_id, status, created_at)
)
PARTITION BY HASH(tenant_id) PARTITIONS 32;

-- -----------------------------------------------------------------
-- Table 3: tool_call_history  (partitioned by tenant_id)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tool_call_history (
    call_id       VARCHAR(36)                                          NOT NULL,
    session_id    VARCHAR(36)                                          NOT NULL,
    tenant_id     VARCHAR(36)                                          NOT NULL,
    tool_name     ENUM('web_search','code_exec','db_query','file_read','api_call') NOT NULL,
    input_params  JSON,
    output_result JSON,
    status        ENUM('pending','success','failed','timeout')         NOT NULL DEFAULT 'pending',
    latency_ms    INT,
    called_at     TIMESTAMP(3)                                         NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (tenant_id, session_id, call_id),
    INDEX idx_tool (tenant_id, tool_name, called_at)
)
PARTITION BY HASH(tenant_id) PARTITIONS 32;

-- -----------------------------------------------------------------
-- TiFlash Replicas (HTAP columnar engine)
-- -----------------------------------------------------------------
ALTER TABLE agent_sessions    SET TIFLASH REPLICA 1;
ALTER TABLE tool_call_history SET TIFLASH REPLICA 1;

-- =================================================================
-- SEED DATA
-- =================================================================

-- -----------------------------------------------------------------
-- 2 Tenants
-- -----------------------------------------------------------------
INSERT INTO tenants (tenant_id, name, plan, status) VALUES
    ('ent-A', 'Enterprise Alpha', 'enterprise', 'active'),
    ('ent-B', 'Enterprise Beta',  'growth',     'active');

-- -----------------------------------------------------------------
-- 20 Agent Sessions  (10 per tenant)
-- -----------------------------------------------------------------
-- Tenant ent-A: 6 completed, 2 failed, 2 running
INSERT INTO agent_sessions (session_id, tenant_id, agent_type, status, task_plan, context, created_at) VALUES
    ('sess-a-001', 'ent-A', 'research', 'completed',
        '{"steps":["search","analyze","report"],"priority":"high"}',
        '{"query":"TiDB architecture","depth":3}',
        NOW() - INTERVAL 23 HOUR),
    ('sess-a-002', 'ent-A', 'codegen',  'completed',
        '{"steps":["scaffold","implement","test"],"priority":"high"}',
        '{"language":"python","framework":"fastapi"}',
        NOW() - INTERVAL 22 HOUR),
    ('sess-a-003', 'ent-A', 'data',     'completed',
        '{"steps":["ingest","transform","load"],"priority":"medium"}',
        '{"source":"s3","destination":"tidb"}',
        NOW() - INTERVAL 20 HOUR),
    ('sess-a-004', 'ent-A', 'web',      'failed',
        '{"steps":["crawl","parse","store"],"priority":"low"}',
        '{"url":"https://example.com","depth":2}',
        NOW() - INTERVAL 18 HOUR),
    ('sess-a-005', 'ent-A', 'research', 'completed',
        '{"steps":["search","analyze","report"],"priority":"high"}',
        '{"query":"multi-tenant SaaS patterns","depth":2}',
        NOW() - INTERVAL 16 HOUR),
    ('sess-a-006', 'ent-A', 'codegen',  'failed',
        '{"steps":["scaffold","implement","test"],"priority":"medium"}',
        '{"language":"go","framework":"gin"}',
        NOW() - INTERVAL 14 HOUR),
    ('sess-a-007', 'ent-A', 'data',     'completed',
        '{"steps":["ingest","transform","load"],"priority":"high"}',
        '{"source":"kafka","destination":"tiflash"}',
        NOW() - INTERVAL 12 HOUR),
    ('sess-a-008', 'ent-A', 'web',      'running',
        '{"steps":["crawl","parse","store"],"priority":"medium"}',
        '{"url":"https://docs.pingcap.com","depth":3}',
        NOW() - INTERVAL 8 HOUR),
    ('sess-a-009', 'ent-A', 'research', 'completed',
        '{"steps":["search","analyze","report"],"priority":"high"}',
        '{"query":"Qwen API integration","depth":2}',
        NOW() - INTERVAL 4 HOUR),
    ('sess-a-010', 'ent-A', 'codegen',  'running',
        '{"steps":["scaffold","implement","test"],"priority":"high"}',
        '{"language":"typescript","framework":"nextjs"}',
        NOW() - INTERVAL 1 HOUR);

-- Tenant ent-B: 6 completed, 3 failed, 1 running
INSERT INTO agent_sessions (session_id, tenant_id, agent_type, status, task_plan, context, created_at) VALUES
    ('sess-b-001', 'ent-B', 'research', 'completed',
        '{"steps":["search","analyze","report"],"priority":"medium"}',
        '{"query":"vector database comparison","depth":2}',
        NOW() - INTERVAL 23 HOUR),
    ('sess-b-002', 'ent-B', 'web',      'completed',
        '{"steps":["crawl","parse","store"],"priority":"high"}',
        '{"url":"https://tidb.cloud","depth":2}',
        NOW() - INTERVAL 21 HOUR),
    ('sess-b-003', 'ent-B', 'data',     'failed',
        '{"steps":["ingest","transform","load"],"priority":"high"}',
        '{"source":"postgres","destination":"tidb"}',
        NOW() - INTERVAL 19 HOUR),
    ('sess-b-004', 'ent-B', 'codegen',  'completed',
        '{"steps":["scaffold","implement","test"],"priority":"medium"}',
        '{"language":"rust","framework":"actix"}',
        NOW() - INTERVAL 17 HOUR),
    ('sess-b-005', 'ent-B', 'research', 'failed',
        '{"steps":["search","analyze","report"],"priority":"low"}',
        '{"query":"HTAP workload benchmarks","depth":4}',
        NOW() - INTERVAL 15 HOUR),
    ('sess-b-006', 'ent-B', 'web',      'completed',
        '{"steps":["crawl","parse","store"],"priority":"medium"}',
        '{"url":"https://arxiv.org","depth":1}',
        NOW() - INTERVAL 13 HOUR),
    ('sess-b-007', 'ent-B', 'data',     'completed',
        '{"steps":["ingest","transform","load"],"priority":"high"}',
        '{"source":"bigquery","destination":"tidb"}',
        NOW() - INTERVAL 10 HOUR),
    ('sess-b-008', 'ent-B', 'codegen',  'failed',
        '{"steps":["scaffold","implement","test"],"priority":"medium"}',
        '{"language":"java","framework":"spring"}',
        NOW() - INTERVAL 7 HOUR),
    ('sess-b-009', 'ent-B', 'research', 'completed',
        '{"steps":["search","analyze","report"],"priority":"high"}',
        '{"query":"agentic AI orchestration","depth":3}',
        NOW() - INTERVAL 3 HOUR),
    ('sess-b-010', 'ent-B', 'web',      'running',
        '{"steps":["crawl","parse","store"],"priority":"low"}',
        '{"url":"https://huggingface.co","depth":2}',
        NOW() - INTERVAL 30 MINUTE);

-- -----------------------------------------------------------------
-- 100 Tool Call History rows  (50 per tenant, ~5 per session)
-- -----------------------------------------------------------------

-- ent-A session sess-a-001 (5 calls: 3 success, 2 failed)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-a001-01','sess-a-001','ent-A','web_search',
 '{"query":"TiDB architecture best practices"}',
 '{"results":["https://docs.pingcap.com/tidb"],"count":10}',
 'success', 120, NOW() - INTERVAL 23 HOUR),
('call-a001-02','sess-a-001','ent-A','web_search',
 '{"query":"HTAP workloads TiDB TiFlash"}',
 '{"results":["https://pingcap.com/blog/htap"],"count":8}',
 'success', 95, NOW() - INTERVAL 22 HOUR + INTERVAL 55 MINUTE),
('call-a001-03','sess-a-001','ent-A','db_query',
 '{"sql":"SELECT COUNT(*) FROM events","timeout":30}',
 '{"rows":[[142839]],"elapsed_ms":88}',
 'success', 88, NOW() - INTERVAL 22 HOUR + INTERVAL 50 MINUTE),
('call-a001-04','sess-a-001','ent-A','api_call',
 '{"endpoint":"https://api.internal/summarize","method":"POST"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9200, NOW() - INTERVAL 22 HOUR + INTERVAL 45 MINUTE),
('call-a001-05','sess-a-001','ent-A','api_call',
 '{"endpoint":"https://api.internal/classify","method":"POST"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9800, NOW() - INTERVAL 22 HOUR + INTERVAL 30 MINUTE);

-- ent-A session sess-a-002 (5 calls: 4 success, 1 timeout)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-a002-01','sess-a-002','ent-A','code_exec',
 '{"language":"python","code":"import pandas as pd\ndf = pd.read_csv(\"data.csv\")"}',
 '{"stdout":"","stderr":"","exit_code":0}',
 'success', 210, NOW() - INTERVAL 22 HOUR),
('call-a002-02','sess-a-002','ent-A','code_exec',
 '{"language":"python","code":"print(df.describe())"}',
 '{"stdout":"count  1000.0\nmean   42.3","exit_code":0}',
 'success', 185, NOW() - INTERVAL 21 HOUR + INTERVAL 55 MINUTE),
('call-a002-03','sess-a-002','ent-A','file_read',
 '{"path":"/workspace/schema.json","encoding":"utf-8"}',
 '{"content":"{\"version\":\"1.0\"}","size_bytes":512}',
 'success', 55, NOW() - INTERVAL 21 HOUR + INTERVAL 50 MINUTE),
('call-a002-04','sess-a-002','ent-A','code_exec',
 '{"language":"python","code":"import torch; model = torch.load(\"model.pt\")"}',
 '{"error":"timeout","message":"execution exceeded 30s limit"}',
 'timeout', 9500, NOW() - INTERVAL 21 HOUR + INTERVAL 40 MINUTE),
('call-a002-05','sess-a-002','ent-A','db_query',
 '{"sql":"SELECT * FROM users LIMIT 100","timeout":30}',
 '{"rows":100,"elapsed_ms":143}',
 'success', 143, NOW() - INTERVAL 21 HOUR + INTERVAL 20 MINUTE);

-- ent-A session sess-a-003 (5 calls: 5 success)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-a003-01','sess-a-003','ent-A','db_query',
 '{"sql":"SELECT COUNT(*) FROM events","timeout":30}',
 '{"rows":[[99231]],"elapsed_ms":76}',
 'success', 76, NOW() - INTERVAL 20 HOUR),
('call-a003-02','sess-a-003','ent-A','db_query',
 '{"sql":"SELECT tenant_id, SUM(cost) FROM billing GROUP BY tenant_id","timeout":30}',
 '{"rows":24,"elapsed_ms":201}',
 'success', 201, NOW() - INTERVAL 19 HOUR + INTERVAL 55 MINUTE),
('call-a003-03','sess-a-003','ent-A','file_read',
 '{"path":"/data/config.yaml","encoding":"utf-8"}',
 '{"content":"host: tidb.cluster\nport: 4000","size_bytes":256}',
 'success', 62, NOW() - INTERVAL 19 HOUR + INTERVAL 50 MINUTE),
('call-a003-04','sess-a-003','ent-A','code_exec',
 '{"language":"python","code":"import pandas as pd\npd.read_parquet(\"s3://bucket/data.parquet\")"}',
 '{"stdout":"DataFrame(100000, 12)","exit_code":0}',
 'success', 287, NOW() - INTERVAL 19 HOUR + INTERVAL 45 MINUTE),
('call-a003-05','sess-a-003','ent-A','db_query',
 '{"sql":"INSERT INTO processed SELECT * FROM staging","timeout":60}',
 '{"rows_affected":100000,"elapsed_ms":312}',
 'success', 312, NOW() - INTERVAL 19 HOUR + INTERVAL 30 MINUTE);

-- ent-A session sess-a-004 (5 calls: 2 success, 3 failed)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-a004-01','sess-a-004','ent-A','web_search',
 '{"query":"site crawling best practices rate limiting"}',
 '{"results":["https://scrapy.org/docs"],"count":5}',
 'success', 130, NOW() - INTERVAL 18 HOUR),
('call-a004-02','sess-a-004','ent-A','api_call',
 '{"endpoint":"https://api.example.com/pages","method":"GET"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 10000, NOW() - INTERVAL 17 HOUR + INTERVAL 55 MINUTE),
('call-a004-03','sess-a-004','ent-A','api_call',
 '{"endpoint":"https://api.example.com/parse","method":"POST"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9500, NOW() - INTERVAL 17 HOUR + INTERVAL 45 MINUTE),
('call-a004-04','sess-a-004','ent-A','api_call',
 '{"endpoint":"https://api.example.com/store","method":"POST"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 8800, NOW() - INTERVAL 17 HOUR + INTERVAL 30 MINUTE),
('call-a004-05','sess-a-004','ent-A','db_query',
 '{"sql":"SELECT url FROM crawl_queue LIMIT 10","timeout":30}',
 '{"rows":10,"elapsed_ms":55}',
 'success', 55, NOW() - INTERVAL 17 HOUR + INTERVAL 15 MINUTE);

-- ent-A session sess-a-005 (5 calls: 5 success)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-a005-01','sess-a-005','ent-A','web_search',
 '{"query":"multi-tenant SaaS architecture patterns 2024"}',
 '{"results":["https://martinfowler.com/articles/saas"],"count":12}',
 'success', 115, NOW() - INTERVAL 16 HOUR),
('call-a005-02','sess-a-005','ent-A','web_search',
 '{"query":"row-level security database isolation"}',
 '{"results":["https://www.postgresql.org/docs/rls"],"count":9}',
 'success', 108, NOW() - INTERVAL 15 HOUR + INTERVAL 55 MINUTE),
('call-a005-03','sess-a-005','ent-A','web_search',
 '{"query":"TiDB partition by tenant performance"}',
 '{"results":["https://docs.pingcap.com/partitioning"],"count":7}',
 'success', 99, NOW() - INTERVAL 15 HOUR + INTERVAL 50 MINUTE),
('call-a005-04','sess-a-005','ent-A','db_query',
 '{"sql":"SELECT COUNT(*) FROM agent_sessions WHERE tenant_id=?","timeout":10}',
 '{"rows":[[10]],"elapsed_ms":42}',
 'success', 42, NOW() - INTERVAL 15 HOUR + INTERVAL 45 MINUTE),
('call-a005-05','sess-a-005','ent-A','code_exec',
 '{"language":"python","code":"import pandas as pd\nresult = analyze_patterns(df)"}',
 '{"stdout":"Patterns found: 5","exit_code":0}',
 'success', 230, NOW() - INTERVAL 15 HOUR + INTERVAL 30 MINUTE);

-- ent-A session sess-a-006 (5 calls: 1 success, 3 failed, 1 timeout)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-a006-01','sess-a-006','ent-A','file_read',
 '{"path":"/workspace/main.go","encoding":"utf-8"}',
 '{"content":"package main\nimport \"fmt\"","size_bytes":2048}',
 'success', 70, NOW() - INTERVAL 14 HOUR),
('call-a006-02','sess-a-006','ent-A','code_exec',
 '{"language":"go","code":"go build ./..."}',
 '{"error":"compilation failed","stderr":"undefined: ginRouter"}',
 'failed', 4200, NOW() - INTERVAL 13 HOUR + INTERVAL 55 MINUTE),
('call-a006-03','sess-a-006','ent-A','code_exec',
 '{"language":"go","code":"go test ./..."}',
 '{"error":"test panic","stderr":"nil pointer dereference"}',
 'failed', 3800, NOW() - INTERVAL 13 HOUR + INTERVAL 45 MINUTE),
('call-a006-04','sess-a-006','ent-A','api_call',
 '{"endpoint":"https://api.internal/lint","method":"POST"}',
 '{"error":"upstream_timeout","retries":3}',
 'timeout', 8200, NOW() - INTERVAL 13 HOUR + INTERVAL 30 MINUTE),
('call-a006-05','sess-a-006','ent-A','code_exec',
 '{"language":"go","code":"go vet ./..."}',
 '{"error":"vet failed","stderr":"SA1006: Printf with no formatting directive"}',
 'failed', 1500, NOW() - INTERVAL 13 HOUR + INTERVAL 15 MINUTE);

-- ent-A session sess-a-007 (5 calls: 5 success)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-a007-01','sess-a-007','ent-A','db_query',
 '{"sql":"SELECT * FROM kafka_offsets","timeout":10}',
 '{"rows":4,"elapsed_ms":38}',
 'success', 38, NOW() - INTERVAL 12 HOUR),
('call-a007-02','sess-a-007','ent-A','code_exec',
 '{"language":"python","code":"import pandas as pd\ndf = consume_kafka_topic(\"events\", 10000)"}',
 '{"stdout":"Consumed 10000 messages","exit_code":0}',
 'success', 195, NOW() - INTERVAL 11 HOUR + INTERVAL 55 MINUTE),
('call-a007-03','sess-a-007','ent-A','code_exec',
 '{"language":"python","code":"df_clean = transform_pipeline(df)"}',
 '{"stdout":"Transformed 9847/10000 rows","exit_code":0}',
 'success', 260, NOW() - INTERVAL 11 HOUR + INTERVAL 50 MINUTE),
('call-a007-04','sess-a-007','ent-A','db_query',
 '{"sql":"INSERT INTO tiflash_sink SELECT * FROM staging_df","timeout":60}',
 '{"rows_affected":9847,"elapsed_ms":280}',
 'success', 280, NOW() - INTERVAL 11 HOUR + INTERVAL 40 MINUTE),
('call-a007-05','sess-a-007','ent-A','db_query',
 '{"sql":"UPDATE kafka_offsets SET offset=offset+10000","timeout":10}',
 '{"rows_affected":4,"elapsed_ms":25}',
 'success', 25, NOW() - INTERVAL 11 HOUR + INTERVAL 30 MINUTE);

-- ent-A session sess-a-008 (5 calls: 4 success, 1 failed)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-a008-01','sess-a-008','ent-A','web_search',
 '{"query":"PingCAP TiDB documentation site:docs.pingcap.com"}',
 '{"results":["https://docs.pingcap.com/tidb"],"count":15}',
 'success', 110, NOW() - INTERVAL 8 HOUR),
('call-a008-02','sess-a-008','ent-A','api_call',
 '{"endpoint":"https://docs.pingcap.com/api/pages","method":"GET"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9100, NOW() - INTERVAL 7 HOUR + INTERVAL 55 MINUTE),
('call-a008-03','sess-a-008','ent-A','web_search',
 '{"query":"TiFlash replica configuration tuning"}',
 '{"results":["https://docs.pingcap.com/tiflash"],"count":6}',
 'success', 125, NOW() - INTERVAL 7 HOUR + INTERVAL 40 MINUTE),
('call-a008-04','sess-a-008','ent-A','file_read',
 '{"path":"/tmp/crawl_output.json","encoding":"utf-8"}',
 '{"content":"{\"pages\":142}","size_bytes":8192}',
 'success', 88, NOW() - INTERVAL 7 HOUR + INTERVAL 30 MINUTE),
('call-a008-05','sess-a-008','ent-A','db_query',
 '{"sql":"INSERT INTO crawl_results VALUES (?,?,?)","timeout":30}',
 '{"rows_affected":142,"elapsed_ms":99}',
 'success', 99, NOW() - INTERVAL 7 HOUR + INTERVAL 20 MINUTE);

-- ent-A session sess-a-009 (5 calls: 5 success)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-a009-01','sess-a-009','ent-A','web_search',
 '{"query":"Qwen API integration Python examples"}',
 '{"results":["https://help.aliyun.com/zh/dashscope"],"count":8}',
 'success', 118, NOW() - INTERVAL 4 HOUR),
('call-a009-02','sess-a-009','ent-A','web_search',
 '{"query":"DashScope text generation API reference"}',
 '{"results":["https://dashscope.aliyun.com/docs"],"count":6}',
 'success', 102, NOW() - INTERVAL 3 HOUR + INTERVAL 55 MINUTE),
('call-a009-03','sess-a-009','ent-A','code_exec',
 '{"language":"python","code":"import httpx\nresp = httpx.post(DASHSCOPE_URL, json=payload)"}',
 '{"stdout":"{\"output\":{\"text\":\"...\"}}","exit_code":0}',
 'success', 245, NOW() - INTERVAL 3 HOUR + INTERVAL 50 MINUTE),
('call-a009-04','sess-a-009','ent-A','db_query',
 '{"sql":"SELECT * FROM tool_call_history WHERE tenant_id=? LIMIT 100","timeout":10}',
 '{"rows":100,"elapsed_ms":67}',
 'success', 67, NOW() - INTERVAL 3 HOUR + INTERVAL 45 MINUTE),
('call-a009-05','sess-a-009','ent-A','code_exec',
 '{"language":"python","code":"import pandas as pd\nreport = generate_optimization_report(df)"}',
 '{"stdout":"Report generated: 5 recommendations","exit_code":0}',
 'success', 190, NOW() - INTERVAL 3 HOUR + INTERVAL 30 MINUTE);

-- ent-A session sess-a-010 (5 calls: 4 success, 1 timeout)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-a010-01','sess-a-010','ent-A','code_exec',
 '{"language":"typescript","code":"npx create-next-app@latest agentnexus-ui"}',
 '{"stdout":"✓ Created Next.js app","exit_code":0}',
 'success', 275, NOW() - INTERVAL 1 HOUR),
('call-a010-02','sess-a-010','ent-A','code_exec',
 '{"language":"typescript","code":"npm install @tidb/client @tanstack/react-query"}',
 '{"stdout":"added 142 packages","exit_code":0}',
 'success', 180, NOW() - INTERVAL 55 MINUTE),
('call-a010-03','sess-a-010','ent-A','file_read',
 '{"path":"/workspace/agentnexus-ui/package.json","encoding":"utf-8"}',
 '{"content":"{\"name\":\"agentnexus-ui\",\"version\":\"0.1.0\"}","size_bytes":1024}',
 'success', 52, NOW() - INTERVAL 50 MINUTE),
('call-a010-04','sess-a-010','ent-A','api_call',
 '{"endpoint":"https://api.vercel.com/deployments","method":"POST"}',
 '{"error":"upstream_timeout","retries":3}',
 'timeout', 8500, NOW() - INTERVAL 45 MINUTE),
('call-a010-05','sess-a-010','ent-A','db_query',
 '{"sql":"SELECT * FROM deployments WHERE status=?","timeout":10}',
 '{"rows":3,"elapsed_ms":44}',
 'success', 44, NOW() - INTERVAL 30 MINUTE);

-- ent-B session sess-b-001 (5 calls: 5 success)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-b001-01','sess-b-001','ent-B','web_search',
 '{"query":"vector database pgvector pinecone weaviate comparison 2024"}',
 '{"results":["https://db-engines.com/en/ranking"],"count":10}',
 'success', 130, NOW() - INTERVAL 23 HOUR),
('call-b001-02','sess-b-001','ent-B','web_search',
 '{"query":"TiDB vector search embedding support"}',
 '{"results":["https://docs.pingcap.com/tidb/stable/vector-search"],"count":7}',
 'success', 112, NOW() - INTERVAL 22 HOUR + INTERVAL 55 MINUTE),
('call-b001-03','sess-b-001','ent-B','db_query',
 '{"sql":"SELECT COUNT(*) FROM embeddings","timeout":10}',
 '{"rows":[[500000]],"elapsed_ms":92}',
 'success', 92, NOW() - INTERVAL 22 HOUR + INTERVAL 50 MINUTE),
('call-b001-04','sess-b-001','ent-B','code_exec',
 '{"language":"python","code":"import pandas as pd\ndf = benchmark_vector_dbs(configs)"}',
 '{"stdout":"Benchmark complete: 3 dbs tested","exit_code":0}',
 'success', 210, NOW() - INTERVAL 22 HOUR + INTERVAL 45 MINUTE),
('call-b001-05','sess-b-001','ent-B','file_read',
 '{"path":"/results/vector_benchmark.json","encoding":"utf-8"}',
 '{"content":"{\"winner\":\"tidb\"}","size_bytes":4096}',
 'success', 78, NOW() - INTERVAL 22 HOUR + INTERVAL 30 MINUTE);

-- ent-B session sess-b-002 (5 calls: 4 success, 1 failed)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-b002-01','sess-b-002','ent-B','web_search',
 '{"query":"site:tidb.cloud pricing enterprise plans"}',
 '{"results":["https://tidb.cloud/pricing"],"count":5}',
 'success', 105, NOW() - INTERVAL 21 HOUR),
('call-b002-02','sess-b-002','ent-B','api_call',
 '{"endpoint":"https://tidb.cloud/api/pricing","method":"GET"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9300, NOW() - INTERVAL 20 HOUR + INTERVAL 55 MINUTE),
('call-b002-03','sess-b-002','ent-B','web_search',
 '{"query":"TiDB serverless connection limits quota"}',
 '{"results":["https://docs.pingcap.com/tidb/stable/serverless-limitations"],"count":8}',
 'success', 117, NOW() - INTERVAL 20 HOUR + INTERVAL 40 MINUTE),
('call-b002-04','sess-b-002','ent-B','db_query',
 '{"sql":"SELECT * FROM scraped_pages ORDER BY scraped_at DESC LIMIT 20","timeout":10}',
 '{"rows":20,"elapsed_ms":58}',
 'success', 58, NOW() - INTERVAL 20 HOUR + INTERVAL 30 MINUTE),
('call-b002-05','sess-b-002','ent-B','file_read',
 '{"path":"/output/tidb_pricing_summary.md","encoding":"utf-8"}',
 '{"content":"# TiDB Pricing\n...","size_bytes":2048}',
 'success', 63, NOW() - INTERVAL 20 HOUR + INTERVAL 20 MINUTE);

-- ent-B session sess-b-003 (5 calls: 1 success, 3 failed, 1 timeout)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-b003-01','sess-b-003','ent-B','db_query',
 '{"sql":"SELECT table_name FROM information_schema.tables WHERE table_schema=?","timeout":10}',
 '{"rows":48,"elapsed_ms":45}',
 'success', 45, NOW() - INTERVAL 19 HOUR),
('call-b003-02','sess-b-003','ent-B','api_call',
 '{"endpoint":"https://postgres.internal/export","method":"POST"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 10000, NOW() - INTERVAL 18 HOUR + INTERVAL 55 MINUTE),
('call-b003-03','sess-b-003','ent-B','api_call',
 '{"endpoint":"https://postgres.internal/schema","method":"GET"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9700, NOW() - INTERVAL 18 HOUR + INTERVAL 45 MINUTE),
('call-b003-04','sess-b-003','ent-B','code_exec',
 '{"language":"python","code":"import pandas as pd\ndf = pg.read_all_tables(conn)"}',
 '{"error":"timeout","message":"execution exceeded 30s limit"}',
 'timeout', 8900, NOW() - INTERVAL 18 HOUR + INTERVAL 30 MINUTE),
('call-b003-05','sess-b-003','ent-B','api_call',
 '{"endpoint":"https://tidb.internal/import","method":"POST"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9400, NOW() - INTERVAL 18 HOUR + INTERVAL 15 MINUTE);

-- ent-B session sess-b-004 (5 calls: 5 success)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-b004-01','sess-b-004','ent-B','code_exec',
 '{"language":"rust","code":"cargo new agentnexus-worker"}',
 '{"stdout":"Created binary (application) agentnexus-worker","exit_code":0}',
 'success', 195, NOW() - INTERVAL 17 HOUR),
('call-b004-02','sess-b-004','ent-B','file_read',
 '{"path":"/workspace/agentnexus-worker/Cargo.toml","encoding":"utf-8"}',
 '{"content":"[package]\nname = \"agentnexus-worker\"","size_bytes":512}',
 'success', 48, NOW() - INTERVAL 16 HOUR + INTERVAL 55 MINUTE),
('call-b004-03','sess-b-004','ent-B','code_exec',
 '{"language":"rust","code":"cargo add actix-web tokio serde"}',
 '{"stdout":"Updating Cargo.lock","exit_code":0}',
 'success', 280, NOW() - INTERVAL 16 HOUR + INTERVAL 50 MINUTE),
('call-b004-04','sess-b-004','ent-B','code_exec',
 '{"language":"rust","code":"cargo build --release"}',
 '{"stdout":"Finished release target","exit_code":0}',
 'success', 295, NOW() - INTERVAL 16 HOUR + INTERVAL 40 MINUTE),
('call-b004-05','sess-b-004','ent-B','db_query',
 '{"sql":"INSERT INTO build_artifacts VALUES (?,?,?,?)","timeout":10}',
 '{"rows_affected":1,"elapsed_ms":35}',
 'success', 35, NOW() - INTERVAL 16 HOUR + INTERVAL 30 MINUTE);

-- ent-B session sess-b-005 (5 calls: 1 success, 4 failed)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-b005-01','sess-b-005','ent-B','web_search',
 '{"query":"HTAP workload TiDB TiFlash benchmark sysbench 2024"}',
 '{"results":["https://pingcap.com/blog/htap-benchmark"],"count":4}',
 'success', 135, NOW() - INTERVAL 15 HOUR),
('call-b005-02','sess-b-005','ent-B','api_call',
 '{"endpoint":"https://benchmark.internal/run","method":"POST"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9800, NOW() - INTERVAL 14 HOUR + INTERVAL 55 MINUTE),
('call-b005-03','sess-b-005','ent-B','api_call',
 '{"endpoint":"https://benchmark.internal/results","method":"GET"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9200, NOW() - INTERVAL 14 HOUR + INTERVAL 45 MINUTE),
('call-b005-04','sess-b-005','ent-B','code_exec',
 '{"language":"python","code":"import pandas as pd\nresults = run_sysbench(config)"}',
 '{"error":"compilation failed","stderr":"ModuleNotFoundError: sysbench"}',
 'failed', 1200, NOW() - INTERVAL 14 HOUR + INTERVAL 30 MINUTE),
('call-b005-05','sess-b-005','ent-B','api_call',
 '{"endpoint":"https://tidb.internal/explain-analyze","method":"POST"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 10000, NOW() - INTERVAL 14 HOUR + INTERVAL 15 MINUTE);

-- ent-B session sess-b-006 (5 calls: 5 success)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-b006-01','sess-b-006','ent-B','web_search',
 '{"query":"arxiv.org machine learning papers 2024 agents"}',
 '{"results":["https://arxiv.org/search/?query=agents"],"count":20}',
 'success', 120, NOW() - INTERVAL 13 HOUR),
('call-b006-02','sess-b-006','ent-B','api_call',
 '{"endpoint":"https://export.arxiv.org/api/query","method":"GET"}',
 '{"status":200,"entries":50}',
 'success', 220, NOW() - INTERVAL 12 HOUR + INTERVAL 55 MINUTE),
('call-b006-03','sess-b-006','ent-B','code_exec',
 '{"language":"python","code":"import pandas as pd\ndf = parse_arxiv_feed(xml_data)"}',
 '{"stdout":"Parsed 50 papers","exit_code":0}',
 'success', 155, NOW() - INTERVAL 12 HOUR + INTERVAL 50 MINUTE),
('call-b006-04','sess-b-006','ent-B','db_query',
 '{"sql":"INSERT INTO research_papers SELECT * FROM arxiv_staging","timeout":30}',
 '{"rows_affected":50,"elapsed_ms":88}',
 'success', 88, NOW() - INTERVAL 12 HOUR + INTERVAL 45 MINUTE),
('call-b006-05','sess-b-006','ent-B','file_read',
 '{"path":"/output/arxiv_summary.json","encoding":"utf-8"}',
 '{"content":"{\"total\":50,\"topics\":[\"agents\"]}","size_bytes":2048}',
 'success', 55, NOW() - INTERVAL 12 HOUR + INTERVAL 30 MINUTE);

-- ent-B session sess-b-007 (5 calls: 5 success)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-b007-01','sess-b-007','ent-B','db_query',
 '{"sql":"SELECT project, SUM(cost_usd) FROM bq_billing GROUP BY project","timeout":30}',
 '{"rows":12,"elapsed_ms":180}',
 'success', 180, NOW() - INTERVAL 10 HOUR),
('call-b007-02','sess-b-007','ent-B','api_call',
 '{"endpoint":"https://bigquery.googleapis.com/bigquery/v2/projects/proj/jobs","method":"POST"}',
 '{"status":200,"jobId":"bqjob_123"}',
 'success', 290, NOW() - INTERVAL 9 HOUR + INTERVAL 55 MINUTE),
('call-b007-03','sess-b-007','ent-B','code_exec',
 '{"language":"python","code":"import pandas as pd\ndf = bq_client.list_rows(table).to_dataframe()"}',
 '{"stdout":"DataFrame(50000, 8)","exit_code":0}',
 'success', 270, NOW() - INTERVAL 9 HOUR + INTERVAL 50 MINUTE),
('call-b007-04','sess-b-007','ent-B','db_query',
 '{"sql":"INSERT INTO tidb_analytics SELECT * FROM bq_export_df","timeout":60}',
 '{"rows_affected":50000,"elapsed_ms":310}',
 'success', 310, NOW() - INTERVAL 9 HOUR + INTERVAL 40 MINUTE),
('call-b007-05','sess-b-007','ent-B','db_query',
 '{"sql":"UPDATE migration_status SET completed_at=NOW() WHERE job_id=?","timeout":10}',
 '{"rows_affected":1,"elapsed_ms":22}',
 'success', 22, NOW() - INTERVAL 9 HOUR + INTERVAL 30 MINUTE);

-- ent-B session sess-b-008 (5 calls: 1 success, 3 failed, 1 timeout)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-b008-01','sess-b-008','ent-B','file_read',
 '{"path":"/workspace/src/main/java/App.java","encoding":"utf-8"}',
 '{"content":"public class App { ... }","size_bytes":3072}',
 'success', 68, NOW() - INTERVAL 7 HOUR),
('call-b008-02','sess-b-008','ent-B','code_exec',
 '{"language":"java","code":"mvn package -DskipTests"}',
 '{"error":"compilation failed","stderr":"[ERROR] COMPILATION ERROR: cannot find symbol"}',
 'failed', 2800, NOW() - INTERVAL 6 HOUR + INTERVAL 55 MINUTE),
('call-b008-03','sess-b-008','ent-B','api_call',
 '{"endpoint":"https://maven.internal/dependencies","method":"POST"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9600, NOW() - INTERVAL 6 HOUR + INTERVAL 45 MINUTE),
('call-b008-04','sess-b-008','ent-B','code_exec',
 '{"language":"java","code":"mvn test"}',
 '{"error":"timeout","message":"execution exceeded 30s limit"}',
 'timeout', 8400, NOW() - INTERVAL 6 HOUR + INTERVAL 30 MINUTE),
('call-b008-05','sess-b-008','ent-B','api_call',
 '{"endpoint":"https://sonarqube.internal/analysis","method":"POST"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9100, NOW() - INTERVAL 6 HOUR + INTERVAL 15 MINUTE);

-- ent-B session sess-b-009 (5 calls: 5 success)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-b009-01','sess-b-009','ent-B','web_search',
 '{"query":"agentic AI orchestration frameworks LangChain AutoGen 2024"}',
 '{"results":["https://github.com/langchain-ai/langchain"],"count":15}',
 'success', 125, NOW() - INTERVAL 3 HOUR),
('call-b009-02','sess-b-009','ent-B','web_search',
 '{"query":"multi-agent coordination patterns tool use"}',
 '{"results":["https://arxiv.org/abs/2308.11432"],"count":11}',
 'success', 108, NOW() - INTERVAL 2 HOUR + INTERVAL 55 MINUTE),
('call-b009-03','sess-b-009','ent-B','code_exec',
 '{"language":"python","code":"import pandas as pd\ndf = compare_frameworks(configs)"}',
 '{"stdout":"Comparison: 4 frameworks evaluated","exit_code":0}',
 'success', 240, NOW() - INTERVAL 2 HOUR + INTERVAL 50 MINUTE),
('call-b009-04','sess-b-009','ent-B','db_query',
 '{"sql":"INSERT INTO framework_benchmarks VALUES (?,?,?,?)","timeout":10}',
 '{"rows_affected":4,"elapsed_ms":38}',
 'success', 38, NOW() - INTERVAL 2 HOUR + INTERVAL 45 MINUTE),
('call-b009-05','sess-b-009','ent-B','file_read',
 '{"path":"/output/framework_comparison.pdf","encoding":"binary"}',
 '{"size_bytes":204800,"pages":12}',
 'success', 95, NOW() - INTERVAL 2 HOUR + INTERVAL 30 MINUTE);

-- ent-B session sess-b-010 (5 calls: 4 success, 1 failed)
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-b010-01','sess-b-010','ent-B','web_search',
 '{"query":"huggingface.co new model releases march 2026"}',
 '{"results":["https://huggingface.co/models"],"count":20}',
 'success', 115, NOW() - INTERVAL 30 MINUTE),
('call-b010-02','sess-b-010','ent-B','api_call',
 '{"endpoint":"https://huggingface.co/api/models","method":"GET"}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9500, NOW() - INTERVAL 25 MINUTE),
('call-b010-03','sess-b-010','ent-B','web_search',
 '{"query":"huggingface transformers model cards LLM"}',
 '{"results":["https://huggingface.co/docs/hub/model-cards"],"count":12}',
 'success', 122, NOW() - INTERVAL 20 MINUTE),
('call-b010-04','sess-b-010','ent-B','db_query',
 '{"sql":"SELECT * FROM model_registry WHERE released_at > NOW() - INTERVAL 7 DAY","timeout":10}',
 '{"rows":8,"elapsed_ms":42}',
 'success', 42, NOW() - INTERVAL 15 MINUTE),
('call-b010-05','sess-b-010','ent-B','file_read',
 '{"path":"/tmp/hf_models_staging.json","encoding":"utf-8"}',
 '{"content":"{\"models\":[]}","size_bytes":256}',
 'success', 58, NOW() - INTERVAL 10 MINUTE);

-- FAILURE SCENARIO DEMO DATA
-- 10 extra api_call failures for tenant ent-A, session sess-a-001
-- All upstream_timeout, high latency — used for Qwen failure analysis demo
INSERT INTO tool_call_history (call_id, session_id, tenant_id, tool_name, input_params, output_result, status, latency_ms, called_at) VALUES
('call-a001-f01','sess-a-001','ent-A','api_call',
 '{"endpoint":"https://api.internal/enrich","method":"POST","payload_size_kb":12}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9850, NOW() - INTERVAL 22 HOUR + INTERVAL 20 MINUTE),
('call-a001-f02','sess-a-001','ent-A','api_call',
 '{"endpoint":"https://api.internal/enrich","method":"POST","payload_size_kb":15}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 10000, NOW() - INTERVAL 22 HOUR + INTERVAL 15 MINUTE),
('call-a001-f03','sess-a-001','ent-A','api_call',
 '{"endpoint":"https://api.internal/summarize","method":"POST","payload_size_kb":8}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 8200, NOW() - INTERVAL 22 HOUR + INTERVAL 10 MINUTE),
('call-a001-f04','sess-a-001','ent-A','api_call',
 '{"endpoint":"https://api.internal/summarize","method":"POST","payload_size_kb":20}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9600, NOW() - INTERVAL 22 HOUR + INTERVAL 5 MINUTE),
('call-a001-f05','sess-a-001','ent-A','api_call',
 '{"endpoint":"https://api.internal/classify","method":"POST","payload_size_kb":6}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 8900, NOW() - INTERVAL 22 HOUR),
('call-a001-f06','sess-a-001','ent-A','api_call',
 '{"endpoint":"https://api.internal/classify","method":"POST","payload_size_kb":9}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9300, NOW() - INTERVAL 21 HOUR + INTERVAL 55 MINUTE),
('call-a001-f07','sess-a-001','ent-A','api_call',
 '{"endpoint":"https://api.internal/rank","method":"POST","payload_size_kb":11}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9700, NOW() - INTERVAL 21 HOUR + INTERVAL 50 MINUTE),
('call-a001-f08','sess-a-001','ent-A','api_call',
 '{"endpoint":"https://api.internal/rank","method":"POST","payload_size_kb":7}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 8500, NOW() - INTERVAL 21 HOUR + INTERVAL 45 MINUTE),
('call-a001-f09','sess-a-001','ent-A','api_call',
 '{"endpoint":"https://api.internal/embed","method":"POST","payload_size_kb":14}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9100, NOW() - INTERVAL 21 HOUR + INTERVAL 40 MINUTE),
('call-a001-f10','sess-a-001','ent-A','api_call',
 '{"endpoint":"https://api.internal/embed","method":"POST","payload_size_kb":18}',
 '{"error":"upstream_timeout","retries":3}',
 'failed', 9400, NOW() - INTERVAL 21 HOUR + INTERVAL 35 MINUTE);
