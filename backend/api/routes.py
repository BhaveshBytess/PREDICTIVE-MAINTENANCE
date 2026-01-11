"""
API Routes — Endpoint Definitions

All handlers are async per user mandate.
"""

from fastapi import APIRouter, HTTPException, status, Depends

from backend.storage import SensorEventWriter, InfluxDBClientError

from .schemas import (
    SensorEventRequest,
    SensorEventResponse,
    SignalsOutput,
    HealthResponse,
)
from .services import ingest_event, check_database_health


router = APIRouter()


# Dependency for database client
def get_db_client() -> SensorEventWriter:
    """
    Dependency that provides a connected InfluxDB client.
    
    In production, this would use connection pooling.
    """
    client = SensorEventWriter()
    try:
        client.connect()
        yield client
    finally:
        client.disconnect()


@router.post(
    "/ingest",
    response_model=SensorEventResponse,
    status_code=status.HTTP_200_OK,
    responses={
        422: {"description": "Validation error (invalid payload)"},
        503: {"description": "Database unavailable"},
    },
    summary="Ingest a single sensor event",
    description="Validates, computes derived signals, and persists to InfluxDB."
)
async def ingest_sensor_event(
    request: SensorEventRequest,
    client: SensorEventWriter = Depends(get_db_client)
) -> SensorEventResponse:
    """
    Ingest a single sensor event.
    
    - Validates all fields against schema
    - Rejects power_kw if provided by client
    - Computes power_kw server-side
    - Persists to InfluxDB
    """
    try:
        # Build dicts from request
        asset_dict = {
            "asset_id": request.asset.asset_id,
            "asset_type": request.asset.asset_type
        }
        signals_dict = {
            "voltage_v": request.signals.voltage_v,
            "current_a": request.signals.current_a,
            "power_factor": request.signals.power_factor,
            "vibration_g": request.signals.vibration_g
        }
        context_dict = {
            "operating_state": request.context.operating_state,
            "source": request.context.source
        }
        
        # Ingest with computed power_kw
        complete_event = await ingest_event(
            event_id=request.event_id,
            timestamp=request.timestamp,
            asset=asset_dict,
            signals=signals_dict,
            context=context_dict,
            client=client
        )
        
        # Build response
        return SensorEventResponse(
            status="accepted",
            event_id=complete_event["event_id"],
            timestamp=complete_event["timestamp"],
            asset=request.asset,
            signals=SignalsOutput(**complete_event["signals"]),
            context=request.context,
            message="Event ingested successfully"
        )
        
    except InfluxDBClientError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {str(e)}"
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        200: {"description": "All systems healthy"},
        503: {"description": "Database unavailable"},
    },
    summary="Health check",
    description="Checks API and database health."
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Pings InfluxDB and returns 503 if unreachable.
    """
    client = SensorEventWriter()
    
    try:
        client.connect()
        is_healthy = await check_database_health(client)
        client.disconnect()
        
        if is_healthy:
            return HealthResponse(
                status="healthy",
                database="connected",
                message="All systems operational"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database health check failed"
            )
            
    except InfluxDBClientError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot connect to database"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )
