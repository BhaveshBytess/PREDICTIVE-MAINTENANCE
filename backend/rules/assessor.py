"""
Health & Risk Assessment — Convert ML Scores to Human Decisions

This is where RULES live. ML outputs scores; this module assigns meaning.

Constraints:
- Deterministic: Health = 100 * (1.0 - anomaly_score)
- Named threshold constants (no magic numbers)
- RUL is heuristic lookup, not physics model
- Trend = slope of anomaly scores over N windows
- Metadata includes detector version + baseline ID

Phase 20 — Cumulative Prognostics:
- Degradation Index (DI): Monotonically increasing damage accumulator
- Formula (Miner's Rule): DI_inc = (severity^2) * SENSITIVITY_CONSTANT
- Constraint: DI must NEVER decrease
- Health is derived from DI: health = (1.0 - DI) * 100
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
# CUMULATIVE DEGRADATION CONSTANTS (Phase 20)
# ============================================================================

# Sensitivity constant for Miner's Rule damage accumulation
# DI_inc = (effective_severity ** 2) * SENSITIVITY_CONSTANT
# At score=1.0 (max fault), DI increases by 0.0005 per second
# → Full degradation (DI=1.0) takes ~2000 seconds (~33 min) of sustained max fault
SENSITIVITY_CONSTANT = 0.0005

# Dead-zone floor: batch_scores below this are treated as healthy noise (zero damage).
# IsolationForest calibration produces non-zero scores (0.1–0.5) even on healthy data
# due to the contamination parameter.  Without this floor the DI accumulator
# "self-harms" — phantom damage accrues during normal operation.
# Scores above HEALTHY_FLOOR are remapped to [0, 1] via:
#   effective_severity = (score - HEALTHY_FLOOR) / (1 - HEALTHY_FLOOR)
HEALTHY_FLOOR = 0.65

# DI threshold milestones for Log Watcher warnings
DI_THRESHOLD_15 = 0.15    # "Motor fatigue reached 15%"
DI_THRESHOLD_30 = 0.30    # "Motor fatigue reached 30%"
DI_THRESHOLD_50 = 0.50    # "Motor fatigue reached 50%"
DI_THRESHOLD_75 = 0.75    # "Motor fatigue reached 75% — CRITICAL"


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


# ============================================================================
# CUMULATIVE DEGRADATION ENGINE (Phase 20)
# ============================================================================
# These are MODULE-LEVEL functions (not methods) so they can be called from
# system_routes.py monitoring loops without instantiating HealthAssessor.

def compute_cumulative_degradation(
    last_di: float,
    batch_anomaly_score: float,
    dt: float = 1.0
) -> tuple:
    """
    Miner's Rule damage accumulation with dead-zone.

    Dead-zone:  scores < HEALTHY_FLOOR (0.65) → effective_severity = 0 → zero damage.
    Above floor: effective_severity = (score - HEALTHY_FLOOR) / (1 - HEALTHY_FLOOR)
    DI_inc = (effective_severity ^ 2) * SENSITIVITY_CONSTANT * dt
    new_di = max(last_di, last_di + DI_inc)   ← absolute monotonicity

    Args:
        last_di:              Previous Degradation Index [0, 1]
        batch_anomaly_score:  Current batch anomaly score [0, 1] (severity)
        dt:                   Time step in seconds (default 1.0)

    Returns:
        (new_di, damage_rate)
        new_di:      Updated DI, clamped to [0, 1], never < last_di
        damage_rate: Instantaneous damage rate (DI per second)
    """
    clamped = max(0.0, min(1.0, batch_anomaly_score))

    # Dead-zone: scores below HEALTHY_FLOOR produce zero damage
    if clamped < HEALTHY_FLOOR:
        effective_severity = 0.0
    else:
        # Remap [HEALTHY_FLOOR, 1.0] → [0.0, 1.0]
        effective_severity = (clamped - HEALTHY_FLOOR) / (1.0 - HEALTHY_FLOOR)

    damage_rate = (effective_severity ** 2) * SENSITIVITY_CONSTANT

    raw_di = last_di + damage_rate * dt
    # Monotonicity: DI must NEVER decrease
    new_di = max(last_di, raw_di)
    # Clamp to [0, 1]
    new_di = min(1.0, new_di)

    return (new_di, damage_rate)


def health_from_degradation(di: float) -> int:
    """
    Derive health score directly from Degradation Index.

    health = (1.0 - DI) * 100, clamped to [0, 100]

    Args:
        di: Degradation Index [0, 1]

    Returns:
        Health score integer [0, 100]
    """
    raw = (1.0 - di) * 100.0
    return int(max(0, min(100, round(raw))))


def rul_from_degradation(di: float, damage_rate: float) -> float:
    """
    Estimate Remaining Useful Life from DI and damage rate.

    RUL_hours = (1.0 - DI) / max(damage_rate, 1e-9)

    Args:
        di:          Current Degradation Index [0, 1]
        damage_rate: Current instantaneous damage rate (DI per second)

    Returns:
        RUL in hours. Returns 99999.0 if damage_rate ≈ 0.
    """
    remaining = 1.0 - di
    if damage_rate < 1e-9:
        return 99999.0
    rul_seconds = remaining / damage_rate
    return round(rul_seconds / 3600.0, 2)


def risk_from_health(health_score: int) -> str:
    """
    Derive risk level from health score using named thresholds.

    Consistent with HealthAssessor.classify_risk_level but returns str.
    """
    if health_score <= THRESHOLD_CRITICAL:
        return "CRITICAL"
    elif health_score <= THRESHOLD_HIGH:
        return "HIGH"
    elif health_score <= THRESHOLD_MODERATE:
        return "MODERATE"
    else:
        return "LOW"


def crossed_thresholds(old_di: float, new_di: float) -> list:
    """
    Return list of DI threshold milestones crossed between old_di and new_di.

    Useful for emitting warning events.

    Args:
        old_di: Previous DI value
        new_di: New DI value

    Returns:
        List of (threshold_value, percent_label) that were newly crossed
    """
    thresholds = [
        (DI_THRESHOLD_15, "15%"),
        (DI_THRESHOLD_30, "30%"),
        (DI_THRESHOLD_50, "50%"),
        (DI_THRESHOLD_75, "75%"),
    ]
    crossed = []
    for thr, label in thresholds:
        if old_di < thr <= new_di:
            crossed.append((thr, label))
    return crossed
