"""
System Control Routes — Frontend-driven demo orchestration (Phase 12+)

Provides lifecycle control endpoints for terminal-free demo:
- GET /system/state — Get current system state
- POST /system/calibrate — Start calibration (background task)
- POST /system/inject-fault — Start fault injection (background task)  
- POST /system/reset — Stop faults, return to healthy
"""

import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field

# Import existing modules for data generation and baseline building
from backend.api.integration_routes import (
    _sensor_history, _baselines, _detectors,
    BaselineBuilder, AnomalyDetector
)
import pandas as pd


router = APIRouter(prefix="/system", tags=["System Control"])


# =============================================================================
# SYSTEM STATE SINGLETON
# =============================================================================

class SystemState(str, Enum):
    """Possible system states for demo lifecycle."""
    IDLE = "IDLE"
    CALIBRATING = "CALIBRATING"
    MONITORING_HEALTHY = "MONITORING_HEALTHY"
    FAULT_INJECTION = "FAULT_INJECTION"


class FaultType(str, Enum):
    """Types of faults that can be injected."""
    SPIKE = "SPIKE"       # Sudden extreme values
    DRIFT = "DRIFT"       # Gradual degradation
    DEFAULT = "DEFAULT"   # Current random fault behavior


class SystemStateManager:
    """Thread-safe singleton for managing system state."""
    
    def __init__(self):
        self._state = SystemState.IDLE
        self._message = "System ready. Click 'Calibrate' to begin."
        self._started_at: Optional[datetime] = None
        self._fault_type: Optional[FaultType] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._active_thread: Optional[threading.Thread] = None
    
    @property
    def state(self) -> SystemState:
        with self._lock:
            return self._state
    
    @property
    def message(self) -> str:
        with self._lock:
            return self._message
    
    @property
    def started_at(self) -> Optional[datetime]:
        with self._lock:
            return self._started_at
    
    @property
    def fault_type(self) -> Optional[FaultType]:
        with self._lock:
            return self._fault_type
    
    def set_state(self, state: SystemState, message: str, fault_type: Optional[FaultType] = None):
        with self._lock:
            self._state = state
            self._message = message
            self._started_at = datetime.now(timezone.utc)
            self._fault_type = fault_type
    
    def stop_background_task(self):
        """Signal background thread to stop."""
        self._stop_event.set()
        if self._active_thread and self._active_thread.is_alive():
            self._active_thread.join(timeout=2.0)
        self._stop_event.clear()
    
    def should_stop(self) -> bool:
        """Check if background task should stop."""
        return self._stop_event.is_set()
    
    def set_active_thread(self, thread: threading.Thread):
        self._active_thread = thread


# Global state manager instance
_state_manager = SystemStateManager()


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class StateResponse(BaseModel):
    """Response for GET /system/state."""
    state: str
    message: str
    started_at: Optional[datetime] = None
    fault_type: Optional[str] = None


class ActionResponse(BaseModel):
    """Response for action endpoints."""
    status: str
    message: str
    state: str


# =============================================================================
# BACKGROUND TASK FUNCTIONS
# =============================================================================

def generate_sensor_reading(asset_id: str, is_faulty: bool = False, fault_type: FaultType = FaultType.DEFAULT):
    """Generate a single sensor reading (inline, no subprocess)."""
    import random
    
    if is_faulty:
        if fault_type == FaultType.SPIKE:
            # Extreme sudden spike
            voltage = random.uniform(270, 300)
            current = random.uniform(22, 30)
            power_factor = random.uniform(0.55, 0.70)
            vibration = random.uniform(1.5, 3.0)
        elif fault_type == FaultType.DRIFT:
            # Gradual degradation (moderate values)
            voltage = random.uniform(238, 250)
            current = random.uniform(17, 20)
            power_factor = random.uniform(0.78, 0.85)
            vibration = random.uniform(0.25, 0.45)
        else:  # DEFAULT
            # Random fault behavior
            voltage = random.uniform(245, 280)
            current = random.uniform(18, 25)
            power_factor = random.uniform(0.60, 0.80)
            vibration = random.uniform(0.5, 2.5)
    else:
        # Healthy readings
        voltage = random.gauss(230, 2)
        current = random.gauss(15, 1)
        power_factor = random.gauss(0.92, 0.02)
        vibration = random.gauss(0.15, 0.03)
    
    # Clamp values
    voltage = max(200, min(300, voltage))
    current = max(5, min(30, current))
    power_factor = max(0.5, min(1.0, power_factor))
    vibration = max(0.05, min(5.0, vibration))
    
    return {
        "voltage_v": round(voltage, 2),
        "current_a": round(current, 2),
        "power_factor": round(power_factor, 3),
        "vibration_g": round(vibration, 3)
    }


