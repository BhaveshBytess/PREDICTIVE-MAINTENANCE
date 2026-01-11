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


# Feature columns used for anomaly detection
# STRICTLY EXCLUDE raw instantaneous signals (voltage_v, current_a)
FEATURE_COLUMNS = [
    'voltage_rolling_mean_1h',
    'current_spike_count',
    'power_factor_efficiency_score',
    'vibration_intensity_rms',
]

# Model hyperparameters
DEFAULT_CONTAMINATION = 0.001  # Very low since training data is pure healthy
DEFAULT_RANDOM_STATE = 42  # Deterministic training
DEFAULT_N_ESTIMATORS = 100


class AnomalyScore(BaseModel):
    """Result of anomaly scoring."""
    asset_id: str
    timestamp: datetime
    score: float = Field(..., ge=0.0, le=1.0, description="0.0=Normal, 1.0=Anomalous")
    feature_values: Dict[str, float] = Field(default_factory=dict)


class AnomalyDetector:
    """
    Isolation Forest-based anomaly detector.
    
    Score semantics:
    - 0.0 = Perfectly Normal (matches baseline)
    - 1.0 = Highly Anomalous (deviation from baseline)
    
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
            contamination: Expected proportion of outliers (low for pure data)
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
    
    @property
    def is_trained(self) -> bool:
        """Check if model has been trained."""
        return self._is_trained
    
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
        
        # Extract features (ignore raw signals)
        features = self._extract_features(data)
        
        if features.shape[0] < 10:
            raise ValueError(f"Insufficient data for training: {features.shape[0]} samples (need >= 10)")
        
        # Drop rows with NaN (incomplete feature windows)
        features_clean = features.dropna()
        
        if features_clean.shape[0] < 10:
            raise ValueError(f"Insufficient valid data after dropping NaN: {features_clean.shape[0]} samples")
        
        # Scale features
        self._scaler = StandardScaler()
        features_scaled = self._scaler.fit_transform(features_clean)
        
        # Train Isolation Forest
        self._model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1  # Use all cores
        )
        self._model.fit(features_scaled)
        
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
        
        # Extract features
        features = self._extract_features(data)
        
        results = []
        
        for idx, row in features.iterrows():
            # Handle NaN
            if row.isna().any():
                # Cannot score if features are incomplete
                continue
            
            # Scale features
            row_scaled = self._scaler.transform(row.values.reshape(1, -1))
            
            # Get decision function value
            # Scikit-learn: higher = more normal
            decision_value = self._model.decision_function(row_scaled)[0]
            
            # Invert to get anomaly score
            # decision_function typically ranges from -0.5 to 0.5
            # We normalize and invert: score = 1.0 - normalized
            anomaly_score = self._invert_decision_score(decision_value)
            
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
                feature_values=row.to_dict()
            ))
        
        return results
    
    def score_single(self, features: Dict[str, float]) -> float:
        """
        Score a single feature set.
        
        Args:
            features: Dict of feature name -> value
            
        Returns:
            Anomaly score [0, 1]
        """
        if not self._is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        # Build feature vector
        feature_vector = []
        for col in FEATURE_COLUMNS:
            if col not in features:
                raise ValueError(f"Missing feature: {col}")
            value = features[col]
            if value is None or np.isnan(value):
                raise ValueError(f"Feature {col} is NaN")
            feature_vector.append(value)
        
        # Scale and score
        scaled = self._scaler.transform([feature_vector])
        decision_value = self._model.decision_function(scaled)[0]
        
        return self._invert_decision_score(decision_value)
    
    def _extract_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Extract feature columns from data."""
        available = [col for col in FEATURE_COLUMNS if col in data.columns]
        
        if not available:
            raise ValueError(
                f"No feature columns found. Expected: {FEATURE_COLUMNS}. "
                f"Got: {list(data.columns)}"
            )
        
        # Use available features
        return data[available].copy()
    
    def _invert_decision_score(self, decision_value: float) -> float:
        """
        Invert scikit-learn decision function to anomaly score.
        
        Scikit-learn decision_function:
        - Higher values = more normal
        - Typically ranges from about -0.5 to 0.5
        
        Our scoring:
        - 0.0 = Normal
        - 1.0 = Anomalous
        
        Transformation: score = 1.0 - sigmoid(decision_value * k)
        Where k scales the decision value to reasonable sigmoid input
        """
        # Sigmoid transformation for smooth [0, 1] output
        # Scale factor of 4 maps decision values well to sigmoid
        sigmoid_input = decision_value * 4
        sigmoid = 1.0 / (1.0 + np.exp(-sigmoid_input))
        
        # Invert: high decision value (normal) -> low anomaly score
        anomaly_score = 1.0 - sigmoid
        
        # Clamp to [0, 1]
        return float(np.clip(anomaly_score, 0.0, 1.0))
    
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
        
        return detector
