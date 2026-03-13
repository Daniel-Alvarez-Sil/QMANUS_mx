"""
app/middleware.py — Tenant authentication middleware.

Every non-exempt request must carry:
  - X-Tenant-ID: <tenant>        header
  - Authorization: Bearer <jwt>  header  (HS256, payload must contain 'tid')

The JWT 'tid' claim must match X-Tenant-ID exactly; any mismatch returns
HTTP 401 {"error": "unauthorized", "code": "TENANT_MISMATCH"}.

On success the validated tenant_id is injected into ctx_tenant for the
lifetime of the request, then cleanly reset in a finally block so the
ContextVar is never visible to later coroutines reusing the same task.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt

from app.config import JWT_SECRET
from app.context import ctx_tenant

# Paths that bypass authentication entirely
_EXEMPT_PATHS = frozenset({"/", "/health", "/docs", "/redoc", "/openapi.json"})

_MISMATCH = JSONResponse(
    status_code=401,
    content={"error": "unauthorized", "code": "TENANT_MISMATCH"},
)


async def tenant_middleware(request: Request, call_next):  # type: ignore[type-arg]
    if request.url.path in _EXEMPT_PATHS:
        return await call_next(request)

    tenant_header = request.headers.get("X-Tenant-ID", "").strip()
    auth_header   = request.headers.get("Authorization", "").strip()

    if not tenant_header or not auth_header.startswith("Bearer "):
        return _MISMATCH

    token = auth_header[len("Bearer "):]

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        return _MISMATCH

    if payload.get("tid", "") != tenant_header:
        return _MISMATCH

    ctx_token = ctx_tenant.set(tenant_header)
    try:
        return await call_next(request)
    finally:
        ctx_tenant.reset(ctx_token)
