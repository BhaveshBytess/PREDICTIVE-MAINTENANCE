"""
FastAPI Application — Ingestion & Validation API

Phase 3: Gates all sensor data through strict contracts.

CORS: Configured via environment variables.
"""

import logging
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
# For Vercel deployments, we use allow_origin_regex to match all vercel.app subdomains
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Match all Vercel preview deployments
    allow_credentials=True,
    allow_methods=["GET", "POST"],
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
