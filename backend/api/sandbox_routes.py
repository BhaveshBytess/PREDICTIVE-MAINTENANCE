"""
Sandbox Routes — What-If Analysis Endpoints

Provides "What-If" analysis for testing manual inputs:
- POST /sandbox/predict — Test manual sensor values
- GET /sandbox/presets — Get preset fault scenarios
"""

from datetime import datetime, timezone
from typing import Dict, Optional, List
import numpy as np

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.ml.detector import AnomalyDetector, NOMINAL_VOLTAGE, BASE_FEATURE_COLUMNS
from backend.rules.assessor import RiskLevel

# Import global state from integration_routes for comparison feature
from backend.api.integration_routes import (
    _detectors, 
    _baselines, 
    _sensor_history,
    _latest_health
)


router = APIRouter(prefix="/sandbox", tags=["Sandbox"])


# =============================================================================
# SCHEMAS
# =============================================================================

class ManualTestInput(BaseModel):
    """Manual sensor input for What-If analysis."""
    voltage_v: float = Field(..., ge=150, le=300, description="Voltage (V)")
    current_a: float = Field(..., ge=1, le=50, description="Current (A)")
    power_factor: float = Field(..., ge=0.3, le=1.0, description="Power Factor")
    vibration_g: float = Field(..., ge=0.01, le=10.0, description="Vibration (g)")
    asset_id: str = Field(default="asset-001", description="Asset to compare against")


class FeatureContribution(BaseModel):
    """Feature contribution to anomaly score."""
    feature: str
    value: float
    contribution_percent: float
    deviation_from_normal: float
    status: str  # "normal", "elevated", "critical"


class LiveComparison(BaseModel):
    """Comparison with live system state."""
    live_voltage: Optional[float] = None
    live_current: Optional[float] = None
    live_power_factor: Optional[float] = None
    live_vibration: Optional[float] = None
    voltage_diff_percent: Optional[float] = None
    current_diff_percent: Optional[float] = None
    power_factor_diff_percent: Optional[float] = None
    vibration_diff_percent: Optional[float] = None
    live_health_score: Optional[int] = None
    live_risk_level: Optional[str] = None


class SandboxPredictResponse(BaseModel):
    """Response from sandbox prediction."""
    anomaly_score: float = Field(..., ge=0, le=1)
    health_score: int = Field(..., ge=0, le=100)
    risk_level: str
    feature_contributions: List[FeatureContribution]
    insight: str
    comparison: Optional[LiveComparison] = None


class PresetScenario(BaseModel):
    """A preset fault scenario."""
    name: str
    description: str
    voltage_v: float
    current_a: float
    power_factor: float
    vibration_g: float
    expected_risk: str


# =============================================================================
# PRESET SCENARIOS
# =============================================================================

