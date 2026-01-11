"""
Rules Module — Health & Risk Assessment Logic (Phase 7)

Public API:
- HealthAssessor: Converts ML scores to human decisions
- HealthReport: Complete assessment matching CONTRACTS.md
- RiskLevel: LOW/MODERATE/HIGH/CRITICAL
"""

from .assessor import (
    HealthAssessor,
    HealthReport,
    RiskLevel,
    Explanation,
    ReportMetadata,
    THRESHOLD_CRITICAL,
    THRESHOLD_HIGH,
    THRESHOLD_MODERATE,
    RUL_BY_RISK,
)

__all__ = [
    "HealthAssessor",
    "HealthReport",
    "RiskLevel",
    "Explanation",
    "ReportMetadata",
    "THRESHOLD_CRITICAL",
    "THRESHOLD_HIGH", 
    "THRESHOLD_MODERATE",
    "RUL_BY_RISK",
]
