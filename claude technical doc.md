# Documento Técnico — Multi-Tenant SaaS Platform
### Alibaba Cloud + TiDB + Qwen AI · Escenario A: GameVault Corp

> **Duración:** 6 horas · **Equipo:** 3 integrantes · **Puntaje total:** 100 pts

---

## Tabla de Contenidos

1. [Visión General de la Arquitectura](#1-visión-general-de-la-arquitectura)
2. [Roles del Equipo](#2-roles-del-equipo)
3. [Desglose de Tareas por Integrante](#3-desglose-de-tareas-por-integrante)
4. [Prompts Útiles](#4-prompts-útiles)
5. [Referencia SQL — Comandos Clave](#5-referencia-sql--comandos-clave)
6. [Cronograma de 6 Horas](#6-cronograma-de-6-horas)
7. [Rúbrica de Evaluación](#7-rúbrica-de-evaluación)
8. [Script del Demo (5 Minutos)](#8-script-del-demo-5-minutos)
9. [Configuración del Entorno](#9-configuración-del-entorno)

---

## 1. Visión General de la Arquitectura

La plataforma implementa cuatro capas lógicas interconectadas sobre infraestructura de Alibaba Cloud, con TiDB como backbone de base de datos distribuida multi-tenant.

| Capa | Servicio | Responsabilidad |
|------|----------|-----------------|
| **Datos** | TiDB Cloud | Schemas multi-tenant, TiFlash HTAP, RBAC, SQL Views |
| **Aplicación** | Alibaba ECS | REST API Python/Node.js, routing por `tenant_id` |
| **IA** | Model Studio (Qwen-Plus) | Recomendaciones LLM, respuestas JSON estructuradas |
| **Analytics** | Quick BI | Dashboards conectados a SQL Views por tenant |

### 1.1 Rutas de Conexión de Red

Existen **tres rutas distintas** que el equipo debe configurar:

- **ECS → TiDB Cloud:** TLS, puerto 4000. IP de ECS debe estar en allowlist de TiDB Cloud.
- **Quick BI → TiDB Cloud:** TLS, puerto 4000. IPs egress de Quick BI en allowlist.
- **ECS → Model Studio (Qwen):** HTTPS puro. Base URL: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`

---

## 2. Roles del Equipo

| Rol | Integrante | Alcance |
|-----|-----------|---------|
| 🏗️ **Arquitecto / Infra** | Integrante 1 | VPC, ECS, Security Group, RAM, arquitectura general, slide del demo |
| ⚙️ **Backend Developer** | Integrante 2 | REST API (FastAPI/Express), integración Qwen, seed data, endpoints |
| 🗄️ **Data Engineer** | Integrante 3 | TiDB schemas, RBAC, TiFlash, Plan Binding, SQL Views, Quick BI |

---

## 3. Desglose de Tareas por Integrante

### 3.1 Integrante 1 — Arquitecto / Infraestructura

| # | Tarea | Tiempo | Prioridad |
|---|-------|--------|-----------|
| 1 | Crear VPC (CIDR `10.0.0.0/16`) + vSwitch (`10.0.1.0/24`) en Singapore | 15 min | 🔴 CRÍTICA |
| 2 | Configurar Security Group: inbound 22/80/443, outbound TCP 4000 y 443 | 10 min | 🔴 CRÍTICA |
| 3 | Lanzar instancia ECS Ubuntu 22.04 (4 vCPU / 8 GB), asignar Elastic IP | 15 min | 🔴 CRÍTICA |
| 4 | Crear RAM user con permisos ECS + Model Studio. **NO usar root.** | 10 min | 🟡 ALTA |
| 5 | Instalar Python 3.11 + dependencias en ECS (FastAPI, openai, pymysql, uvicorn) | 15 min | 🔴 CRÍTICA |
| 6 | Configurar variables de entorno en ECS: `TIDB_HOST`, `TIDB_PORT`, `DASHSCOPE_API_KEY` | 10 min | 🔴 CRÍTICA |
| 7 | Preparar slide de arquitectura para demo (1 slide: capas TiDB / ECS / Qwen / BI) | 20 min | 🟡 ALTA |
| 8 | Obtener IP de ECS y agregarla al allowlist de TiDB Cloud | 10 min | 🔴 CRÍTICA |
| 9 | Verificar conectividad ECS → TiDB Cloud (`mysql -h <host> -P 4000 -u admin -p`) | 10 min | 🔴 CRÍTICA |
| 10 | Coordinar y liderar ensayo del demo script (5 min) | 30 min | 🟡 ALTA |

---

### 3.2 Integrante 2 — Backend Developer

| # | Tarea | Tiempo | Prioridad |
|---|-------|--------|-----------|
| 1 | Escribir `POST /api/{store_id}/purchase` (inserta en `orders` + `order_items` del tenant) | 25 min | 🔴 CRÍTICA |
| 2 | Escribir `GET /api/{store_id}/recommend/{customer_id}` (query TiDB → Qwen → store rec) | 35 min | 🔴 CRÍTICA |
| 3 | Implementar función de contexto Qwen: últimas 20 compras → JSON → system prompt → parse JSON | 30 min | 🔴 CRÍTICA |
| 4 | Agregar manejo de errores: `tenant_id` inválido → 404; Qwen falla → 503 | 15 min | 🟡 ALTA |
| 5 | Configurar connection pool **por tenant** (usar DB user del tenant, nunca el admin) | 20 min | 🔴 CRÍTICA |
| 6 | Ejecutar script de seed data (100+ games, 50+ customers, 200+ orders por store) | 20 min | 🟡 ALTA |
| 7 | Verificar que no hay credenciales hardcodeadas (todo via env vars) | 10 min | 🟡 ALTA |
| 8 | Levantar servidor (`uvicorn main:app --host 0.0.0.0 --port 80`) y probar con curl | 15 min | 🔴 CRÍTICA |
| 9 | Escribir script de write stream continuo para demo del Online DDL (loop POST) | 15 min | 🟠 MEDIA |
| 10 | Documentar ejemplos de curl para cada endpoint (para usar durante el demo) | 15 min | 🟡 ALTA |

---

### 3.3 Integrante 3 — Data Engineer

| # | Tarea | Tiempo | Prioridad |
|---|-------|--------|-----------|
| 1 | **[M1]** Escribir y ejecutar script de provisioning: `CREATE DATABASE`, tablas, user, GRANT, SQL Views para 5 stores | 40 min | 🔴 CRÍTICA |
| 2 | **[M1]** Verificar que el script agrega el 6to tenant en <60s. Probar en dry-run. | 10 min | 🔴 CRÍTICA |
| 3 | **[RBAC]** Verificar aislamiento: conectar como `user_store_alpha` → `SHOW DATABASES` → ACCESS DENIED en `store_beta` | 15 min | 🔴 CRÍTICA |
| 4 | **[M3]** Habilitar TiFlash en `games`, `orders`, `order_items` para los 5 tenants. Esperar `AVAILABLE=1`. | 20 min | 🔴 CRÍTICA |
| 5 | **[M3]** Verificar `cop[tiflash]` en EXPLAIN de la query analítica. Capturar evidencia. | 10 min | 🔴 CRÍTICA |
| 6 | **[M2]** Crear `GLOBAL BINDING` para query cross-tenant (genre + COUNT). Verificar reuso de plan. | 20 min | 🟡 ALTA |
| 7 | **[M4]** Demo Online DDL: lanzar write stream → `ALTER TABLE ADD COLUMN` → confirmar 0 downtime | 20 min | 🟡 ALTA |
| 8 | Configurar Quick BI: agregar IPs egress → crear datasource → 3 datasets sobre SQL Views | 30 min | 🟡 ALTA |
| 9 | Construir dashboard Quick BI: bar chart (ventas por género), top titles, daily revenue trend | 30 min | 🟡 ALTA |
| 10 | Verificar aislamiento en Quick BI: insertar en `store_beta` → confirmar que dashboard `store_alpha` NO cambia | 10 min | 🟡 ALTA |

---

## 4. Prompts Útiles

### 4.1 System Prompt Principal — Qwen Recomendaciones (GameVault)

Usar como `system` message. Exigir **SOLO JSON**, sin texto libre:

```
You are a video game recommendation engine for an e-commerce platform.
You will receive a customer's purchase history as structured JSON.
Analyze genres, platforms, spending patterns, and recency.
Respond ONLY with a valid JSON object — no preamble, no markdown, no backticks:

{
  "recommendations": [
    {"title": "...", "genre": "...", "platform": "...", "reason": "..."},
    {"title": "...", "genre": "...", "platform": "...", "reason": "..."},
    {"title": "...", "genre": "...", "platform": "...", "reason": "..."}
  ],
  "summary": "brief overall insight about this customer"
}
```

**User message template** (reemplazar con datos reales de TiDB):

```
Customer ID: {customer_id}
Customer Name: {name}
Recent Purchases (last 20):
{JSON.stringify(purchases, null, 2)}
Available games in catalog not yet purchased:
{JSON.stringify(available_games.slice(0, 20), null, 2)}
```

---

### 4.2 Prompt Anti-Freetext (si Qwen no responde en JSON)

Agregar al final del system prompt si Qwen responde con texto libre:

```
IMPORTANT: You MUST respond with ONLY valid JSON.
No explanation, no markdown, no backticks.
Your entire response must be parseable by JSON.parse().
If you cannot provide recommendations, return:
{"recommendations": [], "summary": "insufficient data"}
```

---

### 4.3 Prompts para Generar Código con IA

**Backend — Endpoint de recomendación:**

```
Genera un endpoint en FastAPI (Python) llamado:
GET /api/{store_id}/recommend/{customer_id}

Que haga lo siguiente:
1. Conecte a TiDB usando el DB user del tenant (store_id determina el schema y el user)
2. Consulte las últimas 20 compras del customer_id en ese schema
3. Formatee los datos como JSON limpio
4. Llame a Qwen-Plus via openai SDK (base_url=dashscope-intl, api_key=env var)
5. Parsee la respuesta JSON de Qwen
6. Guarde el resultado en la tabla recommendations del schema
7. Retorne el JSON al cliente

No uses credenciales hardcodeadas. Usa connection pooling. Maneja errores con HTTP status codes correctos.
```

**Data Layer — Script de provisioning:**

```
Escribe un script Python que provisione un nuevo tenant de GameVault en TiDB.
El script recibe: TENANT_NAME (ej: store_gamma)

El script debe ejecutar en orden:
1. CREATE DATABASE {tenant_name}
2. CREATE TABLEs: games, customers, orders, order_items, recommendations con los schemas exactos
   - Usar AUTO_RANDOM en game_id, order_id
3. CREATE USER '{prefix}.user_{tenant_name}'@'%' IDENTIFIED BY '{password}'
4. GRANT SELECT, INSERT, UPDATE ON {tenant_name}.* TO ese usuario
5. ALTER TABLE games SET TIFLASH REPLICA 1 (igual para orders y order_items)
6. CREATE VIEW sales_by_genre, top_titles_this_week, daily_revenue

El script completo debe ejecutar en menos de 60 segundos.
```

---

### 4.4 Q&A — Respuestas para los Jueces

| Pregunta del Juez | Respuesta Sugerida |
|-------------------|--------------------|
| ¿Qué pasa si el Resource Group de un tenant se agota? | TiDB throttlea las queries de ese tenant sin afectar a los demás. Los `RU_PER_SEC` actúan como circuit breaker por tenant. |
| ¿Cómo ayuda el plan binding a 500 tenants? | Todos los tenants ejecutan las mismas queries estructuralmente. Un solo `GLOBAL BINDING` garantiza que el optimizador usa el plan óptimo sin divergencia, eliminando plan regression. |
| ¿Por qué elegiste qwen-plus sobre qwen-max? | qwen-plus tiene razonamiento suficiente para recomendaciones contextuales y es ~4x más económico. En un hackathon de 6h el budget es limitado y qwen-plus cumple el objetivo. |
| ¿Cómo agregarías el tenant 50? | Ejecutar el provisioning script con el nuevo nombre. Crea DB, tablas, user, RBAC y TiFlash en <60s sin cambios en el código de la aplicación. |
| ¿Por qué AUTO_RANDOM y no AUTO_INCREMENT? | AUTO_INCREMENT crea hotspots: todos los inserts van al mismo nodo TiKV. AUTO_RANDOM distribuye los IDs aleatoriamente entre regiones, maximizando el throughput paralelo de múltiples tenants. |

---

## 5. Referencia SQL — Comandos Clave

### 5.1 Módulo 1: Provisioning del Schema

```sql
-- Crear schema del tenant
CREATE DATABASE store_alpha;

-- Tabla games con AUTO_RANDOM
CREATE TABLE store_alpha.games (
  game_id      BIGINT PRIMARY KEY AUTO_RANDOM,
  title        VARCHAR(200) NOT NULL,
  genre        ENUM('Action','RPG','Strategy','Sports','Indie','Horror'),
  platform     VARCHAR(50),
  price        DECIMAL(8,2),
  release_date DATE,
  stock        INT DEFAULT 0
);

-- Tabla orders con AUTO_RANDOM
CREATE TABLE store_alpha.orders (
  order_id     BIGINT PRIMARY KEY AUTO_RANDOM,
  customer_id  BIGINT NOT NULL,
  total_amount DECIMAL(10,2),
  status       ENUM('pending','completed','refunded') DEFAULT 'completed',
  ordered_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla recommendations para guardar output de Qwen
CREATE TABLE store_alpha.recommendations (
  rec_id         BIGINT PRIMARY KEY AUTO_RANDOM,
  customer_id    BIGINT NOT NULL,
  game_ids       JSON,
  qwen_reasoning TEXT,
  generated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 5.2 Módulo 3: Habilitar TiFlash HTAP

```sql
-- Habilitar réplicas columnar en tablas analíticas
ALTER TABLE store_alpha.games       SET TIFLASH REPLICA 1;
ALTER TABLE store_alpha.orders      SET TIFLASH REPLICA 1;
ALTER TABLE store_alpha.order_items SET TIFLASH REPLICA 1;

-- Verificar sincronización (esperar AVAILABLE = 1, tarda 2-5 min)
SELECT TABLE_NAME, REPLICA_COUNT, AVAILABLE
FROM   information_schema.tiflash_replica
WHERE  TABLE_SCHEMA = 'store_alpha';

-- Verificar routing a TiFlash (buscar cop[tiflash] en el output)
EXPLAIN
  SELECT g.genre, COUNT(*) AS units
  FROM   order_items oi JOIN games g ON oi.game_id = g.game_id
  GROUP BY g.genre;
```

---

### 5.3 Módulo 2: Cross-Schema Plan Binding

```sql
-- Crear binding global para query analítica común a todos los tenants
CREATE GLOBAL BINDING FOR
  SELECT g.genre, COUNT(*) FROM order_items oi
  JOIN games g ON oi.game_id = g.game_id GROUP BY g.genre
USING
  SELECT /*+ HASH_AGG() USE_INDEX(oi, idx_game_id) */ g.genre, COUNT(*)
  FROM   order_items oi JOIN games g ON oi.game_id = g.game_id
  GROUP BY g.genre;

-- Verificar bindings activos
SHOW GLOBAL BINDINGS;
```

---

### 5.4 Módulo 4: Online Schema Change

```sql
-- Agregar columna sin downtime mientras hay escrituras activas en otro tenant
ALTER TABLE store_alpha.orders ADD COLUMN discount_pct DECIMAL(5,2) DEFAULT 0.00;

-- Verificar que la columna existe y tiene el valor default
DESCRIBE store_alpha.orders;
```

---

### 5.5 RBAC — Verificación de Aislamiento

```sql
-- Crear usuario scoped al schema del tenant (reemplazar {prefix})
CREATE USER '{prefix}.user_store_alpha'@'%' IDENTIFIED BY 'SecurePass123!';
GRANT SELECT, INSERT, UPDATE ON store_alpha.* TO '{prefix}.user_store_alpha'@'%';

-- Verificación (conectado como user_store_alpha):
SHOW DATABASES;                    -- Solo debe mostrar store_alpha
SELECT * FROM store_beta.orders;   -- Debe dar ACCESS DENIED ✅
```

---

### 5.6 SQL Views para Quick BI

```sql
-- Ventas por género
CREATE VIEW store_alpha.sales_by_genre AS
  SELECT g.genre,
         COUNT(oi.item_id)                 AS units_sold,
         SUM(oi.unit_price * oi.quantity)  AS revenue
  FROM   order_items oi JOIN games g ON oi.game_id = g.game_id
  GROUP BY g.genre;

-- Top títulos de la semana
CREATE VIEW store_alpha.top_titles_this_week AS
  SELECT g.title, g.genre, COUNT(*) AS purchases
  FROM   orders o
  JOIN   order_items oi ON o.order_id = oi.order_id
  JOIN   games g ON oi.game_id = g.game_id
  WHERE  o.ordered_at >= NOW() - INTERVAL 7 DAY
  GROUP BY g.title, g.genre
  ORDER BY purchases DESC LIMIT 10;

-- Revenue diario
CREATE VIEW store_alpha.daily_revenue AS
  SELECT DATE(ordered_at) AS sale_date, SUM(total_amount) AS revenue
  FROM   orders
  GROUP BY DATE(ordered_at)
  ORDER BY sale_date;
```

---

## 6. Cronograma de 6 Horas

> I1 = Arquitecto · I2 = Backend · I3 = Data Engineer

| Tiempo | Fase | Tareas Paralelas | Dependencias |
|--------|------|-----------------|--------------|
| 0:00–0:30 | Setup inicial | I1: VPC, ECS, Security Group. I3: conectar TiDB Cloud. | I2: clonar repo, instalar deps |
| 0:30–1:30 | Provisioning & Schema | I3: script provisioning 5 tenants, RBAC, TiFlash. I2: endpoints base + connection pool. | I1: configurar Elastic IP + env vars |
| 1:30–2:30 | Backend + AI | I2: endpoint recommend + integración Qwen. I3: SQL Views. | I1: verificar conectividad end-to-end |
| 2:30–3:30 | Analytics & Módulos | I3: Quick BI datasource + 3 charts. I2: seed data script. | I1: Plan Binding + script Online DDL |
| 3:30–4:30 | Testing & Ajustes | TODOS: probar flujo completo, verificar EXPLAIN TiFlash, aislamiento Quick BI. | Corregir errores críticos |
| 4:30–5:30 | Ensayo del Demo | I1 lidera ensayo del script de 5 min. I2 y I3 ejecutan sus partes. | Comandos curl y SQL listos en terminal |
| 5:30–6:00 | Buffer + Demo | Demo en vivo ante jueces. Responder Q&A. | — |

---

## 7. Rúbrica de Evaluación

| Criterio | Pts | Obligatorio | Qué evalúan los jueces |
|----------|-----|-------------|------------------------|
| **[M1] Provisioning + Aislamiento** | 30 | ✅ SÍ | 5 schemas + script <60s + RBAC ACCESS DENIED cross-tenant |
| **[M3] TiFlash HTAP Verificado** | 30 | ✅ SÍ | TiFlash habilitado + `cop[tiflash]` en EXPLAIN + explicar beneficio HTAP |
| [M2] Cross-Schema Plan Binding | 20 | NO | GLOBAL BINDING creado, mismo plan reusado en todos los tenants |
| [M4] Online Schema Change | 20 | NO | ADD COLUMN sin downtime confirmado con write stream activo |
| Calidad AI (Qwen) | 15 | NO | Respuesta coherente, JSON parseado correctamente, guardado en TiDB |
| Dashboard Quick BI | 10 | NO | 3 charts vivos + aislamiento visual verificado ante jueces |
| Write API Correctness | 10 | NO | POST escribe al tenant correcto, `4xx` en tenant inválido |
| Calidad de Código | 10 | NO | Sin credenciales hardcoded, connection pool, seed data, explicación de escalabilidad |

> ⚠️ **Los criterios marcados como Obligatorio son binarios** — si no se demuestran, el puntaje máximo es **60 puntos** independientemente de todo lo demás.

### Puntos Extra (Stretch Goals)

- **Tier 1:** AUTO_RANDOM comparison + EXPLAIN ANALYZE RU cost + TiFlash vs TiKV benchmark
- **Tier 2:** Embeddings Qwen + Vector Search en TiDB (`VECTOR` column + `VEC_COSINE_DISTANCE`)
- **Tier 3:** TiDB Cloud Branching — schema migration en branch, sandbox de agente, 20 tenants en un run

---

## 8. Script del Demo (5 Minutos)

> Cada integrante debe tener sus comandos listos en terminal. **NO improvisar.**

| Tiempo | Fase | Qué hace el equipo | Comandos / Evidencia |
|--------|------|--------------------|----------------------|
| 0:00–0:30 | Arquitectura | I1 presenta slide de arquitectura. Explica los 4 módulos TiDB. | 1 diapositiva con capas visibles |
| 0:30–1:15 | Aislamiento [M1+M3] | I3 conecta como `user_store_alpha`. `SHOW DATABASES`. Intenta `SELECT` en `store_beta`. | `SHOW DATABASES;` → `SELECT * FROM store_beta.orders;` → ACCESS DENIED |
| 1:15–2:00 | Write + AI | I2 ejecuta POST purchase, luego GET recommend. Muestra JSON de Qwen con reasoning. | `curl -X POST /api/store_alpha/purchase ...` → `curl GET /api/store_alpha/recommend/1` |
| 2:00–2:45 | Provisioning [M1] | I3 ejecuta script en vivo para `store_zeta`. Cronometrar <60s. | `python provision.py store_zeta` → DB, tables, user, views created in Xs |
| 2:45–3:15 | Online DDL [M4] | I2 lanza write stream en background. I3 ejecuta ALTER TABLE. Sin errores. | Loop POST background + `ALTER TABLE store_alpha.orders ADD COLUMN discount_pct ...` |
| 3:15–4:00 | Quick BI + Plan Binding | I3 abre dashboard, 3 charts vivos. Muestra `EXPLAIN` con `cop[tiflash]`. `GLOBAL BINDING` activo. | `EXPLAIN SELECT genre ...` → `cop[tiflash]` · `SHOW GLOBAL BINDINGS` |
| 4:00–5:00 | Q&A | Responder preguntas de los jueces con confianza. | Ver tabla Q&A en sección 4.4 |

### Checklist Pre-Demo (30 min antes)

- [ ] Terminal abierta con `user_store_alpha` autenticado en TiDB
- [ ] Curl commands copiados y listos en un `.txt` (purchase + recommend)
- [ ] Script `provision.py` testeado — `store_zeta` **NO** debe existir todavía
- [ ] Write stream script (loop POST) testeado y listo para ejecutar
- [ ] Dashboard Quick BI abierto en browser con datos frescos
- [ ] EXPLAIN output pre-verificado mostrando `cop[tiflash]`
- [ ] `SHOW GLOBAL BINDINGS` con al menos 1 binding activo
- [ ] Slide de arquitectura en pantalla completa lista

---

## 9. Configuración del Entorno

### 9.1 Variables de Entorno en ECS

```bash
# /etc/environment o .env — NUNCA hardcodear en el código
TIDB_HOST=<gateway-tidb-cloud-host>
TIDB_PORT=4000
TIDB_USER_STORE_ALPHA={prefix}.user_store_alpha
TIDB_PASS_STORE_ALPHA=<password>
TIDB_USER_STORE_BETA={prefix}.user_store_beta
TIDB_PASS_STORE_BETA=<password>
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

### 9.2 Instalación de Dependencias (ECS Ubuntu 22.04)

```bash
sudo apt update && sudo apt install -y python3.11 python3-pip
pip3 install fastapi uvicorn openai pymysql python-dotenv

# Levantar servidor
uvicorn main:app --host 0.0.0.0 --port 80 --workers 2
```

### 9.3 Verificaciones de Conectividad

```bash
# Test TiDB desde ECS
mysql -h $TIDB_HOST -P 4000 -u admin -p -e 'SELECT version();'

# Test Qwen API desde ECS
curl -X POST https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen-plus","messages":[{"role":"user","content":"ping"}]}'
```

### 9.4 Errores Comunes y Soluciones

| Error | Causa | Solución |
|-------|-------|----------|
| `Connection refused port 4000` | IP de ECS no en allowlist TiDB | TiDB Cloud → Security → IP Access List → agregar IP ECS |
| `User name must start with...` | Falta prefijo de cluster en username | Verificar prefijo en TiDB Cloud console. Formato: `{prefix}.user_xxx` |
| Qwen devuelve texto libre, no JSON | System prompt no especifica JSON estrictamente | Agregar: `"Respond ONLY with valid JSON. No other text."` |
| `Quick BI connection refused` | IPs Quick BI no en allowlist | Agregar IPs egress de Quick BI a TiDB Cloud IP Access List |
| EXPLAIN muestra `cop[tikv]` en vez de `cop[tiflash]` | Réplica no lista (`AVAILABLE=0`) | Esperar 2–5 min. Verificar: `SELECT TABLE_NAME, AVAILABLE FROM information_schema.tiflash_replica` |
| ACCESS DENIED al consultar `store_beta` | — | ✅ **Esto ES la demostración de aislamiento. No es un error.** |

---

*Documento generado para Hackathon — GameVault Corp · Multi-Tenant SaaS con Alibaba Cloud + TiDB + Qwen AI*
