"""
Operator Log Routes — Ground Truth for ML Training

Provides endpoints for operators to log maintenance events that can be
correlated with sensor data for supervised learning.

Measurement: maintenance_logs (in sensor_data bucket)
Tags: asset_id, event_type, severity (indexed for fast queries)
Fields: description (unindexed text)
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from backend.database import db


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/log", tags=["Operator Logs"])


# =============================================================================
# ENUMS — Strict ML Data Quality
# =============================================================================

class EventType(str, Enum):
    """
    Allowed maintenance event types for ML classification.
    
    PREVENTIVE: Scheduled maintenance activities
    CORRECTIVE: Repair/replacement activities  
    STATUS: System state changes
    """
    # Preventive maintenance
    PREVENTIVE_LUBRICATION = "PREVENTIVE_LUBRICATION"
    PREVENTIVE_CLEANING = "PREVENTIVE_CLEANING"
    PREVENTIVE_INSPECTION = "PREVENTIVE_INSPECTION"
    
    # Corrective maintenance
    CORRECTIVE_BEARING_REPLACEMENT = "CORRECTIVE_BEARING_REPLACEMENT"
    CORRECTIVE_ALIGNMENT = "CORRECTIVE_ALIGNMENT"
    CORRECTIVE_ELECTRICAL = "CORRECTIVE_ELECTRICAL"
    
    # Status changes
    STATUS_CALIBRATION = "STATUS_CALIBRATION"
    STATUS_RESTART = "STATUS_RESTART"


class Severity(str, Enum):
    """Severity levels for maintenance events."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class LogEntryRequest(BaseModel):
    """
    Operator maintenance log entry.
    
    Used for ground-truth labeling in supervised ML training.
    Events are stored in InfluxDB for correlation with sensor data.
    """
    asset_id: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="Asset identifier (e.g., 'Motor-01')"
    )
    event_type: EventType = Field(
        ...,
        description="Maintenance event classification"
    )
    severity: Severity = Field(
        ...,
        description="Event severity level"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Human-readable description of the maintenance activity"
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Event timestamp (defaults to now). Allows backdating for historical entries."
    )
    
    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, v):
        """Parse timestamp and ensure UTC."""
        if v is None:
            return None
        if isinstance(v, datetime):
            # Ensure timezone-aware
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        # If string, let Pydantic handle parsing
        return v
    
    @field_validator('asset_id')
    @classmethod
    def validate_asset_id(cls, v: str) -> str:
        """Normalize asset_id."""
        return v.strip()
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Normalize description."""
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "asset_id": "Motor-01",
                "event_type": "CORRECTIVE_BEARING_REPLACEMENT",
                "severity": "HIGH",
                "description": "Replaced main bearing due to excessive vibration. Part #SKF-6205-2RS.",
                "timestamp": "2026-01-31T10:30:00Z"
            }
        }


class LogEntryResponse(BaseModel):
    """Response after successfully creating a log entry."""
    event_id: str = Field(..., description="Unique identifier for this log entry")
    asset_id: str = Field(..., description="Asset that was logged")
    event_type: str = Field(..., description="Type of maintenance event")
    severity: str = Field(..., description="Severity level")
    timestamp: datetime = Field(..., description="Timestamp of the event")
    message: str = Field(..., description="Confirmation message")


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post(
    "",
    response_model=LogEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log maintenance event",
    description="Record a maintenance event for ML ground-truth labeling. "
                "Events are stored in InfluxDB and can be correlated with sensor data."
)
async def create_log_entry(entry: LogEntryRequest) -> LogEntryResponse:
    """
    Create a maintenance log entry.
    
    This endpoint allows operators to record maintenance events that serve as
    ground-truth labels for supervised machine learning. Events are stored in
    the `maintenance_logs` measurement within the `sensor_data` bucket.
    
    **Use Cases:**
    - Log bearing replacements to correlate with vibration anomalies
    - Record lubrication events to track maintenance effectiveness
    - Document electrical repairs for failure pattern analysis
    
    **ML Integration:**
    Events can be queried alongside sensor data to train supervised models
    that predict failure modes based on sensor patterns.
    """
    # Generate unique event ID
    event_id = str(uuid.uuid4())
    
    # Use provided timestamp or default to now (UTC)
    event_timestamp = entry.timestamp or datetime.now(timezone.utc)
    
    # Ensure timestamp is UTC
    if event_timestamp.tzinfo is None:
        event_timestamp = event_timestamp.replace(tzinfo=timezone.utc)
    
    # Prepare InfluxDB point
    tags = {
        "asset_id": entry.asset_id,
        "event_type": entry.event_type.value,
        "severity": entry.severity.value,
    }
    
    fields = {
        "description": entry.description,
        "event_id": event_id,
    }
    
    # Write to InfluxDB
    try:
        success = db.write_point(
            measurement="maintenance_logs",
            tags=tags,
            fields=fields,
            timestamp=event_timestamp
        )
        
        if not success:
            logger.error(f"Failed to write maintenance log for {entry.asset_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist log entry to database"
            )
        
        logger.info(
            f"✅ Maintenance log created: {event_id} | "
            f"{entry.asset_id} | {entry.event_type.value} | {entry.severity.value}"
        )
        
        return LogEntryResponse(
            event_id=event_id,
            asset_id=entry.asset_id,
            event_type=entry.event_type.value,
            severity=entry.severity.value,
            timestamp=event_timestamp,
            message=f"Log entry created successfully for {entry.asset_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating maintenance log: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )


@router.get(
    "/types",
    summary="List allowed event types",
    description="Returns all valid event_type values for the log endpoint."
)
async def list_event_types():
    """
    Get all allowed event types.
    
    Useful for populating dropdowns in the frontend.
    """
    return {
        "event_types": [
            {
                "value": e.value,
                "category": e.value.split("_")[0],
                "label": e.value.replace("_", " ").title()
            }
            for e in EventType
        ],
        "severities": [s.value for s in Severity]
    }
