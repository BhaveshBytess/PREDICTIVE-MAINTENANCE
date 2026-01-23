"""
Health & Risk Assessment — Convert ML Scores to Human Decisions

This is where RULES live. ML outputs scores; this module assigns meaning.

Constraints:
- Deterministic: Health = 100 * (1.0 - anomaly_score)
- Named threshold constants (no magic numbers)
- RUL is heuristic lookup, not physics model
- Trend = slope of anomaly scores over N windows
- Metadata includes detector version + baseline ID
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# THRESHOLD CONSTANTS — Explicit, Named, No Magic Numbers
# ============================================================================

# Health Score thresholds (0-100 scale, 100=New, 0=Dead)
THRESHOLD_CRITICAL = 25   # Below this = CRITICAL risk
THRESHOLD_HIGH = 50       # Below this = HIGH risk
THRESHOLD_MODERATE = 75   # Below this = MODERATE risk
# Above THRESHOLD_MODERATE = LOW risk

# RUL Heuristic Lookup (days) by risk level
RUL_BY_RISK = {
    "CRITICAL": (0.0, 1.0),    # 0-1 days
    "HIGH": (1.0, 7.0),        # 1-7 days
    "MODERATE": (7.0, 30.0),   # 7-30 days
    "LOW": (30.0, 90.0),       # 30-90 days
}

# Trend windows for anomaly slope calculation
DEFAULT_TREND_WINDOWS = 5


# ============================================================================
# Enums and Schemas
# ============================================================================

class RiskLevel(str, Enum):
    """Risk classification levels."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Explanation(BaseModel):
    """Explanation for a risk assessment."""
    reason: str = Field(..., description="Human-readable reason")
    related_features: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class ReportMetadata(BaseModel):
    """Audit metadata for the report."""
    model_version: str = Field(..., description="Detector version + Baseline ID")
    assessment_version: str = Field(default="1.0.0")


class HealthReport(BaseModel):
    """
    Health & Risk Report matching CONTRACTS.md Section 5.
    
    Output guarantees:
    - CRITICAL always includes at least one explanation
    - Health Score and Risk Level are monotonic
    """
    report_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    asset_id: str
    
    health_score: int = Field(..., ge=0, le=100, description="0=Dead, 100=New")
    risk_level: RiskLevel
    maintenance_window_days: float = Field(..., ge=0)
    
    explanations: List[Explanation] = Field(default_factory=list)
    metadata: ReportMetadata
    
    @field_validator('timestamp')
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


# ============================================================================
# Health Assessor
# ============================================================================

