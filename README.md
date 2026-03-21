# QMANUS_mx 🤖

> Multi-tenant agentic AI platform built at the **Alibaba Cloud × TiDB Hackathon** — CDMX, March 2026.

**[English](#english) | [Español](#español)**

---

## English

### What is QMANUS_mx?

QMANUS_mx (AgentNexus) is a multi-tenant platform that lets multiple organizations run isolated AI agents simultaneously. Each tenant gets its own isolated session space, tool call history, and real-time analytics — all powered by TiDB Cloud's HTAP engine and Qwen AI.

### Architecture

```
┌─────────────────────────────────────────┐
│           index.html (Frontend)         │
│     Analytics Dashboard + Agent UI      │
└──────────────────┬──────────────────────┘
                   │ HTTP + JWT
┌──────────────────▼──────────────────────┐
│         FastAPI Backend (Python)        │
│   Tenant Auth │ Agent Sessions │ Tools  │
└──────────────────┬──────────────────────┘
                   │ aiomysql + SSL
┌──────────────────▼──────────────────────┐
│         TiDB Cloud (Alibaba Cloud)      │
│   OLTP (agent_sessions, tool_calls)     │
│   OLAP (TiFlash replicas → analytics)  │
└─────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Python 3.12 |
| Database | TiDB Cloud (MySQL-compatible HTAP) |
| AI | Qwen (Alibaba DashScope API) |
| Auth | JWT (HS256) + per-tenant isolation |
| Frontend | Vanilla HTML/JS |
| IaC | Terraform (Alibaba Cloud provider) |

### TiDB Features Used

- **Multi-tenant schema** — tenant-scoped tables with row-level isolation
- **TiFlash HTAP** — columnar replicas for real-time analytics without ETL
- **Online Schema Change** — zero-downtime migrations
- **Global Plan Binding** — consistent query execution plans across tenants

### Quick Start

**Prerequisites:** Python 3.10+, MySQL client, TiDB Cloud account, DashScope API key

```bash
git clone https://github.com/G10hdz/QMANUS_mx.git
cd QMANUS_mx

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Generate secrets
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_hex(32)); print('PROVISIONING_SECRET=' + secrets.token_hex(32))"

# Load schema
mysql --host YOUR_TIDB_HOST --port 4000 \
  --user YOUR_USER --password \
  --ssl-mode=VERIFY_IDENTITY \
  --ssl-ca=isrgrootx1.pem \
  -D test < schema.sql

# Run
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `index.html` in your browser, click **Configure API**, and set:
- Base URL: `http://localhost:8000`
- Tenant ID: `enterprise-A`
- JWT Token: generated via `POST /api/v1/auth/token`

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/auth/token` | Mint JWT (requires `X-Provisioning-Key`) |
| `POST` | `/api/v1/agents/launch` | Launch a new agent session |
| `GET` | `/api/v1/agents/{session_id}/state` | Get agent state |
| `POST` | `/api/v1/agents/{session_id}/tools/call` | Execute a tool call |
| `GET` | `/api/{tenant_id}/insights` | Analytics dashboard data |
| `GET` | `/api/v1/meta-agent/report` | Qwen AI-generated report |

### Deploy with Terraform (Alibaba Cloud)

```bash
cd terraform/

export ALICLOUD_ACCESS_KEY="your_key"
export ALICLOUD_SECRET_KEY="your_secret"
export ALICLOUD_REGION="na-south-1"  # Mexico region

terraform init
terraform plan
terraform apply
```

Creates: VPC, vSwitch, Security Group (ports 22 + 8000), ECS instance (Ubuntu 22.04).

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TIDB_HOST` | TiDB Cloud gateway host | ✅ |
| `TIDB_PORT` | TiDB port (default: 4000) | ✅ |
| `TIDB_USER` | TiDB username | ✅ |
| `TIDB_PASS` | TiDB password | ✅ |
| `TIDB_DB` | Database name (default: agentnexus) | ✅ |
| `JWT_SECRET` | JWT signing secret (min 32 chars) | ✅ |
| `PROVISIONING_SECRET` | Token endpoint auth secret | ✅ |
| `DASHSCOPE_API_KEY` | Alibaba DashScope / Qwen API key | Optional |

### Team

Built in ~6 hours at the Alibaba Cloud × TiDB Hackathon, CDMX.

| Role | Contributor |
|------|-------------|
| Infra / Backend / DevOps | [@G10hdz](https://github.com/G10hdz) |
| Frontend | [@jeanethS](https://github.com/jeanethS) |
| Database / Data Layer | [@Daniel-Alvarez-Sil](https://github.com/Daniel-Alvarez-Sil) |

---

## Español

### ¿Qué es QMANUS_mx?

QMANUS_mx (AgentNexus) es una plataforma multi-tenant que permite a múltiples organizaciones ejecutar agentes de IA de forma simultánea y aislada. Cada tenant tiene su propio espacio de sesiones, historial de llamadas a herramientas y analíticas en tiempo real — todo impulsado por el motor HTAP de TiDB Cloud y el modelo Qwen de Alibaba.

### Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI + Python 3.12 |
| Base de datos | TiDB Cloud (compatible MySQL + HTAP) |
| IA | Qwen (Alibaba DashScope API) |
| Autenticación | JWT (HS256) + aislamiento por tenant |
| Frontend | HTML/JS estático |
| IaC | Terraform (provider Alibaba Cloud) |

### Inicio Rápido

```bash
git clone https://github.com/G10hdz/QMANUS_mx.git
cd QMANUS_mx

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edita .env con tus credenciales

uvicorn main:app --host 0.0.0.0 --port 8000
```

### Deploy en Alibaba Cloud con Terraform

```bash
cd terraform/

export ALICLOUD_ACCESS_KEY="tu_key"
export ALICLOUD_SECRET_KEY="tu_secret"
export ALICLOUD_REGION="na-south-1"  # Región México

terraform init
terraform plan
terraform apply
```

### Construido en

**Alibaba Cloud × TiDB Hackathon** — Ciudad de México, marzo 2026.

---

*Fork of [Daniel-Alvarez-Sil/QMANUS_mx](https://github.com/Daniel-Alvarez-Sil/QMANUS_mx)*
