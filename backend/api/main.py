"""
FastAPI Application — Ingestion & Validation API

Phase 3: Gates all sensor data through strict contracts.

CORS: Restricted to localhost origins only (no wildcard).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from .integration_routes import router as integration_router


# Application metadata
app = FastAPI(
    title="Predictive Maintenance API",
    description="Sensor data ingestion and validation API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# CORS Configuration — Restricted to localhost only
# Per user mandate: Do NOT use allow_origins=["*"]
ALLOWED_ORIGINS = [
    "http://localhost:3000",      # React dev server (primary)
    "http://localhost:3001",      # React dev server (alternate)
    "http://localhost:5173",      # Vite dev server
    "http://localhost:8080",      # Alternative frontend port
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


# Include API routes
app.include_router(router, tags=["Ingestion"])
app.include_router(integration_router)


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint — redirects to docs."""
    return {
        "message": "Predictive Maintenance API",
        "docs": "/docs",
        "health": "/health"
    }
