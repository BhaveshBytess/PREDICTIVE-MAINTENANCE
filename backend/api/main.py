"""
FastAPI Application — Ingestion & Validation API

Phase 3: Gates all sensor data through strict contracts.

CORS: Configured via environment variables.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from .routes import router
from .integration_routes import router as integration_router
from .system_routes import router as system_router
from .sandbox_routes import router as sandbox_router
from .operator_routes import router as operator_router


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Environment Validation ──────────────────────────────────────────────
# Check the resolved settings (pydantic-settings loads from .env + OS env)
_missing_env = []
if not settings.INFLUX_URL or settings.INFLUX_URL == "http://localhost:8086":
    # Only warn if it's still the default AND no env/dotenv override was set
    if not os.environ.get("INFLUXDB_URL") and not os.environ.get("INFLUX_URL"):
        _missing_env.append("INFLUX_URL")
if not settings.INFLUX_TOKEN:
    _missing_env.append("INFLUX_TOKEN")
if _missing_env:
    logger.warning(
        "\n" + "=" * 60
        + "\n  MISSING ENVIRONMENT VARIABLES\n"
        + "\n".join(f"  - {v}" for v in _missing_env)
        + "\n  Set them in .env or export before starting."
        + "\n" + "=" * 60
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info(f"🚀 Starting {settings.PROJECT_NAME}")
    logger.info(f"📍 Running in {settings.ENVIRONMENT} mode")
    logger.info(f"🔗 InfluxDB: {settings.INFLUX_URL}")
    yield
    # Shutdown
    logger.info(f"👋 Shutting down {settings.PROJECT_NAME}")


# Application metadata
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Sensor data ingestion and validation API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# CORS Configuration — loaded from settings
# Ensures localhost + 127.0.0.1 always work (migration-safe), plus Vercel previews
_cors_origins = list(set(settings.CORS_ORIGINS + [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Match all Vercel preview deployments
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# Include API routes
app.include_router(router, tags=["Ingestion"])
app.include_router(integration_router)
app.include_router(system_router)
app.include_router(sandbox_router)
app.include_router(operator_router)


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint — redirects to docs."""
    return {
        "message": "Predictive Maintenance API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/ping", tags=["Health"])
async def ping():
    """Lightweight heartbeat — no DB, no ML. Used by keep-alive pings."""
    return {"status": "ok"}
