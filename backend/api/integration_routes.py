"""
Integration Routes — System Integration Endpoints (Phase 12)

Provides the "glue" endpoints that connect all modules:
- POST /api/v1/baseline/build — Trigger baseline learning
- GET /api/v1/status/{asset_id} — Get latest health status
- GET /api/v1/report/{asset_id} — Download PDF report
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json

from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import pandas as pd
from io import BytesIO

from backend.ml.baseline import BaselineBuilder, BaselineProfile, save_baseline, load_baseline
from backend.ml.detector import AnomalyDetector
from backend.rules.assessor import HealthAssessor, HealthReport, RiskLevel
from backend.rules.explainer import ExplanationGenerator
from backend.reports.generator import generate_pdf_report, generate_excel_report, generate_filename


router = APIRouter(prefix="/api/v1", tags=["Integration"])


# In-memory storage for demo (replace with proper storage in production)
_baselines: Dict[str, BaselineProfile] = {}
_detectors: Dict[str, AnomalyDetector] = {}
_latest_health: Dict[str, HealthReport] = {}
_sensor_history: Dict[str, list] = {}


class BaselineBuildRequest(BaseModel):
    """Request to build a baseline for an asset."""
    training_hours: int = Field(default=1, ge=1, le=168, description="Hours of data to use")


class BaselineBuildResponse(BaseModel):
    """Response after building baseline."""
    status: str
    asset_id: str
    baseline_id: str
    sample_count: int
    message: str


class HealthStatusResponse(BaseModel):
    """Current health status for an asset."""
    asset_id: str
    timestamp: datetime
    health_score: int
    risk_level: str
    maintenance_window_days: float
    explanations: list
    model_version: str


class SimpleIngestRequest(BaseModel):
    """Simplified ingest for demo purposes."""
    asset_id: str
    voltage_v: float
    current_a: float
    power_factor: float
    vibration_g: float
    is_faulty: bool = False


@router.post(
    "/baseline/build",
    response_model=BaselineBuildResponse,
    summary="Build baseline from recent healthy data"
)
async def build_baseline(
    asset_id: str = Query(..., description="Asset to build baseline for"),
    request: Optional[BaselineBuildRequest] = None
):
    """
    Trigger baseline construction for an asset.
    
    Uses recent sensor data (healthy only) to build:
    - Signal profiles (mean, std, min, max)
    - Anomaly detection model (Isolation Forest)
    """
    if request is None:
        request = BaselineBuildRequest()
    
    # Check if we have sensor data for this asset
    if asset_id not in _sensor_history or len(_sensor_history[asset_id]) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient data for asset '{asset_id}'. Need at least 10 samples. "
                   f"Run: python scripts/generate_data.py --asset_id {asset_id} --duration 60 --healthy"
        )
    
    # Get sensor history
    history = _sensor_history[asset_id]
    
    # Convert to DataFrame
    df = pd.DataFrame(history)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # Filter to healthy data only
    if 'is_faulty' in df.columns:
        healthy_df = df[df['is_faulty'] == False].copy()
        healthy_df['is_fault_injected'] = False
    else:
        healthy_df = df.copy()
        healthy_df['is_fault_injected'] = False
    
    if len(healthy_df) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient healthy data. Have {len(healthy_df)} healthy samples, need 10."
        )
    
    # Build baseline
    builder = BaselineBuilder()
    try:
        baseline = builder.build(healthy_df, asset_id=asset_id)
        _baselines[asset_id] = baseline
        
        # Train anomaly detector
        from backend.features.calculator import compute_all_features
        
        feature_data = []
        for idx in range(10, len(healthy_df)):
            f = compute_all_features(healthy_df, idx, healthy_df['power_factor'].iloc[idx])
            feature_data.append(f)
        
        if feature_data:
            feature_df = pd.DataFrame(feature_data)
            feature_cols = ['voltage_rolling_mean_1h', 'current_spike_count', 
                            'power_factor_efficiency_score', 'vibration_intensity_rms']
            train_features = feature_df[feature_cols].dropna()
            
            if len(train_features) >= 10:
                detector = AnomalyDetector(asset_id=asset_id)
                detector.train(train_features)
                _detectors[asset_id] = detector
        
        return BaselineBuildResponse(
            status="success",
            asset_id=asset_id,
            baseline_id=baseline.baseline_id,
            sample_count=len(healthy_df),
            message=f"Baseline built from {len(healthy_df)} healthy samples"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build baseline: {str(e)}"
        )


@router.get(
    "/status/{asset_id}",
    response_model=HealthStatusResponse,
    summary="Get current health status"
)
async def get_health_status(asset_id: str):
    """
    Get the latest health assessment for an asset.
    
    Returns health score, risk level, and explanations.
    Uses direct deviation from baseline for more responsive anomaly detection.
    """
    # Check if we have data
    if asset_id not in _sensor_history or len(_sensor_history[asset_id]) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data for asset '{asset_id}'"
        )
    
    # Get latest reading
    latest = _sensor_history[asset_id][-1]
    
    # Default health if no baseline yet
    if asset_id not in _baselines:
        return HealthStatusResponse(
            asset_id=asset_id,
            timestamp=datetime.now(timezone.utc),
            health_score=85,
            risk_level="LOW",
            maintenance_window_days=30.0,
            explanations=["Baseline not yet established. Collecting data..."],
            model_version="pending"
        )
    
    baseline = _baselines[asset_id]
    
    # DIRECT DEVIATION SCORING
    # Compare current readings directly against baseline profiles
    # This is more responsive than the Isolation Forest for extreme values
    
    max_deviation = 0.0
    signals = ['voltage_v', 'current_a', 'power_factor', 'vibration_g']
    
    for signal in signals:
        if signal in baseline.signal_profiles:
            profile = baseline.signal_profiles[signal]
            current_value = latest.get(signal, 0)
            
            # Calculate z-score (number of standard deviations from mean)
            # Use minimum std floor to prevent divide-by-small-number issues
            effective_std = max(profile.std, profile.mean * 0.02)  # At least 2% of mean
            if effective_std > 0:
                z_score = abs(current_value - profile.mean) / effective_std
                max_deviation = max(max_deviation, z_score)
    
    # Convert z-score to anomaly score [0, 1]
    # HEALTHY DATA: z < 3 -> very low anomaly score (0-0.1) -> health 80+
    # Normal statistical variation is up to 3σ (99.7% of data)
    # MODERATE: z = 3-5 -> anomaly 0.1-0.3 -> health 50-80
    # HIGH: z = 5-8 -> anomaly 0.3-0.6 -> health 20-50  
    # CRITICAL: z > 8 -> anomaly 0.6+ -> health < 20
    import math
    if max_deviation < 3.0:
        # Healthy zone: up to 3σ is normal variation
        anomaly_score = max_deviation * 0.033  # z=3 -> 0.1
    elif max_deviation < 5.0:
        # Moderate zone
        anomaly_score = 0.1 + (max_deviation - 3.0) * 0.1  # z=5 -> 0.3
    elif max_deviation < 8.0:
        # High zone
        anomaly_score = 0.3 + (max_deviation - 5.0) * 0.1  # z=8 -> 0.6
    else:
        # Critical zone
        anomaly_score = min(0.95, 0.6 + (max_deviation - 8.0) * 0.05)
    
    anomaly_score = min(0.98, max(0.0, anomaly_score))  # Clamp to [0, 0.98]
    
    # Also check ML detector if available (use max of both)
    if asset_id in _detectors:
        detector = _detectors[asset_id]
        from backend.features.calculator import compute_all_features
        
        df = pd.DataFrame(_sensor_history[asset_id])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        if len(df) >= 10:
            features = compute_all_features(df, len(df)-1, latest['power_factor'])
            feature_cols = ['voltage_rolling_mean_1h', 'current_spike_count', 
                            'power_factor_efficiency_score', 'vibration_intensity_rms']
            
            if all(features.get(col) is not None for col in feature_cols):
                feature_df = pd.DataFrame([{col: features[col] for col in feature_cols}])
                scores = detector.score(feature_df)
                if scores:
                    ml_score = scores[0].score
                    anomaly_score = max(anomaly_score, ml_score)  # Use higher score
    
    # Generate health assessment
    assessor = HealthAssessor(
        detector_version="1.0.0",
        baseline_id=baseline.baseline_id
    )
    report = assessor.assess(asset_id, anomaly_score)
    
    # Generate explanations
    generator = ExplanationGenerator(baseline)
    current_readings = {
        'voltage_v': latest['voltage_v'],
        'current_a': latest['current_a'],
        'power_factor': latest['power_factor'],
        'vibration_g': latest['vibration_g']
    }
    explanations = generator.generate(current_readings, report.risk_level, baseline)
    
    # Store latest health
    _latest_health[asset_id] = report
    
    return HealthStatusResponse(
        asset_id=asset_id,
        timestamp=report.timestamp,
        health_score=report.health_score,
        risk_level=report.risk_level.value,
        maintenance_window_days=report.maintenance_window_days,
        explanations=[e.reason for e in explanations] if explanations else ["Systems nominal"],
        model_version=report.metadata.model_version
    )


@router.get(
    "/report/{asset_id}",
    summary="Download PDF health report"
)
async def download_report(
    asset_id: str,
    format: str = Query(default="pdf", description="Report format: pdf or xlsx")
):
    """
    Generate and download a health report.
    
    Uses the latest health assessment for the asset.
    """
    # Get or generate health report
    if asset_id not in _latest_health:
        # Generate one
        await get_health_status(asset_id)
    
    if asset_id not in _latest_health:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cannot generate report for '{asset_id}'"
        )
    
    report = _latest_health[asset_id]
    
    if format.lower() == "xlsx":
        content = generate_excel_report(report)
        filename = generate_filename(asset_id, report.timestamp, "xlsx")
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = generate_pdf_report(report)
        filename = generate_filename(asset_id, report.timestamp, "pdf")
        media_type = "application/pdf"
    
    return StreamingResponse(
        BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post(
    "/data/simple",
    summary="Simplified data ingestion for demo"
)
async def simple_ingest(request: SimpleIngestRequest):
    """
    Simplified ingestion endpoint for demo purposes.
    
    Stores data in memory for real-time dashboard updates.
    Auto-detects anomalies by comparing values against baseline.
    """
    # Initialize history for asset
    if request.asset_id not in _sensor_history:
        _sensor_history[request.asset_id] = []
    
    # Auto-detect anomaly by comparing to baseline (if baseline exists)
    is_anomaly = False
    if request.asset_id in _baselines:
        baseline = _baselines[request.asset_id]
        
        # Check each signal against baseline min/max
        signals = {
            'voltage_v': request.voltage_v,
            'current_a': request.current_a,
            'power_factor': request.power_factor,
            'vibration_g': request.vibration_g
        }
        
        for signal_name, value in signals.items():
            if signal_name in baseline.signal_profiles:
                profile = baseline.signal_profiles[signal_name]
                # Check if value exceeds baseline bounds (with 10% tolerance)
                tolerance = (profile.max - profile.min) * 0.1
                if value < (profile.min - tolerance) or value > (profile.max + tolerance):
                    is_anomaly = True
                    break
    
    # Use auto-detected anomaly flag (overrides generator's flag)
    # If no baseline exists yet, fall back to generator's flag
    detected_faulty = is_anomaly if request.asset_id in _baselines else request.is_faulty
    
    # Store reading
    reading = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "voltage_v": request.voltage_v,
        "current_a": request.current_a,
        "power_factor": request.power_factor,
        "vibration_g": request.vibration_g,
        "is_faulty": detected_faulty
    }
    
    _sensor_history[request.asset_id].append(reading)
    
    # Keep only last 1000 readings per asset
    if len(_sensor_history[request.asset_id]) > 1000:
        _sensor_history[request.asset_id] = _sensor_history[request.asset_id][-1000:]
    
    return {"status": "accepted", "sample_count": len(_sensor_history[request.asset_id])}


@router.get(
    "/data/history/{asset_id}",
    summary="Get sensor data history"
)
async def get_data_history(
    asset_id: str,
    limit: int = Query(default=100, ge=1, le=1000)
):
    """Get recent sensor readings for charting."""
    if asset_id not in _sensor_history:
        return {"asset_id": asset_id, "data": [], "count": 0}
    
    history = _sensor_history[asset_id][-limit:]
    return {
        "asset_id": asset_id,
        "data": history,
        "count": len(history)
    }
