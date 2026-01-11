"""
Rules Module — Health & Risk Assessment + Explainability (Phase 7-8)

Public API:
- HealthAssessor: Converts ML scores to human decisions
- HealthReport: Complete assessment matching CONTRACTS.md
- RiskLevel: LOW/MODERATE/HIGH/CRITICAL
- ExplanationGenerator: Human-readable reasoning
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
from .explainer import (
    ExplanationGenerator,
    FeatureContribution,
    ExplanationTemplate,
    EPSILON_RELATIVE,
    MAX_EXPLANATIONS,
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
    "ExplanationGenerator",
    "FeatureContribution",
    "ExplanationTemplate",
    "EPSILON_RELATIVE",
    "MAX_EXPLANATIONS",
]
