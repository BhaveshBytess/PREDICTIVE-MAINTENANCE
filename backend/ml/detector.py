"""
Anomaly Detector — Isolation Forest for Anomaly Scoring

Assigns anomaly scores WITHOUT making decisions.
ML outputs score only — decision logic belongs in Phase 7.

Constraints:
- Features ONLY (no raw signals like voltage_v, current_a)
- Score inverted: 0.0=Normal, 1.0=Anomalous
- Train only on healthy baseline data
- One model per asset (no global models)
- No auto-retraining
- Deterministic (random_state=42)

V2 Enhancements:
- Added derived features (voltage_stability, power_vibration_ratio)
- Quantile-based score calibration
- Improved separation between healthy and faulty data
"""

import joblib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from pydantic import BaseModel, Field


# Original feature columns from Phase 4
BASE_FEATURE_COLUMNS = [
    'voltage_rolling_mean_1h',
    'current_spike_count',
    'power_factor_efficiency_score',
    'vibration_intensity_rms',
]

# Derived feature columns (Phase 1 Enhancement)
DERIVED_FEATURE_COLUMNS = [
    'voltage_stability',        # abs(voltage - 230.0)
    'power_vibration_ratio',    # vibration_rms / (power_factor + 0.01)
]

# All feature columns (input to model)
FEATURE_COLUMNS = BASE_FEATURE_COLUMNS + DERIVED_FEATURE_COLUMNS

# Indian Grid nominal voltage (for stability calculation)
NOMINAL_VOLTAGE = 230.0

# Model hyperparameters
DEFAULT_CONTAMINATION = 0.05  # Increased from 0.001 for better calibration
DEFAULT_RANDOM_STATE = 42     # Deterministic training
DEFAULT_N_ESTIMATORS = 100


class AnomalyScore(BaseModel):
    """Result of anomaly scoring."""
    asset_id: str
    timestamp: datetime
    score: float = Field(..., ge=0.0, le=1.0, description="0.0=Normal, 1.0=Anomalous")
    feature_values: Dict[str, float] = Field(default_factory=dict)


