try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional, env vars can be set directly

"""
USAGE:
  from db import pool_manager, execute_tiflash, check_tidb_health

  # Simple query with tenant isolation
  rows = await pool_manager.execute(
      tenant_id="ent-A",
      sql="SELECT * FROM agent_sessions WHERE tenant_id = %s AND status = %s",
      args=("ent-A", "running")
  )

  # Write operation
  count = await pool_manager.execute_write(
      tenant_id="ent-A",
      sql="INSERT INTO agent_sessions (session_id, tenant_id, agent_type, status) VALUES (%s,%s,%s,%s)",
      args=(session_id, "ent-A", "research", "planning")
  )

  # Analytical query via TiFlash
  stats = await execute_tiflash(
      tenant_id="ent-A",
      sql="SELECT agent_type, COUNT(*) as cnt FROM agent_sessions WHERE tenant_id = %s GROUP BY agent_type",
      args=("ent-A",)
  )

  # Health check
  health = await check_tidb_health()

  # Shutdown (call on app exit)
  await pool_manager.close_all()

  # Run connection test:
  python db.py
"""

import asyncio
import logging
import os
import ssl
from contextlib import asynccontextmanager

import aiomysql

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] TiDB | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("tidb")

# ---------------------------------------------------------------------------
# Part 2: SSL context — created once at module level, reused for all pools
# ---------------------------------------------------------------------------

def _build_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx

ssl_ctx = _build_ssl_ctx()

# ---------------------------------------------------------------------------
# Part 1: Connection Pool Manager
# ---------------------------------------------------------------------------

class TiDBPoolManager:
    """
    Manages per-tenant aiomysql connection pools against TiDB Cloud.

    Each unique tenant_id gets its own pool so connection limits and
    lifecycle can be tracked independently.  Pool creation is protected
    by an asyncio.Lock to avoid duplicate-creation races.
    """

    def __init__(self) -> None:
        self._pools: dict[str, aiomysql.Pool] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Pool management
    # ------------------------------------------------------------------

    async def get_pool(self, tenant_id: str) -> aiomysql.Pool:
        """Return an existing pool or create a new one for *tenant_id*."""
        if tenant_id in self._pools:
            return self._pools[tenant_id]

        async with self._lock:
            # Double-checked locking: another coroutine may have created it
            # while we were waiting for the lock.
            if tenant_id in self._pools:
                return self._pools[tenant_id]

            host = os.getenv("TIDB_HOST")
            port = int(os.getenv("TIDB_PORT", 4000))
            user = os.getenv("TIDB_USER")
            password = os.getenv("TIDB_PASS")
            db = os.getenv("TIDB_DB", "agentnexus")

            logger.info(
                "Creating pool for tenant=%s  host=%s:%s  db=%s",
                tenant_id, host, port, db,
            )

            pool = await aiomysql.create_pool(
                host=host,
                port=port,
                user=user,
                password=password,
                db=db,
                minsize=1,
                maxsize=10,
                ssl=ssl_ctx,
                autocommit=True,
                connect_timeout=10,
                echo=False,
            )

            self._pools[tenant_id] = pool
            logger.info("Pool ready for tenant=%s", tenant_id)
            return pool

    # ------------------------------------------------------------------
    # Context-manager connection acquisition
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def get_conn(self, tenant_id: str):
        """
        Async context manager that yields a connection from the pool.

        Usage::

            async with pool_manager.get_conn("ent-A") as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT 1")
        """
        pool = await self.get_pool(tenant_id)
        conn = None
        try:
            conn = await pool.acquire()
            logger.info("Connection acquired for tenant=%s", tenant_id)
            yield conn
        except Exception:
            logger.error(
                "Connection error for tenant=%s", tenant_id, exc_info=True
            )
            raise
        finally:
            if conn is not None:
                pool.release(conn)

    # ------------------------------------------------------------------
    # Read helper
    # ------------------------------------------------------------------

    async def execute(
        self,
        tenant_id: str,
        sql: str,
        args=None,
    ) -> list[dict]:
        """
        Execute a SELECT (or any read) statement and return rows as dicts.

        Always use %s placeholders — never interpolate values into *sql*
        directly.  A WARNING is logged when 'tenant_id' is absent from
        the SQL text, which may indicate a missing tenant-isolation filter.
        """
        if "tenant_id" not in sql.lower():
            logger.warning(
                "SQL for tenant=%s does not reference 'tenant_id' — "
                "verify that tenant isolation is enforced: %s",
                tenant_id, sql,
            )

        async with self.get_conn(tenant_id) as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, args)
                rows = await cur.fetchall()
                return list(rows) if rows else []

    # ------------------------------------------------------------------
    # Write helper
    # ------------------------------------------------------------------

    async def execute_write(
        self,
        tenant_id: str,
        sql: str,
        args=None,
    ) -> int:
        """
        Execute an INSERT / UPDATE / DELETE statement.

        Returns the number of affected rows (cursor.rowcount).
        """
        if "tenant_id" not in sql.lower():
            logger.warning(
                "Write SQL for tenant=%s does not reference 'tenant_id' — "
                "verify that tenant isolation is enforced: %s",
                tenant_id, sql,
            )

        async with self.get_conn(tenant_id) as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, args)
                return cur.rowcount

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def close_all(self) -> None:
        """Close every managed pool and clear the internal registry."""
        for tenant_id, pool in list(self._pools.items()):
            pool.close()
            await pool.wait_closed()
            logger.info("Pool closed for tenant=%s", tenant_id)
        self._pools.clear()
        logger.info("All TiDB pools closed")


