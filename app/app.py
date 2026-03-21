"""
app/app.py — FastAPI application factory.

This is the only file that imports from every layer.
Responsibility: wire middleware + routers onto the FastAPI instance.
Nothing else belongs here.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.lifespan import lifespan
from app.middleware import tenant_middleware
from app.routes.agents import router as agents_router
from app.routes.auth import router as auth_router
from app.routes.health import router as health_router
from app.routes.insights import router as insights_router
from app.routes.meta_agent import router as meta_agent_router
from app.routes.sessions import router as sessions_router

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

# tenant_middleware must be registered first (inner) so that CORSMiddleware
# (registered last, therefore outermost) runs before auth on every request.
# This ensures CORS headers are present even on 401 responses, and that
# OPTIONS preflight requests receive a proper 200 without hitting auth.
app.middleware("http")(tenant_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(agents_router)
app.include_router(insights_router)
app.include_router(meta_agent_router)
app.include_router(auth_router)
app.include_router(sessions_router)
