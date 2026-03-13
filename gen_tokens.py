"""
gen_tokens.py — Generate test JWT tokens for local API calls.

Usage:
    python gen_tokens.py

Each token encodes a 'tid' claim that must match the X-Tenant-ID header
sent with every request (see app/middleware.py).

Reads JWT_SECRET from .env (falls back to the placeholder if not set).
"""

import os
from pathlib import Path

# ── load .env manually (no extra deps needed) ─────────────────────────────────
_env = {}
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            _env[k.strip()] = v.strip()

SECRET = _env.get("JWT_SECRET", "changeme-replace-with-a-long-random-secret")

# ── tenants to generate tokens for ────────────────────────────────────────────
TENANTS = [
    "enterprise-A",
    "enterprise-B",
    "startup-X",
]

# ── generate ──────────────────────────────────────────────────────────────────
try:
    from jose import jwt
except ImportError:
    raise SystemExit("python-jose is not installed. Run: pip install python-jose")

print(f"JWT_SECRET : {SECRET}\n")
print(f"{'Tenant':<20}  Token")
print("-" * 80)

for tid in TENANTS:
    token = jwt.encode({"tid": tid}, SECRET, algorithm="HS256")
    print(f"{tid:<20}  {token}")

print()
print("-- Example curl --")
example_tid = TENANTS[0]
example_tok = jwt.encode({"tid": example_tid}, SECRET, algorithm="HS256")
print(f'curl -s http://localhost:8000/agents \\\n'
      f'  -H "X-Tenant-ID: {example_tid}" \\\n'
      f'  -H "Authorization: Bearer {example_tok}" | python -m json.tool')