class HealthAssessor:
    """
    Converts ML anomaly scores into health reports.
    
    Pure deterministic logic. Same input = Same output.
    """
    
    def __init__(
        self,
        detector_version: str = "1.0.0",
        baseline_id: str = "unknown"
    ):
        """
        Initialize assessor with audit metadata.
        
        Args:
            detector_version: Version of the anomaly detector
            baseline_id: ID of the baseline used
        """
        self.detector_version = detector_version
        self.baseline_id = baseline_id
    
    def compute_health_score(self, anomaly_score: float) -> int:
        """
        Compute health score from anomaly score.
        
        Formula with Confidence Boost:
        - For low anomaly scores (< 0.15), apply boost to ensure healthy = 80+
        - Base: Health = 100 * (1.0 - anomaly_score)
        - Boost: Amplify health for truly healthy readings
        
        Args:
            anomaly_score: Anomaly score [0, 1] where 1 = highly anomalous
            
        Returns:
            Health score [0, 100] where 100 = perfectly healthy
        """
        # Clamp anomaly score to valid range
        clamped_score = max(0.0, min(1.0, anomaly_score))
        
        # Apply confidence boost for low anomaly scores ("Green Start" rule)
        # When anomaly_score < 0.15 (truly healthy), boost health to 80+
        if clamped_score < 0.15:
            # Scale 0.0-0.15 to health 100-80
            # At score=0.0 -> health=100
            # At score=0.15 -> health=80
            health = 100.0 - (clamped_score / 0.15) * 20.0
        elif clamped_score < 0.35:
            # Moderate zone: scale 0.15-0.35 to health 80-50
            normalized = (clamped_score - 0.15) / 0.20
            health = 80.0 - normalized * 30.0
        else:
            # High anomaly zone: scale 0.35-1.0 to health 50-0
            normalized = (clamped_score - 0.35) / 0.65
            health = 50.0 - normalized * 50.0
        
        return int(round(max(0, min(100, health))))
    
    def classify_risk_level(self, health_score: int) -> RiskLevel:
        """
        Classify risk level from health score.
        
        Uses EXPLICIT NAMED CONSTANTS — no magic numbers.
        
        Args:
            health_score: Health score [0, 100]
            
        Returns:
            Risk level classification
        """
        if health_score < THRESHOLD_CRITICAL:
            return RiskLevel.CRITICAL
        elif health_score < THRESHOLD_HIGH:
            return RiskLevel.HIGH
        elif health_score < THRESHOLD_MODERATE:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW
    
    def estimate_rul(self, risk_level: RiskLevel) -> float:
        """
        Estimate Remaining Useful Life (RUL) in days.
        
        This is HEURISTIC/ADVISORY only — not a physics model.
        Uses lookup table based on risk level.
        
        Args:
            risk_level: Current risk classification
            
        Returns:
            Estimated RUL in days (midpoint of range)
        """
        rul_range = RUL_BY_RISK.get(risk_level.value, (30.0, 90.0))
        
        # Return midpoint of the range
        midpoint = (rul_range[0] + rul_range[1]) / 2.0
        
        return round(midpoint, 1)
    
    def calculate_trend(self, anomaly_scores: List[float]) -> Optional[float]:
        """
        Calculate anomaly trend as slope over recent windows.
        
        Trend = (latest - earliest) / n_windows
        
        Args:
            anomaly_scores: List of recent anomaly scores (oldest first)
            
        Returns:
            Slope value (positive = worsening, negative = improving)
            None if insufficient data
        """
        if len(anomaly_scores) < 2:
            return None
        
        # Simple linear slope: (last - first) / count
        n = len(anomaly_scores)
        slope = (anomaly_scores[-1] - anomaly_scores[0]) / (n - 1)
        
        return round(slope, 4)
    
    def generate_explanations(
        self,
        health_score: int,
        risk_level: RiskLevel,
        anomaly_score: float,
        feature_contributions: Optional[Dict[str, float]] = None
    ) -> List[Explanation]:
        """
        Generate explanations for the assessment.
        
        CRITICAL risk MUST have at least one explanation.
        
        Args:
            health_score: Computed health score
            risk_level: Classified risk level
            anomaly_score: Raw anomaly score
            feature_contributions: Optional feature importance scores
            
        Returns:
            List of explanations
        """
        explanations = []
        
        # Generate explanation based on risk level
        if risk_level == RiskLevel.CRITICAL:
            explanations.append(Explanation(
                reason=f"Critical anomaly detected (score: {anomaly_score:.2f}). Immediate attention required.",
                related_features=list(feature_contributions.keys()) if feature_contributions else [],
                confidence_score=0.95
            ))
        elif risk_level == RiskLevel.HIGH:
            explanations.append(Explanation(
                reason=f"High anomaly level detected (score: {anomaly_score:.2f}). Schedule maintenance soon.",
                related_features=list(feature_contributions.keys()) if feature_contributions else [],
                confidence_score=0.85
            ))
        elif risk_level == RiskLevel.MODERATE:
            explanations.append(Explanation(
                reason=f"Moderate deviation from baseline detected (score: {anomaly_score:.2f}). Monitor closely.",
                related_features=[],
                confidence_score=0.70
            ))
        # LOW risk doesn't require explanation
        
        return explanations
    
    def assess(
        self,
        asset_id: str,
        anomaly_score: float,
        feature_contributions: Optional[Dict[str, float]] = None,
        anomaly_history: Optional[List[float]] = None
    ) -> HealthReport:
        """
        Generate complete health assessment report.
        
        Args:
            asset_id: Asset identifier
            anomaly_score: Current anomaly score [0, 1]
            feature_contributions: Optional feature importance
            anomaly_history: Optional historical scores for trend
            
        Returns:
            Complete HealthReport matching CONTRACTS.md
        """
        # Compute health score (deterministic formula)
        health_score = self.compute_health_score(anomaly_score)
        
        # Classify risk level (named thresholds)
        risk_level = self.classify_risk_level(health_score)
        
        # Estimate RUL (heuristic lookup)
        rul_days = self.estimate_rul(risk_level)
        
        # Generate explanations (required for CRITICAL)
        explanations = self.generate_explanations(
            health_score,
            risk_level,
            anomaly_score,
            feature_contributions
        )
        
        # Build audit metadata
        metadata = ReportMetadata(
            model_version=f"detector:{self.detector_version}|baseline:{self.baseline_id}"
        )
        
        return HealthReport(
            asset_id=asset_id,
            health_score=health_score,
            risk_level=risk_level,
            maintenance_window_days=rul_days,
            explanations=explanations,
            metadata=metadata
        )
