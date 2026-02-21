"""
Event Engine — Transition-Based Event Generator

Core architectural rule: EVENTS ARE TRANSITIONS, NOT STATES.
We emit exactly ONE event when is_faulty changes (0→1 or 1→0),
never a duplicate event for the same sustained state.

The engine maintains a per-asset state tracker in memory (singleton).
Each call to `evaluate()` compares current is_faulty against the
previous value and returns zero or one event objects.

Event schema (JSON):
    {
        "timestamp": "2026-02-21T12:00:00+00:00",   # ISO 8601
        "type": "ANOMALY_DETECTED" | "ANOMALY_CLEARED" | "HEARTBEAT",
        "severity": "info" | "warning" | "critical",
        "message": "Plain-English narration of what changed."
    }
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from threading import Lock

logger = logging.getLogger(__name__)


# ============================================================================
# Event Type Constants
# ============================================================================

EVENT_ANOMALY_DETECTED = "ANOMALY_DETECTED"
EVENT_ANOMALY_CLEARED = "ANOMALY_CLEARED"
EVENT_HEARTBEAT = "HEARTBEAT"

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"


# ============================================================================
# Diagnostic Message Templates
# ============================================================================

def _build_anomaly_detected_message(sensor_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Build a plain-English explanation for an ANOMALY_DETECTED event.
    Inspects both raw sensor averages AND batch statistical features
    (Phase 5) to identify which signals are abnormal and WHY.
    """
    if not sensor_data:
        return "ANOMALY: Sensor readings have deviated from the established baseline."

    deviations = []

    # ── Phase 5: Check batch statistical features first (more descriptive) ──
    batch_feats = sensor_data.get("_batch_features")
    if batch_feats:
        # Vibration variance (noise / jitter detection)
        vib_std = batch_feats.get("vibration_g_std", 0.0)
        if vib_std > 0.06:   # healthy σ ≈ 0.02
            deviations.append(
                f"High vibration variance (mechanical jitter): σ={vib_std:.4f}g"
            )
        
        # Vibration peak-to-peak (transient spikes)
        vib_p2p = batch_feats.get("vibration_g_peak_to_peak", 0.0)
        if vib_p2p > 0.25:   # healthy p2p ≈ 0.10
            deviations.append(
                f"Vibration transient spike: peak-to-peak={vib_p2p:.3f}g"
            )
        
        # Voltage variance (grid instability)
        volt_std = batch_feats.get("voltage_v_std", 0.0)
        if volt_std > 5.0:    # healthy σ ≈ 2.0
            deviations.append(
                f"High voltage variance (grid instability): σ={volt_std:.2f}V"
            )
        
        # Voltage peak-to-peak
        volt_p2p = batch_feats.get("voltage_v_peak_to_peak", 0.0)
        if volt_p2p > 15.0:   # healthy p2p ≈ 8.0
            deviations.append(
                f"Voltage transient: peak-to-peak={volt_p2p:.1f}V"
            )
        
        # Current variance
        curr_std = batch_feats.get("current_a_std", 0.0)
        if curr_std > 3.0:    # healthy σ ≈ 1.0
            deviations.append(
                f"Current draw instability: σ={curr_std:.2f}A"
            )
        
        # Power factor variance
        pf_std = batch_feats.get("power_factor_std", 0.0)
        if pf_std > 0.04:    # healthy σ ≈ 0.01
            deviations.append(
                f"Power factor oscillating (load instability): σ={pf_std:.4f}"
            )

    # ── Legacy: Also check raw signal averages for non-batch faults ──
    voltage = sensor_data.get("voltage_v")
    if voltage is not None and (voltage > 240 or voltage < 220):
        direction = "spike" if voltage > 240 else "drop"
        deviations.append(f"Voltage {direction} detected ({voltage:.1f}V)")

    current = sensor_data.get("current_a")
    if current is not None and (current > 18 or current < 12):
        direction = "surge" if current > 18 else "drop"
        deviations.append(f"Current {direction} detected ({current:.1f}A)")

    power_factor = sensor_data.get("power_factor")
    if power_factor is not None and power_factor < 0.88:
        deviations.append(f"Power factor degradation ({power_factor:.3f})")

    vibration = sensor_data.get("vibration_g")
    if vibration is not None and vibration > 0.25:
        deviations.append(f"Vibration spike ({vibration:.3f}g) — possible bearing wear")

    if deviations:
        # Limit to top 4 for readability
        return "ANOMALY: " + "; ".join(deviations[:4]) + "."
    return "ANOMALY: Sensor readings have deviated from the established baseline."


def _build_anomaly_cleared_message() -> str:
    """Build a plain-English explanation for an ANOMALY_CLEARED event."""
    return "RECOVERY: All sensor readings have returned to within normal operating range."


# ============================================================================
# Per-Asset State Tracker
# ============================================================================

class _AssetState:
    """Tracks the previous is_faulty state for a single asset."""
    __slots__ = ("previous_is_faulty", "last_event_timestamp",
                 "_consecutive_faulty", "_consecutive_healthy")

    # Phase 7: Debounce — require N consecutive matching evaluations
    # before acknowledging a transition. At 1 eval/sec this equals N seconds.
    DEBOUNCE_COUNT = 2  # 2 consecutive seconds

    def __init__(self):
        self.previous_is_faulty: Optional[bool] = None  # None = unknown / first run
        self.last_event_timestamp: Optional[str] = None
        self._consecutive_faulty: int = 0
        self._consecutive_healthy: int = 0


