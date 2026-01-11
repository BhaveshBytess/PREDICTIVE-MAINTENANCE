"""
Pydantic Schemas — API Request/Response Models

Strict validation for sensor event ingestion per CONTRACTS.md.

Constraints:
- power_kw: REJECTED if provided by client (server computes)
- event_id: Must be valid UUIDv4
- timestamp: Must be timezone-aware UTC
- power_factor: Must be 0.0-1.0
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class AssetInput(BaseModel):
    """Asset identification."""
    asset_id: str = Field(..., min_length=1, description="Unique asset identifier")
    asset_type: str = Field(..., min_length=1, description="Asset type (e.g., induction_motor)")


class SignalsInput(BaseModel):
    """
    Raw sensor signals for ingestion.
    
    Note: power_kw is NOT accepted from clients - it's computed server-side.
    """
    voltage_v: float = Field(..., ge=0, description="Voltage in Volts")
    current_a: float = Field(..., ge=0, description="Current in Amperes")
    power_factor: float = Field(..., ge=0.0, le=1.0, description="Power factor (0.0-1.0)")
    vibration_g: float = Field(..., ge=0, description="Vibration in g")
    
    # power_kw is explicitly forbidden in input
    power_kw: Optional[float] = Field(
        default=None,
        description="NOT ALLOWED - Server computes this field"
    )
    
    @model_validator(mode='after')
    def reject_power_kw(self):
        """Reject requests that include power_kw."""
        if self.power_kw is not None:
            raise ValueError(
                "power_kw must not be provided by client. "
                "Server computes this value from voltage_v × current_a × power_factor / 1000"
            )
        return self


class ContextInput(BaseModel):
    """Operating context."""
    operating_state: str = Field(..., description="RUNNING, IDLE, or OFF")
    source: str = Field(default="api", description="Data source identifier")
    
    @field_validator('operating_state')
    @classmethod
    def validate_operating_state(cls, v: str) -> str:
        """Validate operating state is one of allowed values."""
        allowed = {"RUNNING", "IDLE", "OFF"}
        if v.upper() not in allowed:
            raise ValueError(f"operating_state must be one of {allowed}, got '{v}'")
        return v.upper()


class SensorEventRequest(BaseModel):
    """
    Ingestion request for a single sensor event.
    
    Validation rules:
    - event_id: Must be valid UUIDv4
    - timestamp: Must be timezone-aware UTC
    - power_kw: Must NOT be provided (server-computed)
    """
    # Note: strict=True removed to allow datetime string coercion from JSON
    # Validation is still enforced via field validators below
    
    event_id: str = Field(..., description="UUID v4 event identifier")
    timestamp: datetime = Field(..., description="Event timestamp (UTC required)")
    asset: AssetInput
    signals: SignalsInput
    context: ContextInput
    
    @field_validator('event_id')
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        """Validate event_id is a valid UUIDv4."""
        try:
            # Parse the UUID string (don't pass version, let it detect)
            uuid_obj = UUID(v)
            # Ensure it's actually a v4 UUID by checking the version
            if uuid_obj.version != 4:
                raise ValueError(
                    f"event_id must be UUID version 4, got version {uuid_obj.version}"
                )
            return str(uuid_obj)
        except ValueError as e:
            raise ValueError(f"event_id must be a valid UUIDv4: {e}")
    
    @field_validator('timestamp')
    @classmethod
    def validate_utc_timestamp(cls, v: datetime) -> datetime:
        """Validate timestamp is timezone-aware and UTC."""
        if v.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware. "
                "Provide UTC timestamp like '2026-01-11T12:00:00Z'"
            )
        # Convert to UTC if not already
        utc_time = v.astimezone(timezone.utc)
        return utc_time


# ============================================================================
# Response Models
# ============================================================================

class SignalsOutput(BaseModel):
    """Signals with computed power_kw."""
    voltage_v: float
    current_a: float
    power_factor: float
    power_kw: float  # Computed by server
    vibration_g: float


class SensorEventResponse(BaseModel):
    """Successful ingestion response."""
    status: str = "accepted"
    event_id: str
    timestamp: datetime
    asset: AssetInput
    signals: SignalsOutput
    context: ContextInput
    message: str = "Event ingested successfully"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    database: str
    message: str


class ErrorDetail(BaseModel):
    """Error detail for validation failures."""
    loc: list
    msg: str
    type: str


class ErrorResponse(BaseModel):
    """Error response for validation failures."""
    detail: list[ErrorDetail]
