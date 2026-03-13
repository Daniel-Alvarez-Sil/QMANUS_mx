"""
app/context.py — Async-task-local tenant identity.

`ctx_tenant` is the single source of truth for the authenticated tenant
in the current request. It is:
  - written once by tenant_middleware after JWT validation
  - read by every route handler and DB helper — never from user input

No local imports: this module sits at the very bottom of the dependency
graph so middleware and route modules can both import it without cycles.
"""

from contextvars import ContextVar

ctx_tenant: ContextVar[str] = ContextVar("ctx_tenant", default="")
