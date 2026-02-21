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
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field

# Import existing modules for data generation and baseline building
from backend.api.integration_routes import (
    _sensor_history, _baselines, _detectors,
    BaselineBuilder, AnomalyDetector
)
from backend.database import db
from backend.ml.batch_features import extract_batch_features, extract_multi_window_features
from backend.ml.batch_detector import BatchAnomalyDetector

# pandas is lazy-loaded inside functions to keep cold-start fast

# Batch detector storage (one per asset)
_batch_detectors: Dict[str, BatchAnomalyDetector] = {}


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
    JITTER = "JITTER"     # Normal averages but high variance / noise
    DEFAULT = "DEFAULT"   # Current random fault behavior


class FaultSeverity(str, Enum):
    """Severity levels for fault injection."""
    MILD = "MILD"         # Targets MODERATE risk (health 50-74)
    MEDIUM = "MEDIUM"     # Targets HIGH risk (health 25-49)
    SEVERE = "SEVERE"     # Targets CRITICAL risk (health 0-24)


class SystemStateManager:
    """Thread-safe singleton for managing system state and validation metrics."""
    
    def __init__(self):
        self._state = SystemState.IDLE
        self._message = "System ready. Click 'Calibrate' to begin."
        self._started_at: Optional[datetime] = None
        self._fault_type: Optional[FaultType] = None
        self._fault_severity: Optional[FaultSeverity] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._active_thread: Optional[threading.Thread] = None
        
        # Validation Metrics
        self._training_samples = 0
        self._healthy_total = 0
        self._healthy_correct = 0  # Healthy classified as LOW risk
        self._faulty_total = 0
        self._faulty_correct = 0   # Faulty classified as HIGH+ risk
    
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
    
    @property
    def fault_severity(self) -> Optional[FaultSeverity]:
        with self._lock:
            return self._fault_severity
    
    @property
    def training_samples(self) -> int:
        with self._lock:
            return self._training_samples
    
    @property
    def healthy_stability(self) -> float:
        """Healthy Stability: % of healthy points classified as LOW risk."""
        with self._lock:
            if self._healthy_total == 0:
                return 100.0
            return round((self._healthy_correct / self._healthy_total) * 100, 1)
    
    @property
    def fault_capture_rate(self) -> float:
        """Fault Detection Rate: % of faulty points classified as HIGH+ risk."""
        with self._lock:
            if self._faulty_total == 0:
                return 100.0
            return round((self._faulty_correct / self._faulty_total) * 100, 1)
    
    def set_state(
        self, 
        state: SystemState, 
        message: str, 
        fault_type: Optional[FaultType] = None,
        fault_severity: Optional[FaultSeverity] = None
    ):
        with self._lock:
            self._state = state
            self._message = message
            self._started_at = datetime.now(timezone.utc)
            self._fault_type = fault_type
            self._fault_severity = fault_severity
    
    def set_training_samples(self, count: int):
        with self._lock:
            self._training_samples = count
    
    def reset_metrics(self):
        """Reset validation metrics (called on calibrate/stop)."""
        with self._lock:
            self._healthy_total = 0
            self._healthy_correct = 0
            self._faulty_total = 0
            self._faulty_correct = 0
    
    def record_healthy_classification(self, is_low_risk: bool):
        """Record a healthy point classification."""
        with self._lock:
            self._healthy_total += 1
            if is_low_risk:
                self._healthy_correct += 1
    
    def record_faulty_classification(self, is_high_risk: bool):
        """Record a faulty point classification."""
        with self._lock:
            self._faulty_total += 1
            if is_high_risk:
                self._faulty_correct += 1
    
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
    """Response for GET /system/state with validation metrics."""
    state: str
    message: str
    started_at: Optional[datetime] = None
    fault_type: Optional[str] = None
    fault_severity: Optional[str] = None
    # Validation Metrics
    training_samples: int = 0
    healthy_stability: float = 100.0
    fault_capture_rate: float = 100.0


class ActionResponse(BaseModel):
    """Response for action endpoints."""
    status: str
    message: str
    state: str


# =============================================================================
# BACKGROUND TASK FUNCTIONS
# =============================================================================