# Module-level singleton
pool_manager = TiDBPoolManager()

# ---------------------------------------------------------------------------
# Part 3: Health check
# ---------------------------------------------------------------------------

async def check_tidb_health() -> dict:
    """
    Verify connectivity to TiDB Cloud.

    Returns a dict with ``"status": "ok"`` on success or
    ``"status": "error"`` with a ``"message"`` key on failure.
    """
    try:
        rows = await pool_manager.execute(
            tenant_id="__health__",
            sql="SELECT VERSION() AS version, NOW() AS server_time",
            # NOTE: health check SQL intentionally has no tenant_id filter;
            # the warning is expected and harmless here.
        )
        row = rows[0] if rows else {}
        return {
            "status": "ok",
            "tidb_version": str(row.get("version", "unknown")),
            "server_time": str(row.get("server_time", "unknown")),
            "host": os.getenv("TIDB_HOST"),
            "database": os.getenv("TIDB_DB"),
        }
    except Exception as exc:
        logger.error("Health check failed: %s", exc, exc_info=True)
        return {
            "status": "error",
            "message": str(exc),
            "host": os.getenv("TIDB_HOST"),
        }

# ---------------------------------------------------------------------------
# Part 4: TiFlash query helper
# ---------------------------------------------------------------------------

_TIFLASH_HINT = (
    "/*+ READ_FROM_STORAGE(tiflash[agent_sessions, tool_call_history]) */ "
)


async def execute_tiflash(
    tenant_id: str,
    sql: str,
    args=None,
) -> list[dict]:
    """
    Run a SELECT query routed to TiFlash replicas for OLAP workloads.

    The TiFlash optimizer hint is injected automatically.  If TiFlash is
    unavailable the query is transparently retried against TiKV (the
    row-store engine) so callers never need to handle the fallback.

    Raises
    ------
    ValueError
        When *sql* is not a SELECT statement.
    """
    stripped = sql.lstrip()
    if not stripped.upper().startswith("SELECT"):
        raise ValueError("execute_tiflash only supports SELECT queries")

    # Insert hint after the SELECT keyword (preserving any leading whitespace
    # that preceded the keyword so the statement stays syntactically valid).
    offset = sql.index(stripped[0])          # position of 'S' in SELECT
    hint_sql = sql[:offset + 6] + " " + _TIFLASH_HINT + sql[offset + 7:]

    try:
        return await pool_manager.execute(tenant_id, hint_sql, args)
    except Exception as exc:
        logger.warning(
            "TiFlash unavailable (tenant=%s), falling back to TiKV: %s",
            tenant_id, exc,
        )
        return await pool_manager.execute(tenant_id, sql, args)

# ---------------------------------------------------------------------------
# Part 7: __main__ test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    async def test() -> None:
        print("\n=== TiDB Cloud Connection Test ===\n")

        # Test 1: Health check
        health = await check_tidb_health()
        print(f"Health: {health}")

        # Test 2: Create test table
        await pool_manager.execute_write("__test__", """
            CREATE TABLE IF NOT EXISTS connection_test (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                tenant_id  VARCHAR(36),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ Table created")

        # Test 3: Insert row
        rows = await pool_manager.execute_write(
            "__test__",
            "INSERT INTO connection_test (tenant_id) VALUES (%s)",
            args=("__test__",),
        )
        print(f"✓ Insert rowcount: {rows}")

        # Test 4: Read row back
        results = await pool_manager.execute(
            "__test__",
            "SELECT * FROM connection_test WHERE tenant_id = %s",
            args=("__test__",),
        )
        print(f"✓ Read results: {results}")

        # Test 5: TiFlash helper (will fallback gracefully if replica not ready)
        try:
            tf_results = await execute_tiflash(
                "__test__",
                "SELECT COUNT(*) AS cnt FROM connection_test WHERE tenant_id = %s",
                args=("__test__",),
            )
            print(f"✓ TiFlash query: {tf_results}")
        except Exception as exc:
            print(f"⚠ TiFlash test skipped: {exc}")

        # Cleanup
        await pool_manager.close_all()
        print("\n=== All tests passed ✓ ===\n")

    asyncio.run(test())
