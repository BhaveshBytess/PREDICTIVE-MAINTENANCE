"""
API Module — FastAPI Ingestion & Validation (Phase 3)

Public API:
- app: FastAPI application instance
- router: API routes
"""

from .main import app
from .routes import router
from .schemas import SensorEventRequest, SensorEventResponse

__all__ = [
    "app",
    "router",
    "SensorEventRequest",
    "SensorEventResponse",
]
