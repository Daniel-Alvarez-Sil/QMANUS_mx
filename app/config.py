"""
app/config.py — All environment variable bindings.

This is the only file allowed to call os.getenv().
Every other module imports constants from here.
"""

import os

# ── TiDB ──────────────────────────────────────────────────────────────────────
TIDB_HOST: str = os.getenv("TIDB_HOST", "localhost")
TIDB_PORT: int = int(os.getenv("TIDB_PORT", "4000"))
TIDB_USER: str = os.getenv("TIDB_USER", "root")
TIDB_PASS: str = os.getenv("TIDB_PASS", os.getenv("TIDB_PASSWORD", ""))
TIDB_DB:   str = os.getenv("TIDB_DB",   os.getenv("TIDB_DATABASE", "agentnexus"))

# ── Auth ───────────────────────────────────────────────────────────────────────
JWT_SECRET: str = os.getenv("JWT_SECRET", "changeme-set-a-real-secret")

# ── Qwen / DashScope ──────────────────────────────────────────────────────────
# None when unset → routes fall back to mock analysis
DASHSCOPE_API_KEY: str | None = os.getenv("DASHSCOPE_API_KEY") or None
