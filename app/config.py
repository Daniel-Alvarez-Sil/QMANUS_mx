"""
app/config.py — All environment variable bindings.

This is the only file allowed to call os.getenv().
Every other module imports constants from here.
"""

import os

# ── TiDB ──────────────────────────────────────────────────────────────────────
TIDB_HOST: str = os.getenv("TIDB_HOST", "localhost")
TIDB_PORT: int = int(os.getenv("TIDB_PORT", "4000"))
TIDB_USER: str = os.getenv("TIDB_USER") or os.getenv("TIDB_ADMIN_USER", "root")
TIDB_PASS: str = os.getenv("TIDB_PASS") or os.getenv("TIDB_PASSWORD") or os.getenv("TIDB_ADMIN_PASSWORD", "")
TIDB_DB:   str = os.getenv("TIDB_DB",   os.getenv("TIDB_DATABASE", "agentnexus"))
# Enable SSL for TiDB Cloud (required). Set TIDB_SSL=0 only for local plaintext instances.
TIDB_SSL:  bool = os.getenv("TIDB_SSL", "1").lower() not in {"0", "false", "no"}

# ── Auth ───────────────────────────────────────────────────────────────────────
_JWT_SECRET_DEFAULT = "changeme-set-a-real-secret"
JWT_SECRET: str = os.getenv("JWT_SECRET", _JWT_SECRET_DEFAULT)
if JWT_SECRET == _JWT_SECRET_DEFAULT or len(JWT_SECRET) < 32:
    raise RuntimeError(
        "JWT_SECRET must be set to a random string of at least 32 characters. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

# Secret required to call the token-minting endpoint (POST /api/v1/auth/token).
# Set PROVISIONING_SECRET to a strong random value; if unset the endpoint is disabled.
PROVISIONING_SECRET: str | None = os.getenv("PROVISIONING_SECRET") or None

# ── Qwen / DashScope ──────────────────────────────────────────────────────────
# None when unset → routes fall back to mock analysis
DASHSCOPE_API_KEY: str | None = os.getenv("DASHSCOPE_API_KEY") or None
