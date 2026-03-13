"""
app/app.py — FastAPI application factory.

This is the only file that imports from every layer.
Responsibility: wire middleware + routers onto the FastAPI instance.
Nothing else belongs here.
"""

import logging

from fastapi import FastAPI

from app.lifespan import lifespan
from app.middleware import tenant_middleware
from app.routes.agents import router as agents_router
from app.routes.auth import router as auth_router
from app.routes.health import router as health_router
from app.routes.meta_agent import router as meta_agent_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

app = FastAPI(
    title="AgentNexus",
    description="Multi-tenant agentic AI platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware is registered BEFORE routers so every request is authenticated
app.middleware("http")(tenant_middleware)

app.include_router(health_router)
app.include_router(agents_router)
app.include_router(meta_agent_router)
app.include_router(auth_router)
