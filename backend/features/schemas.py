"""
Feature Schemas — Derived Feature Output Models

Per CONTRACTS.md Section 4: All engineered features must conform to this schema.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DerivedFeatures(BaseModel):
    """
    Contract-mandated feature set.
    
    All features use past-only windowing (no future leakage).
    NaN is used for incomplete windows (cold-start).
    """
    voltage_rolling_mean_1h: Optional[float] = Field(
        None,
        description="Rolling mean of voltage_v over past 1 hour. NaN if insufficient data."
    )
    current_spike_count: Optional[int] = Field(
        None,
        description="Count of current readings > 2σ above local window mean. NaN if insufficient data."
    )
    power_factor_efficiency_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Normalized power factor score [0.0-1.0]. Higher = better efficiency."
    )
    vibration_intensity_rms: Optional[float] = Field(
        None,
        description="RMS of vibration_g over past 1 hour. NaN if insufficient data."
    )


class FeatureRecord(BaseModel):
    """
    Complete feature record with metadata.
    
    Timestamp is the EVALUATION timestamp (the "right now" of the event),
    not the start of the window.
    """
    feature_id: str = Field(..., description="Unique feature record ID")
    asset_id: str = Field(..., description="Asset this feature belongs to")
    timestamp: datetime = Field(
        ...,
        description="Evaluation timestamp (UTC) - the point in time features are computed FOR"
    )
    features: DerivedFeatures
    
    @field_validator('timestamp')
    @classmethod
    def validate_utc(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (UTC)")
        return v