def generate_sensor_reading(
    asset_id: str, 
    is_faulty: bool = False, 
    fault_type: FaultType = FaultType.DEFAULT,
    severity: FaultSeverity = FaultSeverity.SEVERE
):
    """
    Generate a single sensor reading (inline, no subprocess).
    
    Healthy baseline (for reference):
    - Voltage: 230V ± 2V → Range ~226-234V
    - Current: 15A ± 1A → Range ~13-17A
    - Power Factor: 0.92 ± 0.02 → Range ~0.88-0.96
    - Vibration: 0.15g ± 0.03g → Range ~0.09-0.21g
    
    Severity levels target different risk levels:
    - MILD: Just outside baseline → MODERATE risk (health 50-74)
    - MEDIUM: Moderately outside → HIGH risk (health 25-49)  
    - SEVERE: Far outside → CRITICAL risk (health 0-24)
    
    JITTER fault type: Produces normal AVERAGES but abnormal VARIANCE.
    Individual readings oscillate wildly around the healthy mean.
    The old 1Hz average model misses this; the batch-feature model catches it.
    """
    import random
    
    if is_faulty and fault_type == FaultType.JITTER:
        # ── JITTER FAULT: average looks healthy, variance is extreme ──
        # Severity controls how wild the oscillation is
        jitter_config = {
            FaultSeverity.MILD:   {"v_jitter": 8,  "c_jitter": 2,  "pf_jitter": 0.06, "vib_jitter": 0.10},
            FaultSeverity.MEDIUM: {"v_jitter": 15, "c_jitter": 4,  "pf_jitter": 0.10, "vib_jitter": 0.20},
            FaultSeverity.SEVERE: {"v_jitter": 25, "c_jitter": 7,  "pf_jitter": 0.15, "vib_jitter": 0.40},
        }
        jcfg = jitter_config[severity]
        
        # Means are HEALTHY, but each point deviates wildly (high std)
        voltage = 230.0 + random.uniform(-jcfg["v_jitter"], jcfg["v_jitter"])
        current = 15.0 + random.uniform(-jcfg["c_jitter"], jcfg["c_jitter"])
        power_factor = 0.92 + random.uniform(-jcfg["pf_jitter"], jcfg["pf_jitter"])
        vibration = max(0.05, 0.15 + random.uniform(-jcfg["vib_jitter"], jcfg["vib_jitter"]))
        
    elif is_faulty:
        # Severity multipliers for how far outside baseline
        # MILD = just crossing the boundary, SEVERE = way beyond
        severity_config = {
            FaultSeverity.MILD: {
                'voltage_offset': (5, 10),      # 235-240V (just above 234V max)
                'current_offset': (1, 3),       # 16-18A (just above 17A max)
                'pf_drop': (0.05, 0.08),        # 0.84-0.87 (just below 0.88 min)
                'vibration_mult': (1.3, 1.8),   # 0.20-0.27g (just above 0.21g max)
            },
            FaultSeverity.MEDIUM: {
                'voltage_offset': (10, 25),     # 240-255V
                'current_offset': (3, 7),       # 18-22A
                'pf_drop': (0.08, 0.15),        # 0.77-0.84
                'vibration_mult': (2.0, 4.0),   # 0.30-0.60g
            },
            FaultSeverity.SEVERE: {
                'voltage_offset': (25, 50),     # 255-280V
                'current_offset': (7, 15),      # 22-30A
                'pf_drop': (0.15, 0.30),        # 0.62-0.77
                'vibration_mult': (5.0, 15.0),  # 0.75-2.25g
            }
        }
        
        config = severity_config[severity]
        
        if fault_type == FaultType.SPIKE:
            # Sudden spike - use upper end of severity range
            v_off = random.uniform(*config['voltage_offset']) * 1.2
            c_off = random.uniform(*config['current_offset']) * 1.2
            pf_drop = random.uniform(*config['pf_drop']) * 1.2
            vib_mult = random.uniform(*config['vibration_mult']) * 1.3
        elif fault_type == FaultType.DRIFT:
            # Gradual drift - use lower end of severity range
            v_off = random.uniform(config['voltage_offset'][0], 
                                   (config['voltage_offset'][0] + config['voltage_offset'][1]) / 2)
            c_off = random.uniform(config['current_offset'][0],
                                   (config['current_offset'][0] + config['current_offset'][1]) / 2)
            pf_drop = random.uniform(config['pf_drop'][0],
                                     (config['pf_drop'][0] + config['pf_drop'][1]) / 2)
            vib_mult = random.uniform(config['vibration_mult'][0],
                                      (config['vibration_mult'][0] + config['vibration_mult'][1]) / 2)
        else:  # DEFAULT - random within severity range
            v_off = random.uniform(*config['voltage_offset'])
            c_off = random.uniform(*config['current_offset'])
            pf_drop = random.uniform(*config['pf_drop'])
            vib_mult = random.uniform(*config['vibration_mult'])
        
        # Apply to healthy baseline values
        voltage = 230 + v_off + random.gauss(0, 1)
        current = 15 + c_off + random.gauss(0, 0.5)
        power_factor = 0.92 - pf_drop + random.gauss(0, 0.01)
        vibration = 0.15 * vib_mult + random.gauss(0, 0.02)
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
    Background task: BURST MODE calibration with 1000 samples.
    Generates training data instantly (no live waiting).
    """
    try:
        # Reset metrics for new calibration
        _state_manager.reset_metrics()
        
        # Phase 1: BURST GENERATE 1000 healthy samples (instant)
        _state_manager.set_state(
            SystemState.CALIBRATING, 
            "Burst generating 1,000 training samples..."
        )
        
        if asset_id not in _sensor_history:
            _sensor_history[asset_id] = []
        
        BURST_SAMPLES = 1000
        burst_data = []
        
        # Generate all samples instantly (no sleep)
        for i in range(BURST_SAMPLES):
            if _state_manager.should_stop():
                _state_manager.set_state(SystemState.IDLE, "Calibration cancelled.")
                return
            
            reading = generate_sensor_reading(asset_id, is_faulty=False)
            # Spread timestamps across the last hour for realistic baseline
            fake_time = datetime.now(timezone.utc) - timedelta(seconds=(BURST_SAMPLES - i) * 3.6)
            reading["timestamp"] = fake_time.isoformat()
            reading["is_faulty"] = False
            burst_data.append(reading)
            
            # Persist to InfluxDB (every 10th sample to avoid overwhelming)
            # NOTE: is_faulty is stored as FIELD (not tag) to prevent table fragmentation
            if i % 10 == 0:
                db.write_point(
                    measurement="sensor_events",
                    tags={
                        "asset_id": asset_id,
                        "asset_type": "motor",
                        "source": "calibration"
                    },
                    fields={
                        "voltage_v": reading["voltage_v"],
                        "current_a": reading["current_a"],
                        "power_factor": reading["power_factor"],
                        "vibration_g": reading["vibration_g"],
                        "is_faulty": False,
                    },
                    timestamp=fake_time
                )
            
            # Update progress every 100 samples
            if i % 100 == 0:
                _state_manager.set_state(
                    SystemState.CALIBRATING,
                    f"Generating training data... {i}/{BURST_SAMPLES}"
                )
        
        # Store in history (keep last 100 for display, full for training)
        _sensor_history[asset_id] = burst_data[-100:]
        _state_manager.set_training_samples(BURST_SAMPLES)
        
        # Phase 2: Build baseline from burst data
        _state_manager.set_state(SystemState.CALIBRATING, "Building baseline profile from 1,000 samples...")
        
        import pandas as pd
        df = pd.DataFrame(burst_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
        df.set_index('timestamp', inplace=True)
        df['is_fault_injected'] = False
        
        builder = BaselineBuilder()
        baseline = builder.build(df, asset_id=asset_id)
        _baselines[asset_id] = baseline
        
        # Phase 3: Train LEGACY anomaly detector (backward compat)
        _state_manager.set_state(SystemState.CALIBRATING, "Training anomaly model on 1,000 samples...")
        
        from backend.features.calculator import compute_all_features
        
        feature_data = []
        # Sample every 10th point for features (100 feature samples)
        for i in range(50, len(df), 10):
            row = df.iloc[i]
            features = compute_all_features(df.iloc[:i+1], i, row.get('power_factor', 0.9))
            feature_cols = ['voltage_rolling_mean_1h', 'current_spike_count', 
                           'power_factor_efficiency_score', 'vibration_intensity_rms']
            if all(features.get(col) is not None for col in feature_cols):
                feature_data.append({col: features[col] for col in feature_cols})
        
        if len(feature_data) >= 10:
            import pandas as pd
            feature_df = pd.DataFrame(feature_data)
            detector = AnomalyDetector(asset_id=asset_id, contamination=0.05)
            detector.train(feature_df)
            _detectors[asset_id] = detector
        
        # Phase 3b: Train BATCH FEATURE detector (Phase 5 — 100Hz statistical features)
        _state_manager.set_state(
            SystemState.CALIBRATING,
            "Training batch-feature model (16-D statistical features)..."
        )
        
        batch_feature_rows = extract_multi_window_features(burst_data, window_size=100)
        if len(batch_feature_rows) >= 10:
            batch_det = BatchAnomalyDetector(asset_id=asset_id)
            batch_det.train(batch_feature_rows)
            _batch_detectors[asset_id] = batch_det
            print(f"[SYSTEM] BatchDetector trained on {len(batch_feature_rows)} windows (16-D features)")
        else:
            print(f"[SYSTEM] WARNING: Only {len(batch_feature_rows)} batch windows — need 10+ for training")
        
        # CALIBRATION COMPLETE
        _state_manager.set_state(
            SystemState.MONITORING_HEALTHY,
            f"Calibration complete. Trained on {BURST_SAMPLES} samples."
        )
        
        # Continue generating healthy monitoring data with metrics tracking
        # Phase 5: Batch feature inference — extract features from 100 raw points,
        # run through BatchAnomalyDetector, set is_faulty based on score
        while not _state_manager.should_stop():
            if _state_manager.state != SystemState.MONITORING_HEALTHY:
                break
            
            # Batch: Generate 100 points with 10ms spacing
            batch_payload = []
            raw_batch = []
            base_ms = int(time.time() * 1000)
            
            for i in range(100):
                reading = generate_sensor_reading(asset_id, is_faulty=False)
                ts_ms = base_ms + (i * 10)
                reading["timestamp"] = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
                raw_batch.append(reading)
            
            # PHASE 5: Batch-feature anomaly detection (replaces per-point range check)
            is_batch_anomaly = False
            if asset_id in _batch_detectors and _batch_detectors[asset_id].is_trained:
                try:
                    batch_score = _batch_detectors[asset_id].score_raw_batch(raw_batch)
                    is_batch_anomaly = batch_score > 0.65
                except Exception:
                    is_batch_anomaly = False
            elif asset_id in _baselines:
                # Fallback to range check if no batch detector
                # Phase 7: Widened from 10% → 25% to suppress Gaussian noise false positives
                bl = _baselines[asset_id]
                latest = raw_batch[-1]
                for signal_name, value in [('voltage_v', latest['voltage_v']),
                                           ('current_a', latest['current_a']),
                                           ('power_factor', latest['power_factor']),
                                           ('vibration_g', latest['vibration_g'])]:
                    if signal_name in bl.signal_profiles:
                        profile = bl.signal_profiles[signal_name]
                        tolerance = (profile.max - profile.min) * 0.25
                        if value < (profile.min - tolerance) or value > (profile.max + tolerance):
                            is_batch_anomaly = True
                            break
            
            # Stamp all points in this batch with the batch-level verdict
            for i, reading in enumerate(raw_batch):
                ts_ms = base_ms + (i * 10)
                reading["is_faulty"] = is_batch_anomaly
                _sensor_history[asset_id].append(reading)
                
                batch_payload.append({
                    "tags": {
                        "asset_id": asset_id,
                        "asset_type": "motor",
                        "source": "healthy_monitoring"
                    },
                    "fields": {
                        "voltage_v": reading["voltage_v"],
                        "current_a": reading["current_a"],
                        "power_factor": reading["power_factor"],
                        "vibration_g": reading["vibration_g"],
                        "is_faulty": is_batch_anomaly,
                    },
                    "timestamp_ms": ts_ms
                })
                
                _state_manager.record_healthy_classification(is_low_risk=(not is_batch_anomaly))
            
            # Write batch of 100 points in single API call
            db.write_batch(measurement="sensor_events", points=batch_payload)
            print(f"[SYSTEM] Batch of 100 points written to InfluxDB (healthy_monitoring)")
            
            # Keep only last 100 readings for display
            if len(_sensor_history[asset_id]) > 100:
                _sensor_history[asset_id] = _sensor_history[asset_id][-100:]
            
            time.sleep(1.0)
    
    except Exception as e:
        _state_manager.set_state(SystemState.IDLE, f"Calibration failed: {str(e)}")


def run_fault_injection(asset_id: str, fault_type: FaultType, severity: FaultSeverity):
    """Background task: Generate faulty sensor data with batch-feature ML detection.
    
    Phase 5: Uses BatchAnomalyDetector for inference on each 1-second window.
    This enables detection of JITTER faults (normal means, abnormal variance).
    """
    try:
        while not _state_manager.should_stop():
            if _state_manager.state != SystemState.FAULT_INJECTION:
                break
            
            # Batch: Generate 100 points with 10ms spacing
            batch_payload = []
            raw_batch = []
            base_ms = int(time.time() * 1000)
            
            for i in range(100):
                reading = generate_sensor_reading(
                    asset_id, 
                    is_faulty=True, 
                    fault_type=fault_type,
                    severity=severity
                )
                ts_ms = base_ms + (i * 10)
                reading["timestamp"] = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
                raw_batch.append(reading)
            
            # PHASE 5: Batch-feature anomaly detection
            is_anomaly = True  # Default for fault injection
            batch_features = None
            if asset_id in _batch_detectors and _batch_detectors[asset_id].is_trained:
                try:
                    batch_features = extract_batch_features(raw_batch)
                    batch_score = _batch_detectors[asset_id].score_batch(batch_features)
                    is_anomaly = batch_score > 0.5  # Lower threshold for fault detection
                except Exception:
                    is_anomaly = True
            elif asset_id in _baselines:
                # Fallback to range check
                bl = _baselines[asset_id]
                latest = raw_batch[-1]
                for signal_name, value in [('voltage_v', latest['voltage_v']),
                                           ('current_a', latest['current_a']),
                                           ('power_factor', latest['power_factor']),
                                           ('vibration_g', latest['vibration_g'])]:
                    if signal_name in bl.signal_profiles:
                        profile = bl.signal_profiles[signal_name]
                        range_size = profile.max - profile.min
                        tolerance = range_size * 0.5
                        if value < (profile.min - tolerance) or value > (profile.max + tolerance):
                            is_anomaly = True
                            break
            
            # Store batch features in the last reading for event engine narration
            for i, reading in enumerate(raw_batch):
                ts_ms = base_ms + (i * 10)
                reading["is_faulty"] = is_anomaly
                if i == len(raw_batch) - 1 and batch_features:
                    reading["_batch_features"] = batch_features
                _sensor_history[asset_id].append(reading)
                
                batch_payload.append({
                    "tags": {
                        "asset_id": asset_id,
                        "asset_type": "motor",
                        "source": "fault_injection",
                        "fault_type": fault_type.value,
                        "severity": severity.value
                    },
                    "fields": {
                        "voltage_v": reading["voltage_v"],
                        "current_a": reading["current_a"],
                        "power_factor": reading["power_factor"],
                        "vibration_g": reading["vibration_g"],
                        "is_faulty": is_anomaly,
                    },
                    "timestamp_ms": ts_ms
                })
                
                _state_manager.record_faulty_classification(is_high_risk=is_anomaly)
            
            # Write batch of 100 points in single API call
            db.write_batch(measurement="sensor_events", points=batch_payload)
            print(f"[SYSTEM] Batch of 100 points written to InfluxDB (fault_injection)")
            
            # Keep only last 100 readings for display
            if len(_sensor_history[asset_id]) > 100:
                _sensor_history[asset_id] = _sensor_history[asset_id][-100:]
            
            time.sleep(1.0)
    
    except Exception as e:
        _state_manager.set_state(SystemState.IDLE, f"Fault injection failed: {str(e)}")


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/state", response_model=StateResponse)
async def get_system_state():
    """Get current system state with validation metrics."""
    return StateResponse(
        state=_state_manager.state.value,
        message=_state_manager.message,
        started_at=_state_manager.started_at,
        fault_type=_state_manager.fault_type.value if _state_manager.fault_type else None,
        fault_severity=_state_manager.fault_severity.value if _state_manager.fault_severity else None,
        training_samples=_state_manager.training_samples,
        healthy_stability=_state_manager.healthy_stability,
        fault_capture_rate=_state_manager.fault_capture_rate
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
    fault_type: FaultType = Query(default=FaultType.DEFAULT, description="Type of fault to inject"),
    severity: FaultSeverity = Query(default=FaultSeverity.SEVERE, description="Severity of fault (MILD=MODERATE risk, MEDIUM=HIGH risk, SEVERE=CRITICAL risk)")
):
    """
    Start fault injection (background task).
    
    Injects faulty sensor data to trigger anomaly detection.
    
    Severity levels:
    - MILD: Targets MODERATE risk (health 50-74)
    - MEDIUM: Targets HIGH risk (health 25-49)
    - SEVERE: Targets CRITICAL risk (health 0-24)
    
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
        f"Injecting {severity.value} {fault_type.value} fault...",
        fault_type=fault_type,
        fault_severity=severity
    )
    
    thread = threading.Thread(
        target=run_fault_injection, 
        args=(asset_id, fault_type, severity), 
        daemon=True
    )
    _state_manager.set_active_thread(thread)
    thread.start()
    
    return ActionResponse(
        status="started",
        message=f"Fault injection started ({severity.value} {fault_type.value})",
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
    
    # Start healthy monitoring with Phase 5 batch-feature inference
    def resume_healthy_monitoring():
        """Generate healthy data with batch-feature ML detection for natural recovery."""
        while not _state_manager.should_stop():
            if _state_manager.state != SystemState.MONITORING_HEALTHY:
                break
            
            batch_payload = []
            raw_batch = []
            base_ms = int(time.time() * 1000)
            
            for i in range(100):
                reading = generate_sensor_reading(asset_id, is_faulty=False)
                ts_ms = base_ms + (i * 10)
                reading["timestamp"] = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
                raw_batch.append(reading)
            
            # Phase 5: Batch-feature anomaly detection
            is_anomaly = False
            if asset_id in _batch_detectors and _batch_detectors[asset_id].is_trained:
                try:
                    batch_score = _batch_detectors[asset_id].score_raw_batch(raw_batch)
                    is_anomaly = batch_score > 0.65
                except Exception:
                    is_anomaly = False
            elif asset_id in _baselines:
                # Phase 7: Widened from 10% → 25% to suppress Gaussian noise false positives
                bl = _baselines[asset_id]
                latest = raw_batch[-1]
                for signal_name, value in [('voltage_v', latest['voltage_v']),
                                           ('current_a', latest['current_a']),
                                           ('power_factor', latest['power_factor']),
                                           ('vibration_g', latest['vibration_g'])]:
                    if signal_name in bl.signal_profiles:
                        profile = bl.signal_profiles[signal_name]
                        tolerance = (profile.max - profile.min) * 0.25
                        if value < (profile.min - tolerance) or value > (profile.max + tolerance):
                            is_anomaly = True
                            break
            
            for i, reading in enumerate(raw_batch):
                ts_ms = base_ms + (i * 10)
                reading["is_faulty"] = is_anomaly
                _sensor_history[asset_id].append(reading)
                
                batch_payload.append({
                    "tags": {
                        "asset_id": asset_id,
                        "asset_type": "motor",
                        "source": "healthy_monitoring"
                    },
                    "fields": {
                        "voltage_v": reading["voltage_v"],
                        "current_a": reading["current_a"],
                        "power_factor": reading["power_factor"],
                        "vibration_g": reading["vibration_g"],
                        "is_faulty": is_anomaly,
                    },
                    "timestamp_ms": ts_ms
                })
            
            # Write batch of 100 points in single API call
            db.write_batch(measurement="sensor_events", points=batch_payload)
            print(f"[SYSTEM] Batch of 100 points written to InfluxDB (resume_healthy)")
            
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
    
    # Reset metrics for new session
    _state_manager.reset_metrics()
    _state_manager.set_training_samples(0)
    
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


@router.post("/purge", response_model=ActionResponse)
async def purge_and_recalibrate():
    """
    Deep System Purge — wipe ALL data and return to blank state.

    Actions:
    1. Stop any running background task.
    2. Delete all entries in the InfluxDB sensor_data bucket.
    3. Clear in-memory sensor history, baselines, detectors.
    4. Reset system state to IDLE.

    After purge the dashboard shows a blank canvas and the user
    must click Calibrate to restart the demo narrative.
    """
    # 1. Stop background task if running
    _state_manager.stop_background_task()

    # 2. Delete all InfluxDB data
    db.delete_all()

    # 3. Wipe in-memory state
    _sensor_history.clear()
    _baselines.clear()
    _detectors.clear()
    _batch_detectors.clear()

    # 4. Reset state manager
    _state_manager.reset_metrics()
    _state_manager.set_training_samples(0)
    _state_manager.set_state(
        SystemState.IDLE,
        "System purged. All data wiped. Click 'Calibrate' to begin fresh."
    )

    return ActionResponse(
        status="purged",
        message="All data purged. InfluxDB bucket cleared, ML baselines wiped. System is IDLE.",
        state=SystemState.IDLE.value
    )
