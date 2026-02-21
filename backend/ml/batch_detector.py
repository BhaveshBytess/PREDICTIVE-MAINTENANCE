"""
Batch Anomaly Detector — Isolation Forest on 100Hz Statistical Features

Replaces the old point-inference model with a batch-feature model that
trains and scores on the 16-dimensional statistical feature vector
extracted from each 1-second window of 100Hz raw data.

Feature space (16 dimensions):
    voltage_v_mean, voltage_v_std, voltage_v_peak_to_peak, voltage_v_rms,
    current_a_mean, current_a_std, current_a_peak_to_peak, current_a_rms,
    power_factor_mean, power_factor_std, power_factor_peak_to_peak, power_factor_rms,
    vibration_g_mean, vibration_g_std, vibration_g_peak_to_peak, vibration_g_rms

Why batch features matter:
    A "Jitter Fault" where the average vibration is normal (0.15g) but
    variance spikes (std 0.08 vs healthy 0.02) is INVISIBLE to a model
    trained on 1Hz averages. This detector catches it because std and
    peak-to-peak are explicit features.

Training contract:
    - Train ONLY on healthy batch features.
    - One model per asset.
    - Deterministic (random_state=42).
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from .batch_features import (
    BATCH_FEATURE_NAMES,
    BATCH_FEATURE_COUNT,
    extract_batch_features,
)

logger = logging.getLogger(__name__)


# Hyperparameters
DEFAULT_CONTAMINATION = 0.05
DEFAULT_N_ESTIMATORS = 150   # More trees for 16-D space
DEFAULT_RANDOM_STATE = 42


class BatchAnomalyDetector:
    """
    Isolation Forest trained on batch statistical features.

    Score semantics (same as legacy detector):
        0.0 = Perfectly Normal (matches healthy batch-feature distribution)
        1.0 = Highly Anomalous (deviation from healthy batch-feature distribution)
    """

    def __init__(
        self,
        asset_id: str,
        contamination: float = DEFAULT_CONTAMINATION,
        n_estimators: int = DEFAULT_N_ESTIMATORS,
        random_state: int = DEFAULT_RANDOM_STATE,
    ):
        self.asset_id = asset_id
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state

        self._model: Optional[IsolationForest] = None
        self._scaler: Optional[StandardScaler] = None
        self._is_trained: bool = False
        self._training_timestamp: Optional[datetime] = None
        self._training_sample_count: int = 0
        self._threshold_score: float = 0.5  # Updated during training

        # Store healthy feature stats for explainability
        self._healthy_means: Optional[Dict[str, float]] = None
        self._healthy_stds: Optional[Dict[str, float]] = None

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, feature_rows: List[Dict[str, float]]) -> None:
        """
        Train on a list of healthy batch-feature dicts.

        Args:
            feature_rows: List of dicts, each with 16 keys from BATCH_FEATURE_NAMES.

        Raises:
            ValueError: If insufficient data or missing features.
        """
        if len(feature_rows) < 10:
            raise ValueError(
                f"Need >= 10 training windows, got {len(feature_rows)}"
            )

        # Build DataFrame
        df = pd.DataFrame(feature_rows)

        # Validate columns
        missing = [c for c in BATCH_FEATURE_NAMES if c not in df.columns]
        if missing:
            raise ValueError(f"Missing batch feature columns: {missing}")

        feature_matrix = df[BATCH_FEATURE_NAMES].dropna()
        if len(feature_matrix) < 10:
            raise ValueError(
                f"After dropping NaN, only {len(feature_matrix)} rows remain"
            )

        # Store healthy stats for explainability
        self._healthy_means = {
            col: float(feature_matrix[col].mean()) for col in BATCH_FEATURE_NAMES
        }
        self._healthy_stds = {
            col: float(feature_matrix[col].std()) for col in BATCH_FEATURE_NAMES
        }

        # Fit scaler
        self._scaler = StandardScaler()
        scaled = self._scaler.fit_transform(feature_matrix)

        # Fit Isolation Forest
        self._model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self._model.fit(scaled)

        # Quantile calibration (99th percentile of healthy decision scores)
        decisions = self._model.decision_function(scaled)
        self._threshold_score = float(np.percentile(-decisions, 99))

        self._is_trained = True
        self._training_timestamp = datetime.now(timezone.utc)
        self._training_sample_count = len(feature_matrix)

        logger.info(
            f"[BatchDetector] {self.asset_id}: trained on "
            f"{self._training_sample_count} windows, threshold={self._threshold_score:.4f}"
        )

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_batch(self, features: Dict[str, float]) -> float:
        """
        Score a single batch-feature dict.

        Args:
            features: Dict with 16 keys from BATCH_FEATURE_NAMES.

        Returns:
            Calibrated anomaly score in [0.0, 1.0].
        """
        if not self._is_trained:
            raise RuntimeError("Model not trained.")

        # Validate
        for col in BATCH_FEATURE_NAMES:
            if col not in features:
                raise ValueError(f"Missing feature: {col}")
            if features[col] is None or np.isnan(features[col]):
                raise ValueError(f"Feature {col} is NaN")

        # Build array in canonical order
        arr = np.array(
            [[features[name] for name in BATCH_FEATURE_NAMES]],
            dtype=np.float64,
        )

        # Scale
        scaled = self._scaler.transform(arr)

        # Decision function → calibrated score
        decision = self._model.decision_function(scaled)[0]
        return self._calibrated_score(decision)

    def score_raw_batch(self, raw_points: List[Dict[str, Any]]) -> float:
        """
        Convenience: extract features from raw 100Hz batch and score.

        Args:
            raw_points: List of 50-200 raw sensor dicts.

        Returns:
            Calibrated anomaly score, or 0.0 if extraction fails.
        """
        feats = extract_batch_features(raw_points)
        if feats is None:
            return 0.0
        return self.score_batch(feats)

    # ------------------------------------------------------------------
    # Explainability
    # ------------------------------------------------------------------

    def explain_anomaly(self, features: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Return the top contributing features to an anomaly, with plain-English
        descriptions. Sorted by z-score deviation from healthy means.

        Returns list of dicts: [{feature, value, healthy_mean, healthy_std, zscore, narrative}]
        """
        if self._healthy_means is None or self._healthy_stds is None:
            return []

        contributions = []
        for name in BATCH_FEATURE_NAMES:
            val = features.get(name, 0.0)
            h_mean = self._healthy_means.get(name, 0.0)
            h_std = self._healthy_stds.get(name, 1e-9)
            if h_std < 1e-9:
                h_std = 1e-9  # prevent div-by-zero

            zscore = (val - h_mean) / h_std
            if abs(zscore) < 1.5:
                continue  # Not significant

            contributions.append({
                "feature": name,
                "value": round(val, 6),
                "healthy_mean": round(h_mean, 6),
                "healthy_std": round(h_std, 6),
                "zscore": round(zscore, 2),
                "narrative": self._narrate(name, val, h_mean, zscore),
            })

        contributions.sort(key=lambda c: abs(c["zscore"]), reverse=True)
        return contributions[:5]  # top 5

    @staticmethod
    def _narrate(feature_name: str, value: float, healthy_mean: float, zscore: float) -> str:
        """Generate a plain-English explanation for a single feature deviation."""
        # Parse signal and stat from feature name
        parts = feature_name.rsplit("_", 1)
        if len(parts) == 2 and parts[1] in ("mean", "std", "rms"):
            signal_raw, stat = parts
        else:
            # peak_to_peak has underscores — special case
            if feature_name.endswith("_peak_to_peak"):
                signal_raw = feature_name[:-len("_peak_to_peak")]
                stat = "peak_to_peak"
            else:
                signal_raw = feature_name
                stat = "unknown"

        # Human-readable signal names
        signal_labels = {
            "voltage_v": "Voltage",
            "current_a": "Current",
            "power_factor": "Power Factor",
            "vibration_g": "Vibration",
        }
        signal_label = signal_labels.get(signal_raw, signal_raw)

        direction = "above" if zscore > 0 else "below"
        abs_z = abs(zscore)

        if stat == "std":
            return (
                f"High {signal_label.lower()} variance (noise): "
                f"σ={value:.4f} vs healthy σ={healthy_mean:.4f} ({abs_z:.1f}σ {direction} normal)"
            )
        elif stat == "peak_to_peak":
            return (
                f"{signal_label} transient spike: "
                f"peak-to-peak={value:.3f} vs healthy={healthy_mean:.3f} ({abs_z:.1f}σ {direction} normal)"
            )
        elif stat == "rms":
            return (
                f"{signal_label} energy anomaly: "
                f"RMS={value:.4f} vs healthy={healthy_mean:.4f} ({abs_z:.1f}σ {direction} normal)"
            )
        elif stat == "mean":
            return (
                f"{signal_label} mean shift: "
                f"{value:.2f} vs healthy={healthy_mean:.2f} ({abs_z:.1f}σ {direction} normal)"
            )
        else:
            return f"{feature_name}={value:.4f} deviates {abs_z:.1f}σ {direction} normal"

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def _calibrated_score(self, decision_value: float) -> float:
        """Convert IsolationForest decision_function to [0, 1] anomaly score."""
        raw = -decision_value
        factor = self._threshold_score * 1.5
        if factor > 0:
            calibrated = raw / factor
        else:
            calibrated = raw + 0.5
        return float(np.clip(calibrated, 0.0, 1.0))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: str = "backend/models") -> Path:
        """Save model + scaler + healthy stats to disk."""
        if not self._is_trained:
            raise RuntimeError("Cannot save untrained model")

        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)

        filepath = dir_path / f"batch_detector_{self.asset_id}.joblib"
        data = {
            "asset_id": self.asset_id,
            "model": self._model,
            "scaler": self._scaler,
            "contamination": self.contamination,
            "n_estimators": self.n_estimators,
            "random_state": self.random_state,
            "training_timestamp": self._training_timestamp,
            "training_sample_count": self._training_sample_count,
            "threshold_score": self._threshold_score,
            "healthy_means": self._healthy_means,
            "healthy_stds": self._healthy_stds,
            "version": 3,  # v3 = batch features
        }
        joblib.dump(data, filepath)
        logger.info(f"[BatchDetector] Saved to {filepath}")
        return filepath

    @classmethod
    def load(cls, filepath: str) -> "BatchAnomalyDetector":
        """Load a saved batch detector."""
        data = joblib.load(filepath)
        det = cls(
            asset_id=data["asset_id"],
            contamination=data["contamination"],
            n_estimators=data["n_estimators"],
            random_state=data["random_state"],
        )
        det._model = data["model"]
        det._scaler = data["scaler"]
        det._is_trained = True
        det._training_timestamp = data["training_timestamp"]
        det._training_sample_count = data["training_sample_count"]
        det._threshold_score = data.get("threshold_score", 0.5)
        det._healthy_means = data.get("healthy_means")
        det._healthy_stds = data.get("healthy_stds")
        return det
