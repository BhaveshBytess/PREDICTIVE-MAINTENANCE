"""
ML Module — Machine Learning Components (Phase 5+)

Public API:
- BaselineProfile: Statistical profile for an asset
- BaselineBuilder: Constructs baselines from healthy data
- AnomalyDetector: Isolation Forest anomaly scoring
"""

from .baseline import (
    BaselineProfile,
    BaselineBuilder,
    BaselineBuildError,
    SignalProfile,
    TrainingWindow,
    save_baseline,
    load_baseline,
)
from .validation import (
    validate_baseline,
    check_data_against_baseline,
    ValidationResult,
    get_expected_range,
)
from .detector import (
    AnomalyDetector,
    AnomalyScore,
    FEATURE_COLUMNS,
)

__all__ = [
    "BaselineProfile",
    "BaselineBuilder",
    "BaselineBuildError",
    "SignalProfile",
    "TrainingWindow",
    "save_baseline",
    "load_baseline",
    "validate_baseline",
    "check_data_against_baseline",
    "ValidationResult",
    "get_expected_range",
    "AnomalyDetector",
    "AnomalyScore",
    "FEATURE_COLUMNS",
]
