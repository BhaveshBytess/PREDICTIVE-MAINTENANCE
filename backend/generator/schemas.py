"""
Canonical Sensor Event Schema — Pydantic Models

This module defines the data contracts for sensor events as specified in CONTRACTS.md.
Used for OUTPUT VALIDATION of generator data.

CONTRACTS.md Reference: Section 3.1 - Canonical Sensor Event (V1)
"""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class OperatingState(str, Enum):
    """Asset operating states."""
    RUNNING = "RUNNING"
    IDLE = "IDLE"
    OFF = "OFF"


class AssetType(str, Enum):
    """Supported asset types for V1."""
    INDUCTION_MOTOR = "induction_motor"


class Asset(BaseModel):
    """Asset identification block."""
    asset_id: str = Field(..., min_length=1, description="Unique asset identifier")
    asset_type: AssetType = Field(default=AssetType.INDUCTION_MOTOR)


class Signals(BaseModel):
    """
    Raw signal measurements from the asset.
    
    Constraints (per CONTRACTS.md):
    - voltage_v: Indian Grid ~230V base
    - power_factor: Bounded 0.0 to 1.0
    - power_kw: Derived as (voltage_v * current_a * power_factor) / 1000
    - vibration_g: Acceleration in g (NASA context)
    """
    voltage_v: float = Field(..., ge=0, description="Voltage in Volts (Indian Grid ~230V)")
    current_a: float = Field(..., ge=0, description="Current in Amperes")
    power_factor: float = Field(..., ge=0.0, le=1.0, description="Power Factor (0.0-1.0)")
    power_kw: float = Field(..., ge=0, description="Power in Kilowatts (derived)")
    vibration_g: float = Field(..., ge=0, description="Vibration acceleration in g")

    @field_validator("power_factor")
    @classmethod
    def validate_power_factor_bounds(cls, v: float) -> float:
        """Ensure power factor is strictly bounded."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Power factor must be between 0.0 and 1.0")
        return v


class Context(BaseModel):
    """Event context metadata."""
    operating_state: OperatingState = Field(..., description="Current operating state")
    source: Literal["simulator"] = Field(
        default="simulator",
        description="Data source identifier (always 'simulator' for Digital Twin)"
    )


class CanonicalSensorEvent(BaseModel):
    """
    Canonical Sensor Event — V1
    
    The normalized record representing the state of an asset at a specific point in time.
    All timestamps are UTC (per CONTRACTS.md Section 3.2).
    
    This schema is IMMUTABLE per CONTRACTS.md.
    """
    event_id: UUID = Field(..., description="Unique event identifier (UUID v4)")
    timestamp: datetime = Field(..., description="Event timestamp (UTC, ISO-8601)")
    asset: Asset = Field(..., description="Asset identification")
    signals: Signals = Field(..., description="Raw signal measurements")
    context: Context = Field(..., description="Event context")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            UUID: str
        }
