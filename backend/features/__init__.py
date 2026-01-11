"""
Features Module — Feature Engineering Layer (Phase 4)

Public API:
- FeatureEngine: Stateless feature extraction orchestrator
- FeatureRecord: Complete feature record with metadata
- DerivedFeatures: The four contract-mandated features
"""

from .schemas import FeatureRecord, DerivedFeatures
from .engine import FeatureEngine
from .calculator import (
    calculate_voltage_rolling_mean,
    calculate_current_spike_count,
    calculate_power_factor_efficiency_score,
    calculate_vibration_rms,
    compute_all_features,
)

__all__ = [
    "FeatureEngine",
    "FeatureRecord",
    "DerivedFeatures",
    "calculate_voltage_rolling_mean",
    "calculate_current_spike_count", 
    "calculate_power_factor_efficiency_score",
    "calculate_vibration_rms",
    "compute_all_features",
]
