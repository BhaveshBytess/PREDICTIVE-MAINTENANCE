"""
Integration Routes — System Integration Endpoints (Phase 12)

Provides the "glue" endpoints that connect all modules:
- POST /api/v1/baseline/build — Trigger baseline learning
- GET /api/v1/status/{asset_id} — Get latest health status
- GET /api/v1/report/{asset_id} — Download PDF report
"""

import logging
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
from backend.reports.industrial_report import (
    IndustrialReportGenerator,
    generate_industrial_report,
    generate_industrial_filename
)
from backend.database import db


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1", tags=["Integration"])


# In-memory storage for demo (replace with proper storage in production)
_baselines: Dict[str, BaselineProfile] = {}
_detectors: Dict[str, AnomalyDetector] = {}
_latest_health: Dict[str, HealthReport] = {}
_sensor_history: Dict[str, list] = {}


def _simple_range_check(baseline: BaselineProfile, latest: Dict[str, Any]) -> float:
    """
    Simple range-based anomaly scoring with graduated severity response.
    
    Produces proportional anomaly scores based on deviation from baseline:
    - Deviation 0-0.5x range: anomaly 0.0-0.25 (LOW risk, health 75+)
    - Deviation 0.5-1.5x range: anomaly 0.25-0.45 (MODERATE risk, health 50-74)
    - Deviation 1.5-3.0x range: anomaly 0.45-0.70 (HIGH risk, health 25-49)
    - Deviation 3.0x+ range: anomaly 0.70-0.95 (CRITICAL risk, health 0-24)
    
    Args:
        baseline: Baseline profile for the asset
        latest: Latest sensor reading dict
        
    Returns:
        Anomaly score [0, 1]
    """
    total_deviation = 0.0
    deviation_count = 0
    signals = ['voltage_v', 'current_a', 'power_factor', 'vibration_g']
    
    for signal in signals:
        if signal in baseline.signal_profiles:
            profile = baseline.signal_profiles[signal]
            current_value = latest.get(signal, 0)
            
            # Calculate how far outside the baseline range (no tolerance)
            range_size = profile.max - profile.min
            if range_size < 0.001:
                range_size = 0.001  # Avoid division by zero
            
            if current_value < profile.min:
                # Below minimum
                deviation = (profile.min - current_value) / range_size
            elif current_value > profile.max:
                # Above maximum
                deviation = (current_value - profile.max) / range_size
            else:
                # Within range
                deviation = 0.0
            
            total_deviation += deviation
            deviation_count += 1
    
    # Average deviation across all signals
    if deviation_count == 0:
        return 0.0
    avg_deviation = total_deviation / deviation_count
    
    # Convert average deviation to anomaly score with graduated response
    # This mapping is calibrated to match severity levels:
    # MILD severity (~0.3-0.8x deviation) → anomaly 0.20-0.35 → MODERATE health
    # MEDIUM severity (~1.0-2.0x deviation) → anomaly 0.40-0.60 → HIGH health
    # SEVERE severity (~3.0-10x deviation) → anomaly 0.70-0.95 → CRITICAL health
    
    if avg_deviation <= 0:
        return 0.0
    elif avg_deviation < 0.3:
        # Very slight deviation - still healthy
        return avg_deviation * 0.5  # 0.0 - 0.15
    elif avg_deviation < 1.0:
        # Mild deviation - MODERATE risk target
        return 0.15 + (avg_deviation - 0.3) * 0.30  # 0.15 - 0.36
    elif avg_deviation < 2.5:
        # Medium deviation - HIGH risk target  
        return 0.36 + (avg_deviation - 1.0) * 0.20  # 0.36 - 0.66
    else:
        # Severe deviation - CRITICAL risk target
        return min(0.95, 0.66 + (avg_deviation - 2.5) * 0.06)  # 0.66 - 0.95


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
    
    # CALIBRATED ML SCORING (Phase 3 Integration)
    # Use the upgraded Isolation Forest with derived features and quantile calibration
    # PLUS simple range check for more proportional severity response
    anomaly_score = 0.0
    ml_score = 0.0
    range_score = 0.0
    
    # Always compute range-based score for proportional response
    range_score = _simple_range_check(baseline, latest)
    
    if asset_id in _detectors and _detectors[asset_id].is_trained:
        # Use calibrated ML detector
        detector = _detectors[asset_id]
        
        # Compute features from current readings
        from backend.features.calculator import compute_all_features
        
        df = pd.DataFrame(_sensor_history[asset_id])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        if len(df) >= 10:
            features = compute_all_features(df, len(df)-1, latest['power_factor'])
            feature_cols = ['voltage_rolling_mean_1h', 'current_spike_count', 
                            'power_factor_efficiency_score', 'vibration_intensity_rms']
            
            if all(features.get(col) is not None for col in feature_cols):
                try:
                    feature_dict = {col: features[col] for col in feature_cols}
                    ml_score = detector.score_single(feature_dict)
                except Exception:
                    ml_score = range_score
            else:
                ml_score = range_score
        else:
            ml_score = range_score
    else:
        ml_score = range_score
    
    # BLEND SCORES: Use the MORE PROPORTIONAL of the two scores
    # ML detector tends to be binary (low or max), range check is proportional
    # For better severity graduation:
    # - If range_score indicates mild fault, don't let ML override to critical
    # - Use weighted average: 40% ML, 60% range for more proportional response
    if ml_score > 0.7 and range_score < 0.4:
        # ML says critical but range says mild/moderate - trust range more
        anomaly_score = range_score * 0.7 + ml_score * 0.3
    elif ml_score < 0.2 and range_score > 0.3:
        # ML says healthy but range says fault - trust range
        anomaly_score = range_score
    else:
        # Normal blending
        anomaly_score = range_score * 0.6 + ml_score * 0.4
    
    anomaly_score = min(0.98, max(0.0, anomaly_score))  # Clamp to [0, 0.98]
    
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
    format: str = Query(default="pdf", description="Report format: pdf, xlsx, or industrial")
):
    """
    Generate and download a health report.
    
    Uses the latest health assessment for the asset.
    
    Formats:
    - pdf: Basic health certificate (1-page)
    - xlsx: Excel spreadsheet format
    - industrial: 5-page Industrial Asset Health Certificate (recommended)
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
    
    # Get current sensor readings for the industrial report
    current_readings = None
    if asset_id in _sensor_history and len(_sensor_history[asset_id]) > 0:
        latest = _sensor_history[asset_id][-1]
        current_readings = {
            'voltage_v': latest.get('voltage_v', 230.0),
            'current_a': latest.get('current_a', 15.0),
            'power_factor': latest.get('power_factor', 0.95),
            'vibration_g': latest.get('vibration_g', 0.0),
        }
    
    # Get sensor history for reports
    sensor_data = _sensor_history.get(asset_id, [])
    
    if format.lower() == "xlsx":
        content = generate_excel_report(report, sensor_data)
        filename = generate_filename(asset_id, report.timestamp, "xlsx")
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif format.lower() == "industrial":
        # 5-page Industrial Asset Health Certificate
        content = generate_industrial_report(report, current_readings, sensor_data)
        filename = generate_industrial_filename(asset_id, report.timestamp)
        media_type = "application/pdf"
    else:
        content = generate_pdf_report(report, sensor_data)
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
    timestamp = datetime.now(timezone.utc)
    reading = {
        "timestamp": timestamp.isoformat(),
        "voltage_v": request.voltage_v,
        "current_a": request.current_a,
        "power_factor": request.power_factor,
        "vibration_g": request.vibration_g,
        "is_faulty": detected_faulty
    }
    
    _sensor_history[request.asset_id].append(reading)
    
    # Persist to InfluxDB (with fallback to mock mode)
    db.write_point(
        measurement="sensor_events",
        tags={
            "asset_id": request.asset_id,
            "asset_type": "motor",
            "is_faulty": str(detected_faulty).lower()
        },
        fields={
            "voltage_v": request.voltage_v,
            "current_a": request.current_a,
            "power_factor": request.power_factor,
            "vibration_g": request.vibration_g,
        },
        timestamp=timestamp
    )
    
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
