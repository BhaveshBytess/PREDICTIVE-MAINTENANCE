"""
ML Module — Machine Learning Components (Phase 5+)

Public API:
- BaselineProfile: Statistical profile for an asset
- BaselineBuilder: Constructs baselines from healthy data
- AnomalyDetector: Isolation Forest anomaly scoring

All heavy imports (sklearn, numpy, pandas) are lazy-loaded inside methods
to keep Render cold-start under 10 seconds.
"""


def __getattr__(name):
    """Lazy-load ML classes on first access to avoid heavy imports at startup."""
    _baseline_exports = {
        "BaselineProfile", "BaselineBuilder", "BaselineBuildError",
        "SignalProfile", "TrainingWindow", "save_baseline", "load_baseline",
    }
    _validation_exports = {
        "validate_baseline", "check_data_against_baseline",
        "ValidationResult", "get_expected_range",
    }
    _detector_exports = {
        "AnomalyDetector", "AnomalyScore", "FEATURE_COLUMNS",
    }
    _batch_features_exports = {
        "extract_batch_features", "extract_multi_window_features",
        "BATCH_FEATURE_NAMES",
    }
    _batch_detector_exports = {
        "BatchAnomalyDetector",
    }

    if name in _baseline_exports:
        from . import baseline
        return getattr(baseline, name)
    if name in _validation_exports:
        from . import validation
        return getattr(validation, name)
    if name in _detector_exports:
        from . import detector
        return getattr(detector, name)
    if name in _batch_features_exports:
        from . import batch_features
        return getattr(batch_features, name)
    if name in _batch_detector_exports:
        from . import batch_detector
        return getattr(batch_detector, name)

    raise AttributeError(f"module 'backend.ml' has no attribute {name!r}")


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
    "extract_batch_features",
    "extract_multi_window_features",
    "BATCH_FEATURE_NAMES",
    "BatchAnomalyDetector",
]
