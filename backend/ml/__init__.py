"""
ML Module — Machine Learning Components (Phase 5+)

Public API:
- BaselineProfile: Statistical profile for an asset
- BaselineBuilder: Constructs baselines from healthy data
- save_baseline / load_baseline: JSON persistence
- validate_baseline: Profile completeness check
- check_data_against_baseline: 3-Sigma validation
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
]