PRESET_SCENARIOS = [
    PresetScenario(
        name="Normal",
        description="Healthy operating conditions - Indian Grid nominal",
        voltage_v=230.0,
        current_a=15.0,
        power_factor=0.92,
        vibration_g=0.15,
        expected_risk="LOW"
    ),
    PresetScenario(
        name="Motor Stall",
        description="Motor experiencing stall condition with high current draw",
        voltage_v=210.0,
        current_a=35.0,
        power_factor=0.55,
        vibration_g=2.5,
        expected_risk="CRITICAL"
    ),
    PresetScenario(
        name="Voltage Spike",
        description="Grid voltage spike damaging equipment",
        voltage_v=285.0,
        current_a=18.0,
        power_factor=0.85,
        vibration_g=0.35,
        expected_risk="HIGH"
    ),
    PresetScenario(
        name="Bearing Failure",
        description="Bearing degradation causing excessive vibration",
        voltage_v=228.0,
        current_a=16.0,
        power_factor=0.88,
        vibration_g=3.8,
        expected_risk="CRITICAL"
    ),
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def compute_derived_features(voltage: float, current: float, pf: float, vibration: float) -> Dict[str, float]:
    """
    Compute all features for ML model input.
    Must match AnomalyDetector._compute_derived_features_single exactly.
    """
    return {
        'voltage_rolling_mean_1h': voltage,
        'current_spike_count': 0 if current < 20 else int((current - 15) / 2),
        'power_factor_efficiency_score': max(0.0, min(1.0, pf)),
        'vibration_intensity_rms': vibration,
        'voltage_stability': abs(voltage - NOMINAL_VOLTAGE),
        'power_vibration_ratio': vibration / (pf + 0.01)
    }


def compute_feature_contributions(
    features: Dict[str, float],
    scaler,
    detector: AnomalyDetector
) -> List[FeatureContribution]:
    """
    Compute feature contributions using deviation-based heuristic.
    
    Since Isolation Forest doesn't provide direct feature importance,
    we use how far each feature deviates from the "healthy mean" (scaler.mean_).
    """
    contributions = []
    
    # Get scaler statistics
    means = scaler.mean_
    stds = scaler.scale_
    feature_names = BASE_FEATURE_COLUMNS + ['voltage_stability', 'power_vibration_ratio']
    
    # Calculate raw deviations
    raw_deviations = {}
    for i, name in enumerate(feature_names):
        if name in features:
            value = features[name]
            mean = means[i]
            std = stds[i] if stds[i] > 0 else 1.0
            
            # Z-score deviation (how many std devs from mean)
            deviation = abs(value - mean) / std
            raw_deviations[name] = deviation
    
    # Normalize to percentages (sum = 100%)
    total_deviation = sum(raw_deviations.values()) + 0.001  # Avoid div by zero
    
    for name, deviation in raw_deviations.items():
        contribution_pct = (deviation / total_deviation) * 100
        
        # Determine status based on deviation
        if deviation < 1.0:
            status = "normal"
        elif deviation < 2.5:
            status = "elevated"
        else:
            status = "critical"
        
        contributions.append(FeatureContribution(
            feature=_format_feature_name(name),
            value=features.get(name, 0),
            contribution_percent=round(contribution_pct, 1),
            deviation_from_normal=round(deviation, 2),
            status=status
        ))
    
    # Sort by contribution (highest first)
    contributions.sort(key=lambda x: x.contribution_percent, reverse=True)
    
    return contributions


def _format_feature_name(name: str) -> str:
    """Convert feature name to human-readable format."""
    mapping = {
        'voltage_rolling_mean_1h': 'Voltage',
        'current_spike_count': 'Current Spikes',
        'power_factor_efficiency_score': 'Power Factor',
        'vibration_intensity_rms': 'Vibration',
        'voltage_stability': 'Voltage Stability',
        'power_vibration_ratio': 'Power/Vibration Ratio'
    }
    return mapping.get(name, name)


def generate_insight(
    anomaly_score: float,
    risk_level: str,
    contributions: List[FeatureContribution],
    input_data: ManualTestInput
) -> str:
    """Generate human-readable insight text."""
    
    if risk_level == "LOW":
        return "All sensor values are within normal operating ranges. System appears healthy."
    
    # Get top contributors
    top_contributors = contributions[:2]
    
    # Build insight based on top contributors
    insights = []
    
    for contrib in top_contributors:
        if contrib.feature == "Voltage":
            diff = input_data.voltage_v - NOMINAL_VOLTAGE
            if diff > 20:
                insights.append(f"Voltage is {abs(diff):.0f}V above nominal ({NOMINAL_VOLTAGE}V)")
            elif diff < -20:
                insights.append(f"Voltage is {abs(diff):.0f}V below nominal ({NOMINAL_VOLTAGE}V)")
        
        elif contrib.feature == "Vibration":
            if input_data.vibration_g > 1.0:
                insights.append(f"Vibration ({input_data.vibration_g:.2f}g) is significantly elevated")
        
        elif contrib.feature == "Power Factor":
            if input_data.power_factor < 0.8:
                insights.append(f"Power Factor ({input_data.power_factor:.2f}) is below acceptable threshold")
        
        elif contrib.feature == "Current Spikes":
            if input_data.current_a > 25:
                insights.append(f"Current draw ({input_data.current_a:.1f}A) indicates potential overload")
    
    if not insights:
        insights.append(f"Anomaly detected with {anomaly_score:.0%} confidence")
    
    return ". ".join(insights) + "."


def get_live_comparison(asset_id: str, input_data: ManualTestInput) -> Optional[LiveComparison]:
    """Get comparison with current live system state."""
    
    if asset_id not in _sensor_history or not _sensor_history[asset_id]:
        return None
    
    # Get latest reading
    latest = _sensor_history[asset_id][-1]
    
    # Calculate percentage differences
    def pct_diff(manual, live):
        if live == 0:
            return 0
        return ((manual - live) / live) * 100
    
    # Get live health if available
    live_health = None
    live_risk = None
    if asset_id in _latest_health:
        health_report = _latest_health[asset_id]
        live_health = health_report.health_score
        live_risk = health_report.risk_level.value
    
    return LiveComparison(
        live_voltage=latest.get('voltage_v'),
        live_current=latest.get('current_a'),
        live_power_factor=latest.get('power_factor'),
        live_vibration=latest.get('vibration_g'),
        voltage_diff_percent=round(pct_diff(input_data.voltage_v, latest.get('voltage_v', 230)), 1),
        current_diff_percent=round(pct_diff(input_data.current_a, latest.get('current_a', 15)), 1),
        power_factor_diff_percent=round(pct_diff(input_data.power_factor, latest.get('power_factor', 0.92)), 1),
        vibration_diff_percent=round(pct_diff(input_data.vibration_g, latest.get('vibration_g', 0.15)), 1),
        live_health_score=live_health,
        live_risk_level=live_risk
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post(
    "/predict",
    response_model=SandboxPredictResponse,
    summary="Test manual sensor values"
)
async def sandbox_predict(input_data: ManualTestInput):
    """
    Run What-If analysis on manual sensor inputs.
    
    - Computes derived features
    - Runs through calibrated ML model
    - Returns anomaly score, risk level, and feature contributions
    - Compares against live system state if available
    """
    asset_id = input_data.asset_id
    
    # Check if detector is trained
    if asset_id not in _detectors or not _detectors[asset_id].is_trained:
        # Use a fallback simple scoring if no detector
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No trained detector for asset '{asset_id}'. Please calibrate the system first."
        )
    
    detector = _detectors[asset_id]
    
    # Compute all features (base + derived)
    features = compute_derived_features(
        voltage=input_data.voltage_v,
        current=input_data.current_a,
        pf=input_data.power_factor,
        vibration=input_data.vibration_g
    )
    
    # Run prediction using detector's score_single method
    try:
        anomaly_score = detector.score_single({
            'voltage_rolling_mean_1h': features['voltage_rolling_mean_1h'],
            'current_spike_count': features['current_spike_count'],
            'power_factor_efficiency_score': features['power_factor_efficiency_score'],
            'vibration_intensity_rms': features['vibration_intensity_rms']
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )
    
    # Calculate health score and risk level
    health_score = int(100 * (1.0 - anomaly_score))
    health_score = max(0, min(100, health_score))
    
    if health_score >= 75:
        risk_level = "LOW"
    elif health_score >= 50:
        risk_level = "MODERATE"
    elif health_score >= 25:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"
    
    # Compute feature contributions
    contributions = compute_feature_contributions(
        features=features,
        scaler=detector._scaler,
        detector=detector
    )
    
    # Generate insight text
    insight = generate_insight(anomaly_score, risk_level, contributions, input_data)
    
    # Get comparison with live state
    comparison = get_live_comparison(asset_id, input_data)
    
    return SandboxPredictResponse(
        anomaly_score=round(anomaly_score, 3),
        health_score=health_score,
        risk_level=risk_level,
        feature_contributions=contributions,
        insight=insight,
        comparison=comparison
    )


@router.get(
    "/presets",
    response_model=List[PresetScenario],
    summary="Get preset fault scenarios"
)
async def get_presets():
    """
    Get list of preset fault scenarios for quick testing.
    
    Returns scenarios: Normal, Motor Stall, Voltage Spike, Bearing Failure.
    """
    return PRESET_SCENARIOS