def run_calibration(asset_id: str):
    """
    Background task: Generate healthy data, build baseline, train model.
    Uses signal-based completion (not time-based).
    """
    try:
        # Phase 1: Generate healthy data (30 samples)
        _state_manager.set_state(
            SystemState.CALIBRATING, 
            "Generating healthy sensor data..."
        )
        
        if asset_id not in _sensor_history:
            _sensor_history[asset_id] = []
        
        samples_needed = 30
        for i in range(samples_needed):
            if _state_manager.should_stop():
                _state_manager.set_state(SystemState.IDLE, "Calibration cancelled.")
                return
            
            reading = generate_sensor_reading(asset_id, is_faulty=False)
            reading["timestamp"] = datetime.now(timezone.utc).isoformat()
            reading["is_faulty"] = False
            _sensor_history[asset_id].append(reading)
            
            # Update progress
            progress = int((i + 1) / samples_needed * 50)
            _state_manager.set_state(
                SystemState.CALIBRATING,
                f"Generating healthy data... {progress}%"
            )
            time.sleep(0.5)  # 0.5s between samples
        
        # Phase 2: Build baseline
        _state_manager.set_state(SystemState.CALIBRATING, "Building baseline profile...")
        
        history = _sensor_history[asset_id]
        df = pd.DataFrame(history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        if 'is_faulty' in df.columns:
            healthy_df = df[df['is_faulty'] == False].copy()
            healthy_df['is_fault_injected'] = False
        else:
            healthy_df = df.copy()
            healthy_df['is_fault_injected'] = False
        
        builder = BaselineBuilder()
        baseline = builder.build(healthy_df, asset_id=asset_id)
        _baselines[asset_id] = baseline
        
        # Phase 3: Train anomaly detector
        _state_manager.set_state(SystemState.CALIBRATING, "Training anomaly detection model...")
        
        from backend.features.calculator import compute_all_features
        
        feature_data = []
        for i in range(10, len(healthy_df)):
            row = healthy_df.iloc[i]
            features = compute_all_features(healthy_df.iloc[:i+1], i, row.get('power_factor', 0.9))
            feature_cols = ['voltage_rolling_mean_1h', 'current_spike_count', 
                           'power_factor_efficiency_score', 'vibration_intensity_rms']
            if all(features.get(col) is not None for col in feature_cols):
                feature_data.append({col: features[col] for col in feature_cols})
        
        if len(feature_data) >= 5:
            feature_df = pd.DataFrame(feature_data)
            detector = AnomalyDetector(asset_id=asset_id, contamination=0.05)
            detector.train(feature_df)
            _detectors[asset_id] = detector
        
        # SIGNAL-BASED COMPLETION: Calibration finished
        _state_manager.set_state(
            SystemState.MONITORING_HEALTHY,
            "Calibration complete. System is monitoring."
        )
        
        # Continue generating healthy monitoring data
        while not _state_manager.should_stop():
            if _state_manager.state != SystemState.MONITORING_HEALTHY:
                break
            
            reading = generate_sensor_reading(asset_id, is_faulty=False)
            reading["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            # Auto-detect anomaly against baseline
            is_anomaly = False
            if asset_id in _baselines:
                bl = _baselines[asset_id]
                for signal_name, value in [('voltage_v', reading['voltage_v']),
                                           ('current_a', reading['current_a']),
                                           ('power_factor', reading['power_factor']),
                                           ('vibration_g', reading['vibration_g'])]:
                    if signal_name in bl.signal_profiles:
                        profile = bl.signal_profiles[signal_name]
                        tolerance = (profile.max - profile.min) * 0.1
                        if value < (profile.min - tolerance) or value > (profile.max + tolerance):
                            is_anomaly = True
                            break
            
            reading["is_faulty"] = is_anomaly
            _sensor_history[asset_id].append(reading)
            
            # Keep only last 1000 readings
            if len(_sensor_history[asset_id]) > 1000:
                _sensor_history[asset_id] = _sensor_history[asset_id][-1000:]
            
            time.sleep(1.0)
    
    except Exception as e:
        _state_manager.set_state(SystemState.IDLE, f"Calibration failed: {str(e)}")


def run_fault_injection(asset_id: str, fault_type: FaultType):
    """Background task: Generate faulty sensor data."""
    try:
        while not _state_manager.should_stop():
            if _state_manager.state != SystemState.FAULT_INJECTION:
                break
            
            reading = generate_sensor_reading(asset_id, is_faulty=True, fault_type=fault_type)
            reading["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            # Auto-detect against baseline (should flag as anomaly)
            is_anomaly = True  # Fault injection always produces anomalies
            if asset_id in _baselines:
                bl = _baselines[asset_id]
                for signal_name, value in [('voltage_v', reading['voltage_v']),
                                           ('current_a', reading['current_a']),
                                           ('power_factor', reading['power_factor']),
                                           ('vibration_g', reading['vibration_g'])]:
                    if signal_name in bl.signal_profiles:
                        profile = bl.signal_profiles[signal_name]
                        tolerance = (profile.max - profile.min) * 0.1
                        if value < (profile.min - tolerance) or value > (profile.max + tolerance):
                            is_anomaly = True
                            break
            
            reading["is_faulty"] = is_anomaly
            _sensor_history[asset_id].append(reading)
            
            # Keep only last 1000 readings
            if len(_sensor_history[asset_id]) > 1000:
                _sensor_history[asset_id] = _sensor_history[asset_id][-1000:]
            
            time.sleep(1.0)
    
    except Exception as e:
        _state_manager.set_state(SystemState.IDLE, f"Fault injection failed: {str(e)}")


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/state", response_model=StateResponse)
async def get_system_state():
    """Get current system state."""
    return StateResponse(
        state=_state_manager.state.value,
        message=_state_manager.message,
        started_at=_state_manager.started_at,
        fault_type=_state_manager.fault_type.value if _state_manager.fault_type else None
    )


@router.post("/calibrate", response_model=ActionResponse)
async def calibrate_system(
    asset_id: str = Query(default="Motor-01", description="Asset to calibrate")
):
    """
    Start system calibration (background task).
    
    Generates healthy data, builds baseline, trains anomaly model.
    State transitions: IDLE → CALIBRATING → MONITORING_HEALTHY
    """
    current_state = _state_manager.state
    
    if current_state not in [SystemState.IDLE]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot calibrate in state '{current_state.value}'. Must be IDLE."
        )
    
    # Stop any existing background task
    _state_manager.stop_background_task()
    
    # Start calibration in background thread
    thread = threading.Thread(target=run_calibration, args=(asset_id,), daemon=True)
    _state_manager.set_active_thread(thread)
    thread.start()
    
    return ActionResponse(
        status="started",
        message="Calibration started. Generating healthy data...",
        state=SystemState.CALIBRATING.value
    )


@router.post("/inject-fault", response_model=ActionResponse)
async def inject_fault(
    asset_id: str = Query(default="Motor-01", description="Asset to inject fault"),
    fault_type: FaultType = Query(default=FaultType.DEFAULT, description="Type of fault to inject")
):
    """
    Start fault injection (background task).
    
    Injects faulty sensor data to trigger anomaly detection.
    State transitions: MONITORING_HEALTHY → FAULT_INJECTION
    """
    current_state = _state_manager.state
    
    if current_state != SystemState.MONITORING_HEALTHY:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot inject fault in state '{current_state.value}'. Must be MONITORING_HEALTHY."
        )
    
    # Stop healthy monitoring
    _state_manager.stop_background_task()
    
    # Update state and start fault injection
    _state_manager.set_state(
        SystemState.FAULT_INJECTION,
        f"Injecting {fault_type.value} fault...",
        fault_type=fault_type
    )
    
    thread = threading.Thread(target=run_fault_injection, args=(asset_id, fault_type), daemon=True)
    _state_manager.set_active_thread(thread)
    thread.start()
    
    return ActionResponse(
        status="started",
        message=f"Fault injection started ({fault_type.value})",
        state=SystemState.FAULT_INJECTION.value
    )


@router.post("/reset", response_model=ActionResponse)
async def reset_system(
    asset_id: str = Query(default="Motor-01", description="Asset to reset")
):
    """
    Stop fault injection and return to healthy monitoring.
    
    State transitions: FAULT_INJECTION → MONITORING_HEALTHY
    """
    current_state = _state_manager.state
    
    if current_state not in [SystemState.FAULT_INJECTION, SystemState.MONITORING_HEALTHY]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reset in state '{current_state.value}'. Must be FAULT_INJECTION or MONITORING_HEALTHY."
        )
    
    # Stop fault injection
    _state_manager.stop_background_task()
    
    # Return to healthy monitoring
    _state_manager.set_state(
        SystemState.MONITORING_HEALTHY,
        "System reset. Monitoring healthy operation (True Recovery)."
    )
    
    # Start healthy monitoring with PROPER anomaly detection (True Recovery)
    def resume_healthy_monitoring():
        """Generate healthy data with proper baseline comparison for natural recovery."""
        while not _state_manager.should_stop():
            if _state_manager.state != SystemState.MONITORING_HEALTHY:
                break
            
            reading = generate_sensor_reading(asset_id, is_faulty=False)
            reading["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            # TRUE RECOVERY: Check against baseline (don't hardcode is_faulty)
            is_anomaly = False
            if asset_id in _baselines:
                bl = _baselines[asset_id]
                for signal_name, value in [('voltage_v', reading['voltage_v']),
                                           ('current_a', reading['current_a']),
                                           ('power_factor', reading['power_factor']),
                                           ('vibration_g', reading['vibration_g'])]:
                    if signal_name in bl.signal_profiles:
                        profile = bl.signal_profiles[signal_name]
                        tolerance = (profile.max - profile.min) * 0.1
                        if value < (profile.min - tolerance) or value > (profile.max + tolerance):
                            is_anomaly = True
                            break
            
            reading["is_faulty"] = is_anomaly
            _sensor_history[asset_id].append(reading)
            
            if len(_sensor_history[asset_id]) > 1000:
                _sensor_history[asset_id] = _sensor_history[asset_id][-1000:]
            
            time.sleep(1.0)
    
    thread = threading.Thread(target=resume_healthy_monitoring, daemon=True)
    _state_manager.set_active_thread(thread)
    thread.start()
    
    return ActionResponse(
        status="reset",
        message="System reset to healthy monitoring.",
        state=SystemState.MONITORING_HEALTHY.value
    )


@router.post("/stop", response_model=ActionResponse)
async def stop_session():
    """
    Stop monitoring session and return to IDLE state.
    
    Allows user to recalibrate without restarting the server.
    State transitions: MONITORING_HEALTHY | FAULT_INJECTION → IDLE
    """
    current_state = _state_manager.state
    
    if current_state == SystemState.IDLE:
        raise HTTPException(
            status_code=400,
            detail="System is already IDLE."
        )
    
    if current_state == SystemState.CALIBRATING:
        raise HTTPException(
            status_code=400,
            detail="Cannot stop during calibration. Please wait for it to complete."
        )
    
    # Stop background task
    _state_manager.stop_background_task()
    
    # Return to IDLE
    _state_manager.set_state(
        SystemState.IDLE,
        "Session stopped. Click 'Calibrate' to begin a new demo."
    )
    
    return ActionResponse(
        status="stopped",
        message="Session stopped. System is now IDLE.",
        state=SystemState.IDLE.value
    )
