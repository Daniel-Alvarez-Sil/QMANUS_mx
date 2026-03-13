#!/usr/bin/env python3
"""
AgentNexus tenant provisioner for TiDB Cloud / Alibaba hackathon.

What it creates per tenant:
- database/schema: tenant_<name>
- tables: agents, sessions, state_snapshots, tool_calls, insights
- tenant DB user with schema-scoped grants
- 3 SQL views for Quick BI:
    - agent_performance
    - tool_usage_stats
    - daily_sessions
- optional TiFlash replicas on analytical tables

Why this matches the challenge:
- database-per-tenant model
- automated provisioning for a 6th tenant in under 60s
- AUTO_RANDOM on high-write primary keys
- per-tenant users / RBAC
- 3 analytical views per tenant
- TiFlash enabled on analytical tables

Usage:
    python provision_tenant.py acme
    python provision_tenant.py globex --password "StrongPass123!"
    python provision_tenant.py umbrella --with-tiflash --wait-tiflash
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import secrets
import string
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Iterable, Optional

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import Cursor


# -----------------------------
# Configuration / helpers
# -----------------------------

SAFE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,62}$")

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()  # loads variables from .env in current folder


@dataclass
class Config:
    host: str
    port: int
    admin_user: str
    admin_password: str
    ssl_ca: Optional[str]
    ssl_required: bool
    cluster_prefix: str


def getenv_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_config() -> Config:
    ssl_ca_value = os.getenv("TIDB_SSL_CA")
    if ssl_ca_value == "":
        ssl_ca_value = None

    if ssl_ca_value is None:
        bundled_ca = Path(__file__).with_name("isrgrootx1.pem")
        if bundled_ca.exists():
            ssl_ca_value = str(bundled_ca)

    return Config(
        host=getenv_required("TIDB_HOST"),
        port=int(os.getenv("TIDB_PORT", "4000")),
        admin_user=getenv_required("TIDB_ADMIN_USER"),
        admin_password=getenv_required("TIDB_ADMIN_PASSWORD"),
        ssl_ca=ssl_ca_value,
        ssl_required=os.getenv("TIDB_SSL_REQUIRED", "1").lower() not in {"0", "false", "no"},
        cluster_prefix=getenv_required("TIDB_CLUSTER_PREFIX"),
    )


def sanitize_tenant_name(raw: str) -> str:
    """
    Converts input like 'Acme Inc' -> 'acme_inc'
    """
    tenant = raw.strip().lower()
    tenant = re.sub(r"[^a-z0-9]+", "_", tenant)
    tenant = tenant.strip("_")

    if not tenant:
        raise ValueError("Tenant name cannot be empty after sanitization.")

    if tenant[0].isdigit():
        tenant = f"t_{tenant}"

    if not SAFE_NAME_RE.match(tenant):
        raise ValueError(
            f"Tenant name '{tenant}' is invalid after sanitization. "
            "Use letters, numbers, underscores; start with a letter."
        )

    return tenant


def database_name(tenant: str) -> str:
    return f"tenant_{tenant}"


def user_prefix(admin_user: str, cluster_prefix: str) -> str:
    """
    TiDB Cloud user creation requires the admin namespace prefix.
    In this environment the effective constraint is:
    - username must start with "<admin-namespace>."
    - total username length must be <= 32

    The cluster prefix is not appended here because it can easily exceed TiDB's
    32-character username limit for child users.
    """
    admin_namespace = admin_user.split(".", 1)[0]
    return admin_namespace


def compact_username(prefix: str, role: str, tenant: str, max_length: int = 32) -> str:
    suffix_budget = max_length - len(prefix) - 1
    if suffix_budget <= 0:
        raise ValueError(f"User prefix '{prefix}' is too long for TiDB's {max_length}-char username limit.")

    base_suffix = f"{role}_{tenant}"
    if len(base_suffix) <= suffix_budget:
        return f"{prefix}.{base_suffix}"

    digest = hashlib.sha1(tenant.encode("utf-8")).hexdigest()[:6]
    separator = "_"
    reserved = len(role) + len(separator) + len(digest)
    tenant_budget = suffix_budget - reserved
    if tenant_budget <= 0:
        raise ValueError(f"Cannot build a valid TiDB username for tenant '{tenant}' within {max_length} characters.")

    shortened_tenant = tenant[:tenant_budget]
    return f"{prefix}.{role}_{shortened_tenant}{digest}"


def tenant_username(cluster_prefix: str, tenant: str) -> str:
    return compact_username(cluster_prefix, "u", tenant)


def quickbi_username(cluster_prefix: str, tenant: str) -> str:
    return compact_username(cluster_prefix, "q", tenant)


def generate_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits + "_-!@#%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def connect_admin(cfg: Config, database: Optional[str] = None, autocommit: bool = True) -> Connection:
    ssl_arg = None
    if cfg.ssl_required:
        ssl_arg = {"ca": cfg.ssl_ca} if cfg.ssl_ca else {}

    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.admin_user,
        password=cfg.admin_password,
        database=database,
        autocommit=autocommit,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor,
        ssl=ssl_arg,
    )


def execute(cur: Cursor, sql: str, params: Optional[tuple] = None) -> None:
    if params is None:
        cur.execute(sql)
        return

    cur.execute(sql, params)


def quote_ident(identifier: str) -> str:
    """
    Basic MySQL/TiDB identifier quoting.
    Caller must still sanitize names before use.
    """
    return f"`{identifier.replace('`', '``')}`"


def print_step(message: str) -> None:
    print(f"[+] {message}")


# -----------------------------
# DDL
# -----------------------------

def create_platform_db(cur: Cursor) -> None:
    execute(cur, "CREATE DATABASE IF NOT EXISTS `platform`;")
    print_step("Ensured shared platform database exists: platform")


def create_platform_tables(cur: Cursor) -> None:
    execute(
        cur,
        """
        CREATE TABLE IF NOT EXISTS `platform`.`tenants` (
            tenant_id VARCHAR(100) PRIMARY KEY,
            db_name VARCHAR(100) NOT NULL,
            db_user VARCHAR(200) NOT NULL,
            db_password VARCHAR(255) NOT NULL,
            is_active TINYINT NOT NULL DEFAULT 1
        );
        """,
    )
    print_step("Ensured platform tenant registry exists: platform.tenants")


def create_tenant_database(cur: Cursor, db_name: str) -> None:
    execute(cur, f"CREATE DATABASE IF NOT EXISTS {quote_ident(db_name)};")
    print_step(f"Created database (if not exists): {db_name}")


def create_tables(cur: Cursor, db_name: str) -> None:
    db = quote_ident(db_name)

    # Agents
    execute(cur, f"""
        CREATE TABLE IF NOT EXISTS {db}.agents (
            agent_id BIGINT PRIMARY KEY AUTO_RANDOM,
            name VARCHAR(100) NOT NULL,
            type VARCHAR(50) NOT NULL,
            capabilities JSON NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_agents_type (type),
            KEY idx_agents_created_at (created_at)
        );
    """)

    # Sessions - high write, AUTO_RANDOM
    execute(cur, f"""
        CREATE TABLE IF NOT EXISTS {db}.sessions (
            session_id BIGINT PRIMARY KEY AUTO_RANDOM,
            agent_id BIGINT NOT NULL,
            task_description TEXT NOT NULL,
            status VARCHAR(30) NOT NULL,
            started_at DATETIME NOT NULL,
            completed_at DATETIME NULL,
            KEY idx_sessions_agent_id (agent_id),
            KEY idx_sessions_status (status),
            KEY idx_sessions_started_at (started_at),
            KEY idx_sessions_completed_at (completed_at)
        );
    """)

    # State snapshots
    execute(cur, f"""
        CREATE TABLE IF NOT EXISTS {db}.state_snapshots (
            snapshot_id BIGINT PRIMARY KEY AUTO_RANDOM,
            session_id BIGINT NOT NULL,
            step_number INT NOT NULL,
            state_data JSON NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_snapshots_session_id (session_id),
            KEY idx_snapshots_created_at (created_at)
        );
    """)

    # Tool calls - high write, AUTO_RANDOM
    execute(cur, f"""
        CREATE TABLE IF NOT EXISTS {db}.tool_calls (
            call_id BIGINT PRIMARY KEY AUTO_RANDOM,
            session_id BIGINT NOT NULL,
            tool_name VARCHAR(100) NOT NULL,
            input JSON NULL,
            output JSON NULL,
            duration_ms INT NULL,
            called_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_tool_calls_session_id (session_id),
            KEY idx_tool_calls_tool_name (tool_name),
            KEY idx_tool_calls_called_at (called_at)
        );
    """)

    # Insights
    execute(cur, f"""
        CREATE TABLE IF NOT EXISTS {db}.insights (
            insight_id BIGINT PRIMARY KEY AUTO_RANDOM,
            tenant_id VARCHAR(100) NOT NULL,
            qwen_analysis TEXT NOT NULL,
            recommendations JSON NULL,
            generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_insights_tenant_id (tenant_id),
            KEY idx_insights_generated_at (generated_at)
        );
    """)

    print_step(f"Created 5 tables in {db_name}")


def create_views(cur: Cursor, db_name: str) -> None:
    db = quote_ident(db_name)

    # Drop/recreate to make reruns idempotent and easy to update
    execute(cur, f"DROP VIEW IF EXISTS {db}.agent_performance;")
    execute(cur, f"""
        CREATE VIEW {db}.agent_performance AS
        SELECT
            a.type AS agent_type,
            COUNT(s.session_id) AS total_sessions,
            SUM(CASE WHEN s.status = 'completed' THEN 1 ELSE 0 END) AS completed_sessions,
            SUM(CASE WHEN s.status = 'failed' THEN 1 ELSE 0 END) AS failed_sessions,
            ROUND(AVG(
                CASE
                    WHEN s.completed_at IS NOT NULL
                    THEN TIMESTAMPDIFF(SECOND, s.started_at, s.completed_at)
                    ELSE NULL
                END
            ), 2) AS avg_duration_sec
        FROM {db}.agents a
        LEFT JOIN {db}.sessions s
            ON a.agent_id = s.agent_id
        GROUP BY a.type;
    """)

    execute(cur, f"DROP VIEW IF EXISTS {db}.tool_usage_stats;")
    execute(cur, f"""
        CREATE VIEW {db}.tool_usage_stats AS
        SELECT
            tc.tool_name,
            COUNT(*) AS call_count,
            ROUND(AVG(tc.duration_ms), 2) AS avg_duration_ms,
            MIN(tc.duration_ms) AS min_duration_ms,
            MAX(tc.duration_ms) AS max_duration_ms
        FROM {db}.tool_calls tc
        GROUP BY tc.tool_name
        ORDER BY call_count DESC;
    """)

    execute(cur, f"DROP VIEW IF EXISTS {db}.daily_sessions;")
    execute(cur, f"""
        CREATE VIEW {db}.daily_sessions AS
        SELECT
            DATE(s.started_at) AS session_day,
            COUNT(*) AS total_sessions,
            SUM(CASE WHEN s.status = 'completed' THEN 1 ELSE 0 END) AS completed_sessions,
            SUM(CASE WHEN s.status = 'failed' THEN 1 ELSE 0 END) AS failed_sessions
        FROM {db}.sessions s
        GROUP BY DATE(s.started_at)
        ORDER BY session_day;
    """)

    print_step(f"Created 3 analytical views in {db_name}")


def create_tenant_user(cur: Cursor, username: str, password: str, db_name: str) -> None:
    # MySQL/TiDB user identifiers are written as 'user'@'%'
    execute(cur, f"CREATE USER IF NOT EXISTS '{username}'@'%%' IDENTIFIED BY %s;", (password,))
    execute(cur, f"GRANT SELECT, INSERT, UPDATE, DELETE ON {quote_ident(db_name)}.* TO '{username}'@'%';")
    print_step(f"Created tenant DB user and granted schema-scoped access: {username}")


def create_quickbi_user(cur: Cursor, username: str, password: str, db_name: str) -> None:
    """
    Optional helper:
    Quick BI should read views only, not raw tables.
    """
    db = quote_ident(db_name)
    execute(cur, f"CREATE USER IF NOT EXISTS '{username}'@'%%' IDENTIFIED BY %s;", (password,))
    execute(cur, f"GRANT SELECT ON {db}.agent_performance TO '{username}'@'%';")
    execute(cur, f"GRANT SELECT ON {db}.tool_usage_stats TO '{username}'@'%';")
    execute(cur, f"GRANT SELECT ON {db}.daily_sessions TO '{username}'@'%';")
    print_step(f"Created Quick BI reader user restricted to views: {username}")


def upsert_platform_tenant(
    cur: Cursor,
    tenant_id: str,
    db_name: str,
    db_user: str,
    db_password: str,
) -> None:
    execute(
        cur,
        """
        INSERT INTO `platform`.`tenants` (
            tenant_id,
            db_name,
            db_user,
            db_password,
            is_active
        )
        VALUES (%s, %s, %s, %s, 1)
        ON DUPLICATE KEY UPDATE
            db_name = VALUES(db_name),
            db_user = VALUES(db_user),
            db_password = VALUES(db_password),
            is_active = 1;
        """,
        (tenant_id, db_name, db_user, db_password),
    )
    print_step(f"Recorded tenant in platform registry: {tenant_id}")


def enable_tiflash(cur: Cursor, db_name: str) -> None:
    """
    The brief requires TiFlash on analytical tables.
    For AgentNexus, practical choices are agents, sessions, tool_calls.
    """
    db = quote_ident(db_name)
    analytical_tables = ["agents", "sessions", "tool_calls"]

    for table in analytical_tables:
        sql = f"ALTER TABLE {db}.{quote_ident(table)} SET TIFLASH REPLICA 1;"
        try:
            execute(cur, sql)
            print_step(f"Requested TiFlash replica for {db_name}.{table}")
        except Exception as exc:
            print(f"[!] Could not enable TiFlash on {db_name}.{table}: {exc}")


def wait_for_tiflash(cfg: Config, db_name: str, timeout_sec: int = 300, poll_sec: int = 5) -> None:
    """
    Poll information_schema.tiflash_replica until analytical tables are AVAILABLE = 1.
    """
    deadline = time.time() + timeout_sec
    target_tables = {"agents", "sessions", "tool_calls"}

    with connect_admin(cfg) as conn:
        with conn.cursor() as cur:
            while time.time() < deadline:
                execute(cur, """
                    SELECT TABLE_NAME, REPLICA_COUNT, AVAILABLE
                    FROM information_schema.tiflash_replica
                    WHERE TABLE_SCHEMA = %s
                """, (db_name,))
                rows = cur.fetchall()

                status = {row[0]: {"replica_count": row[1], "available": row[2]} for row in rows}
                ready = all(
                    table in status and status[table]["replica_count"] >= 1 and status[table]["available"] == 1
                    for table in target_tables
                )

                print(f"[*] TiFlash status for {db_name}: {status}")

                if ready:
                    print_step(f"TiFlash replicas are AVAILABLE = 1 for all target tables in {db_name}")
                    return

                time.sleep(poll_sec)

    raise TimeoutError(f"Timed out waiting for TiFlash replicas on {db_name}")


def show_verification(cur: Cursor, db_name: str, tenant_db_user: str) -> None:
    print("\n=== Verification Commands ===")
    print(f"-- Login as tenant user: {tenant_db_user}")
    print("SHOW DATABASES;")
    print(f"USE {db_name};")
    print("SHOW TABLES;")
    print("SELECT * FROM agent_performance LIMIT 5;")
    print("SELECT * FROM tool_usage_stats LIMIT 5;")
    print("SELECT * FROM daily_sessions LIMIT 5;")
    print("=============================\n")


# -----------------------------
# Optional: resource group hook
# -----------------------------

def maybe_create_resource_group(cur: Cursor, tenant: str, ru_per_sec: Optional[int]) -> None:
    """
    The brief mentions creating a resource group per tenant, but actual support / syntax can depend
    on the TiDB edition or privileges available in the hackathon cluster.

    This function is intentionally OFF unless you pass --resource-group-ru.
    Adjust the SQL if your cluster requires a different syntax.
    """
    if ru_per_sec is None:
        return

    rg_name = f"rg_tenant_{tenant}"
    try:
        # Common TiDB syntax pattern; adjust if your event cluster differs.
        execute(cur, f"CREATE RESOURCE GROUP IF NOT EXISTS {quote_ident(rg_name)} RU_PER_SEC = {int(ru_per_sec)};")
        print_step(f"Created resource group: {rg_name} with RU_PER_SEC={ru_per_sec}")
    except Exception as exc:
        print(f"[!] Resource group creation skipped/failed for {rg_name}: {exc}")
        print("[!] Keep going. If your judge environment supports resource groups, adjust this SQL to your cluster version.")


# -----------------------------
# Main provisioning flow
# -----------------------------

def provision_tenant(
    cfg: Config,
    raw_tenant: str,
    tenant_password: Optional[str],
    quickbi_password: Optional[str],
    with_tiflash: bool,
    wait_tiflash_flag: bool,
    with_quickbi_user: bool,
    resource_group_ru: Optional[int],
) -> None:
    tenant = sanitize_tenant_name(raw_tenant)
    db_name = database_name(tenant)
    full_user_prefix = user_prefix(cfg.admin_user, cfg.cluster_prefix)
    app_user = tenant_username(full_user_prefix, tenant)
    app_password = tenant_password or generate_password()

    qbi_user = quickbi_username(full_user_prefix, tenant)
    qbi_password = quickbi_password or generate_password()

    print_step(f"Provisioning tenant: {tenant}")
    print_step(f"Target database: {db_name}")

    with connect_admin(cfg) as conn:
        with conn.cursor() as cur:
            create_platform_db(cur)
            create_platform_tables(cur)
            create_tenant_database(cur, db_name)
            create_tables(cur, db_name)
            create_views(cur, db_name)
            create_tenant_user(cur, app_user, app_password, db_name)
            upsert_platform_tenant(cur, tenant, db_name, app_user, app_password)

            if with_quickbi_user:
                create_quickbi_user(cur, qbi_user, qbi_password, db_name)

            maybe_create_resource_group(cur, tenant, resource_group_ru)

            if with_tiflash:
                enable_tiflash(cur, db_name)

            execute(cur, "FLUSH PRIVILEGES;")

    if with_tiflash and wait_tiflash_flag:
        wait_for_tiflash(cfg, db_name)

    print("\n=== Provisioning Result ===")
    print(f"tenant_name      = {tenant}")
    print(f"database         = {db_name}")
    print(f"tenant_db_user   = {app_user}")
    print(f"tenant_db_pass   = {app_password}")
    if with_quickbi_user:
        print(f"quickbi_user     = {qbi_user}")
        print(f"quickbi_pass     = {qbi_password}")
    print("===========================\n")

    with connect_admin(cfg) as conn:
        with conn.cursor() as cur:
            show_verification(cur, db_name, app_user)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provision one AgentNexus tenant in TiDB.")
    parser.add_argument("tenant", help="Tenant short name, e.g. acme, globex, initech")
    parser.add_argument("--password", help="Optional password for the tenant DB user")
    parser.add_argument("--with-quickbi-user", action="store_true", help="Also create a Quick BI read-only user for this tenant")
    parser.add_argument("--quickbi-password", help="Optional password for the Quick BI user")
    parser.add_argument("--with-tiflash", action="store_true", help="Enable TiFlash replicas on analytical tables")
    parser.add_argument("--wait-tiflash", action="store_true", help="Poll until TiFlash replicas are AVAILABLE = 1")
    parser.add_argument(
        "--resource-group-ru",
        type=int,
        default=None,
        help="Optional RU_PER_SEC for a resource group. Leave unset if unsupported in your cluster."
    )
    return parser


def main() -> int:
    try:
        cfg = load_config()
        parser = build_arg_parser()
        args = parser.parse_args()

        provision_tenant(
            cfg=cfg,
            raw_tenant=args.tenant,
            tenant_password=args.password,
            quickbi_password=args.quickbi_password,
            with_tiflash=args.with_tiflash,
            wait_tiflash_flag=args.wait_tiflash,
            with_quickbi_user=args.with_quickbi_user,
            resource_group_ru=args.resource_group_ru,
        )
        return 0

    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