# ============================================================================
# Event Engine (Singleton)
# ============================================================================

class EventEngine:
    """
    Thread-safe, per-asset event generator.

    Usage:
        from backend.events import event_engine

        events = event_engine.evaluate("Motor-01", is_faulty=True, sensor_snapshot={...})
        # Returns [] if no transition, or [event_dict] if state changed.
    """

    _instance: Optional["EventEngine"] = None
    _lock: Lock = Lock()

    def __new__(cls) -> "EventEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._states: Dict[str, _AssetState] = {}
        self._states_lock = Lock()
        self._initialized = True
        logger.info("[EventEngine] Initialized — transition-based event generator ready.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        asset_id: str,
        is_faulty: bool,
        timestamp: Optional[str] = None,
        sensor_snapshot: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Evaluate the current fault state for an asset.

        Returns an event ONLY on a state transition:
            - healthy → faulty  → ANOMALY_DETECTED (critical)
            - faulty  → healthy → ANOMALY_CLEARED  (info)
            - same state        → [] (no event)

        On first call (no prior state), we seed the tracker without
        emitting an event to avoid a false-positive on startup.

        Args:
            asset_id: Identifier of the asset (e.g. "Motor-01").
            is_faulty: Current anomaly boolean.
            timestamp: ISO 8601 string for the event (defaults to now).
            sensor_snapshot: Optional dict of the latest sensor reading
                             for diagnostic message enrichment.

        Returns:
            List of 0 or 1 event dicts.
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        with self._states_lock:
            # Ensure tracker exists for this asset
            if asset_id not in self._states:
                self._states[asset_id] = _AssetState()

            state = self._states[asset_id]

            # First-ever reading: seed state, no event
            if state.previous_is_faulty is None:
                state.previous_is_faulty = is_faulty
                state.last_event_timestamp = ts
                logger.info(
                    f"[EventEngine] {asset_id}: initial state seeded "
                    f"(is_faulty={is_faulty}). No event emitted."
                )
                return []

            # No transition → no event
            if is_faulty == state.previous_is_faulty:
                # Reset the opposite counter while maintaining current state
                if is_faulty:
                    state._consecutive_healthy = 0
                else:
                    state._consecutive_faulty = 0
                return []

            # --- PHASE 7: Debounce — count consecutive contrary readings ---
            if is_faulty:
                state._consecutive_faulty += 1
                state._consecutive_healthy = 0
            else:
                state._consecutive_healthy += 1
                state._consecutive_faulty = 0

            if is_faulty and state._consecutive_faulty < _AssetState.DEBOUNCE_COUNT:
                logger.debug(
                    f"[EventEngine] {asset_id}: faulty tick "
                    f"{state._consecutive_faulty}/{_AssetState.DEBOUNCE_COUNT} — debouncing"
                )
                return []
            if not is_faulty and state._consecutive_healthy < _AssetState.DEBOUNCE_COUNT:
                logger.debug(
                    f"[EventEngine] {asset_id}: healthy tick "
                    f"{state._consecutive_healthy}/{_AssetState.DEBOUNCE_COUNT} — debouncing"
                )
                return []

            # --- STATE TRANSITION CONFIRMED (passed debounce) ---
            state._consecutive_faulty = 0
            state._consecutive_healthy = 0

            if is_faulty and not state.previous_is_faulty:
                # healthy → faulty
                event = {
                    "timestamp": ts,
                    "type": EVENT_ANOMALY_DETECTED,
                    "severity": SEVERITY_CRITICAL,
                    "message": _build_anomaly_detected_message(sensor_snapshot),
                }
                logger.warning(
                    f"[EventEngine] {asset_id}: ANOMALY_DETECTED at {ts}"
                )
            else:
                # faulty → healthy
                event = {
                    "timestamp": ts,
                    "type": EVENT_ANOMALY_CLEARED,
                    "severity": SEVERITY_INFO,
                    "message": _build_anomaly_cleared_message(),
                }
                logger.info(
                    f"[EventEngine] {asset_id}: ANOMALY_CLEARED at {ts}"
                )

            # Update tracker
            state.previous_is_faulty = is_faulty
            state.last_event_timestamp = ts

            return [event]

    def get_state(self, asset_id: str) -> Optional[bool]:
        """Return the last-known is_faulty state for an asset, or None."""
        with self._states_lock:
            s = self._states.get(asset_id)
            return s.previous_is_faulty if s else None

    def reset(self, asset_id: Optional[str] = None) -> None:
        """
        Reset tracker(s).  If asset_id given, reset just that asset.
        Otherwise reset all assets.
        """
        with self._states_lock:
            if asset_id:
                self._states.pop(asset_id, None)
                logger.info(f"[EventEngine] Reset tracker for {asset_id}")
            else:
                self._states.clear()
                logger.info("[EventEngine] All asset trackers reset.")


# Module-level singleton
event_engine = EventEngine()