class AnomalyDetector:
    """
    Isolation Forest-based anomaly detector with calibrated scoring.
    
    Score semantics:
    - 0.0 = Perfectly Normal (matches baseline)
    - 1.0 = Highly Anomalous (deviation from baseline)
    
    V2 Features:
    - Derived features for better separation
    - Quantile-calibrated scores
    - StandardScaler for all features
    
    One model per asset. No auto-retraining.
    """
    
    def __init__(
        self,
        asset_id: str,
        contamination: float = DEFAULT_CONTAMINATION,
        n_estimators: int = DEFAULT_N_ESTIMATORS,
        random_state: int = DEFAULT_RANDOM_STATE
    ):
        """
        Initialize detector for a specific asset.
        
        Args:
            asset_id: Asset this detector belongs to
            contamination: Expected proportion of outliers
            n_estimators: Number of trees in the forest
            random_state: Random seed for reproducibility
        """
        self.asset_id = asset_id
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        
        self._model: Optional[IsolationForest] = None
        self._scaler: Optional[StandardScaler] = None
        self._is_trained = False
        self._training_timestamp: Optional[datetime] = None
        self._training_sample_count: int = 0
        
        # Phase 2: Quantile calibration threshold
        self._threshold_score: float = 0.5  # Default, updated during training
    
    @property
    def is_trained(self) -> bool:
        """Check if model has been trained."""
        return self._is_trained
    
    def _compute_derived_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute derived features from base features.
        
        Phase 1 Enhancement:
        - voltage_stability: Distance from nominal Indian Grid voltage
        - power_vibration_ratio: Interaction term for fault detection
        
        Args:
            data: DataFrame with base feature columns
            
        Returns:
            DataFrame with base + derived features
        """
        result = data.copy()
        
        # Compute voltage_stability: abs(voltage_rolling_mean - 230.0)
        if 'voltage_rolling_mean_1h' in result.columns:
            result['voltage_stability'] = abs(result['voltage_rolling_mean_1h'] - NOMINAL_VOLTAGE)
        else:
            result['voltage_stability'] = 0.0
        
        # Compute power_vibration_ratio: vibration / (power_factor + epsilon)
        if 'vibration_intensity_rms' in result.columns and 'power_factor_efficiency_score' in result.columns:
            result['power_vibration_ratio'] = (
                result['vibration_intensity_rms'] / 
                (result['power_factor_efficiency_score'] + 0.01)
            )
        else:
            result['power_vibration_ratio'] = 0.0
        
        return result
    
    def _compute_derived_features_single(self, features: Dict[str, float]) -> Dict[str, float]:
        """
        Compute derived features for a single feature set.
        
        Args:
            features: Dict of base feature values
            
        Returns:
            Dict with base + derived features
        """
        result = features.copy()
        
        # Compute voltage_stability
        voltage_mean = features.get('voltage_rolling_mean_1h', NOMINAL_VOLTAGE)
        result['voltage_stability'] = abs(voltage_mean - NOMINAL_VOLTAGE)
        
        # Compute power_vibration_ratio
        vibration = features.get('vibration_intensity_rms', 0.0)
        power_factor = features.get('power_factor_efficiency_score', 0.92)
        result['power_vibration_ratio'] = vibration / (power_factor + 0.01)
        
        return result
    
    def train(self, data: pd.DataFrame) -> None:
        """
        Train the model on HEALTHY data only.
        
        Args:
            data: DataFrame with feature columns (already filtered to healthy)
            
        Raises:
            ValueError: If data is empty or missing required features
        """
        # Validate data
        if data.empty:
            raise ValueError("Cannot train on empty data")
        
        # Extract base features
        base_features = self._extract_base_features(data)
        
        if base_features.shape[0] < 10:
            raise ValueError(f"Insufficient data for training: {base_features.shape[0]} samples (need >= 10)")
        
        # Add derived features
        enhanced_features = self._compute_derived_features(base_features)
        
        # Drop rows with NaN (incomplete feature windows)
        features_clean = enhanced_features.dropna()
        
        if features_clean.shape[0] < 10:
            raise ValueError(f"Insufficient valid data after dropping NaN: {features_clean.shape[0]} samples")
        
        # Get all feature columns (base + derived)
        all_feature_cols = [col for col in FEATURE_COLUMNS if col in features_clean.columns]
        feature_matrix = features_clean[all_feature_cols]
        
        # Scale ALL features (Phase 1: StandardScaler)
        self._scaler = StandardScaler()
        features_scaled = self._scaler.fit_transform(feature_matrix)
        
        # Train Isolation Forest
        self._model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1  # Use all cores
        )
        self._model.fit(features_scaled)
        
        # Phase 2: Compute quantile threshold for calibration
        # Get decision scores for training data
        training_decisions = self._model.decision_function(features_scaled)
        
        # Decision function: higher = more normal
        # We want the 99th percentile of healthy data as our threshold
        # Invert the sign because we'll invert later for anomaly scores
        self._threshold_score = float(np.percentile(-training_decisions, 99))
        
        self._is_trained = True
        self._training_timestamp = datetime.now(timezone.utc)
        self._training_sample_count = features_clean.shape[0]
    
    def score(self, data: pd.DataFrame) -> List[AnomalyScore]:
        """
        Score data for anomalies.
        
        Args:
            data: DataFrame with feature columns
            
        Returns:
            List of AnomalyScore objects
            
        Raises:
            RuntimeError: If model not trained
        """
        if not self._is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        # Extract and enhance features
        base_features = self._extract_base_features(data)
        enhanced_features = self._compute_derived_features(base_features)
        
        # Get all feature columns
        all_feature_cols = [col for col in FEATURE_COLUMNS if col in enhanced_features.columns]
        
        results = []
        
        for idx, row in enhanced_features.iterrows():
            # Handle NaN
            if row[all_feature_cols].isna().any():
                continue
            
            # Get feature vector as DataFrame with proper column names
            # This prevents "X does not have valid feature names" warning
            feature_df = pd.DataFrame([row[all_feature_cols].values], columns=all_feature_cols)
            
            # Scale features (passing DataFrame preserves feature names)
            row_scaled = self._scaler.transform(feature_df)
            
            # Get decision function value
            decision_value = self._model.decision_function(row_scaled)[0]
            
            # Compute calibrated anomaly score
            anomaly_score = self._calibrated_score(decision_value)
            
            # Get timestamp
            if isinstance(idx, datetime):
                timestamp = idx
            elif 'timestamp' in data.columns:
                timestamp = data.loc[idx, 'timestamp']
            else:
                timestamp = datetime.now(timezone.utc)
            
            results.append(AnomalyScore(
                asset_id=self.asset_id,
                timestamp=timestamp,
                score=anomaly_score,
                feature_values=row[all_feature_cols].to_dict()
            ))
        
        return results
    
    def score_single(self, features: Dict[str, float]) -> float:
        """
        Score a single feature set.
        
        Args:
            features: Dict of feature name -> value (base features only)
            
        Returns:
            Calibrated anomaly score [0, 1]
        """
        if not self._is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        # Validate base features are present
        for col in BASE_FEATURE_COLUMNS:
            if col not in features:
                raise ValueError(f"Missing base feature: {col}")
            value = features[col]
            if value is None or np.isnan(value):
                raise ValueError(f"Feature {col} is NaN")
        
        # Add derived features
        enhanced = self._compute_derived_features_single(features)
        
        # Build feature vector as DataFrame with proper column names
        # This prevents "X does not have valid feature names" warning
        feature_df = pd.DataFrame([enhanced], columns=FEATURE_COLUMNS)
        
        # Scale and score (passing DataFrame preserves feature names)
        scaled = self._scaler.transform(feature_df)
        decision_value = self._model.decision_function(scaled)[0]
        
        return self._calibrated_score(decision_value)
    
    def _extract_base_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Extract base feature columns from data (without derived)."""
        available = [col for col in BASE_FEATURE_COLUMNS if col in data.columns]
        
        if not available:
            raise ValueError(
                f"No base feature columns found. Expected: {BASE_FEATURE_COLUMNS}. "
                f"Got: {list(data.columns)}"
            )
        
        return data[available].copy()
    
    def _calibrated_score(self, decision_value: float) -> float:
        """
        Convert decision function to calibrated anomaly score.
        
        Phase 2 Enhancement: Quantile-based calibration.
        
        Scikit-learn decision_function:
        - Higher values = more normal
        - Typically ranges from about -0.5 to 0.5
        
        Our calibrated scoring:
        - 0.0 = Normal (within healthy distribution)
        - 1.0 = Highly Anomalous (far outside healthy distribution)
        
        Calibration formula:
        - raw_score = -decision_value (invert so higher = more anomalous)
        - calibrated = raw_score / (threshold * 1.5)
        - Healthy data (< threshold) maps to < 0.67
        - Anomalies (> threshold) map to > 0.67
        """
        # Invert decision value (higher decision = more normal, so negate)
        raw_score = -decision_value
        
        # Calibrate against training threshold
        # threshold_score is the 99th percentile of healthy (-decision) values
        calibration_factor = self._threshold_score * 1.5
        
        if calibration_factor > 0:
            calibrated = raw_score / calibration_factor
        else:
            # Fallback if threshold is 0 (shouldn't happen)
            calibrated = raw_score + 0.5
        
        # Clip to [0, 1]
        return float(np.clip(calibrated, 0.0, 1.0))
    
    def save_model(self, directory: str = "backend/models") -> Path:
        """
        Save trained model to disk.
        
        Args:
            directory: Target directory
            
        Returns:
            Path to saved file
        """
        if not self._is_trained:
            raise RuntimeError("Cannot save untrained model")
        
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        
        filename = f"detector_{self.asset_id}.joblib"
        filepath = dir_path / filename
        
        model_data = {
            'asset_id': self.asset_id,
            'model': self._model,
            'scaler': self._scaler,
            'contamination': self.contamination,
            'n_estimators': self.n_estimators,
            'random_state': self.random_state,
            'training_timestamp': self._training_timestamp,
            'training_sample_count': self._training_sample_count,
            'threshold_score': self._threshold_score,  # V2: Save calibration threshold
            'version': 2,  # Model version
        }
        
        joblib.dump(model_data, filepath)
        
        return filepath
    
    @classmethod
    def load_model(cls, filepath: str) -> 'AnomalyDetector':
        """
        Load trained model from disk.
        
        Args:
            filepath: Path to saved model
            
        Returns:
            Loaded AnomalyDetector instance
        """
        model_data = joblib.load(filepath)
        
        detector = cls(
            asset_id=model_data['asset_id'],
            contamination=model_data['contamination'],
            n_estimators=model_data['n_estimators'],
            random_state=model_data['random_state']
        )
        
        detector._model = model_data['model']
        detector._scaler = model_data['scaler']
        detector._is_trained = True
        detector._training_timestamp = model_data['training_timestamp']
        detector._training_sample_count = model_data['training_sample_count']
        
        # V2: Load calibration threshold (with backward compatibility)
        detector._threshold_score = model_data.get('threshold_score', 0.5)
        
        return detector
