"""
Anomaly Detector Tests

Tests verify:
- Training on healthy data
- Score inversion (0=normal, 1=anomalous)
- Features-only input (no raw signals)
- Model persistence roundtrip
- Faulty data scores higher than healthy data
- Determinism (same input = same output)
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
import pytest

from backend.ml.detector import AnomalyDetector, FEATURE_COLUMNS


def create_healthy_feature_data(n_points: int = 100) -> pd.DataFrame:
    """Create sample healthy feature data."""
    np.random.seed(42)
    
    timestamps = [
        datetime.now(timezone.utc) - timedelta(minutes=i)
        for i in range(n_points, 0, -1)
    ]
    
    data = {
        'timestamp': timestamps,
        'voltage_rolling_mean_1h': np.random.normal(230.0, 2.0, n_points),
        'current_spike_count': np.random.poisson(0.5, n_points),
        'power_factor_efficiency_score': np.clip(np.random.normal(0.85, 0.03, n_points), 0, 1),
        'vibration_intensity_rms': np.abs(np.random.normal(0.15, 0.02, n_points)),
    }
    
    return pd.DataFrame(data).set_index('timestamp')


def create_faulty_feature_data(n_points: int = 20) -> pd.DataFrame:
    """Create sample faulty feature data (anomalous)."""
    np.random.seed(123)
    
    timestamps = [
        datetime.now(timezone.utc) - timedelta(minutes=i)
        for i in range(n_points, 0, -1)
    ]
    
    # Anomalous values - significantly different from healthy
    data = {
        'timestamp': timestamps,
        'voltage_rolling_mean_1h': np.random.normal(250.0, 10.0, n_points),  # Higher, more variance
        'current_spike_count': np.random.poisson(5.0, n_points),  # Many more spikes
        'power_factor_efficiency_score': np.clip(np.random.normal(0.6, 0.1, n_points), 0, 1),  # Lower PF
        'vibration_intensity_rms': np.abs(np.random.normal(0.5, 0.1, n_points)),  # Much higher vibration
    }
    
    return pd.DataFrame(data).set_index('timestamp')


class TestAnomalyDetector:
    """Test anomaly detector training and scoring."""

    def test_train_on_healthy_data(self):
        """Detector can be trained on healthy data."""
        data = create_healthy_feature_data(100)
        detector = AnomalyDetector(asset_id="test-motor")
        
        detector.train(data)
        
        assert detector.is_trained
        assert detector.asset_id == "test-motor"

    def test_training_is_deterministic(self):
        """Same data produces same model (random_state fixed)."""
        data = create_healthy_feature_data(100)
        
        detector1 = AnomalyDetector(asset_id="motor-1", random_state=42)
        detector1.train(data)
        
        detector2 = AnomalyDetector(asset_id="motor-2", random_state=42)
        detector2.train(data)
        
        # Score same data point
        test_point = {
            'voltage_rolling_mean_1h': 230.0,
            'current_spike_count': 1,
            'power_factor_efficiency_score': 0.85,
            'vibration_intensity_rms': 0.15
        }
        
        score1 = detector1.score_single(test_point)
        score2 = detector2.score_single(test_point)
        
        assert score1 == score2

    def test_score_range_is_0_to_1(self):
        """Anomaly scores are bounded [0, 1]."""
        data = create_healthy_feature_data(100)
        detector = AnomalyDetector(asset_id="test-motor")
        detector.train(data)
        
        # Score healthy data
        scores = detector.score(data)
        
        for score_obj in scores:
            assert 0.0 <= score_obj.score <= 1.0

    def test_healthy_data_scores_low(self):
        """Healthy data should score low (close to 0)."""
        data = create_healthy_feature_data(100)
        detector = AnomalyDetector(asset_id="test-motor")
        detector.train(data)
        
        scores = detector.score(data)
        median_score = np.median([s.score for s in scores])
        
        # Healthy data trained on itself should score very low
        assert median_score < 0.5

    def test_faulty_data_scores_higher(self):
        """
        Faulty data scores higher than healthy.
        
        EXIT CRITERIA: Median(Anomaly_Score_Faulty) > Median(Anomaly_Score_Healthy)
        """
        healthy_data = create_healthy_feature_data(100)
        faulty_data = create_faulty_feature_data(20)
        
        detector = AnomalyDetector(asset_id="test-motor")
        detector.train(healthy_data)
        
        healthy_scores = detector.score(healthy_data)
        faulty_scores = detector.score(faulty_data)
        
        median_healthy = np.median([s.score for s in healthy_scores])
        median_faulty = np.median([s.score for s in faulty_scores])
        
        # Critical validation
        assert median_faulty > median_healthy, (
            f"Faulty data should score higher than healthy. "
            f"Median faulty: {median_faulty:.4f}, Median healthy: {median_healthy:.4f}"
        )

    def test_fails_on_empty_data(self):
        """Training on empty data raises error."""
        data = pd.DataFrame()
        detector = AnomalyDetector(asset_id="test-motor")
        
        with pytest.raises(ValueError):
            detector.train(data)

    def test_fails_on_insufficient_data(self):
        """Training on too few samples raises error."""
        data = create_healthy_feature_data(5)  # Only 5 samples
        detector = AnomalyDetector(asset_id="test-motor")
        
        with pytest.raises(ValueError):
            detector.train(data)

    def test_score_before_train_raises_error(self):
        """Scoring before training raises error."""
        detector = AnomalyDetector(asset_id="test-motor")
        
        with pytest.raises(RuntimeError):
            detector.score_single({
                'voltage_rolling_mean_1h': 230.0,
                'current_spike_count': 1,
                'power_factor_efficiency_score': 0.85,
                'vibration_intensity_rms': 0.15
            })


class TestModelPersistence:
    """Test model save/load."""

    def test_save_and_load_roundtrip(self):
        """Model can be saved and loaded."""
        data = create_healthy_feature_data(100)
        detector = AnomalyDetector(asset_id="test-motor")
        detector.train(data)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = detector.save_model(directory=tmpdir)
            
            assert filepath.exists()
            
            loaded = AnomalyDetector.load_model(str(filepath))
            
            assert loaded.asset_id == "test-motor"
            assert loaded.is_trained

    def test_loaded_model_scores_same(self):
        """Loaded model produces identical scores."""
        data = create_healthy_feature_data(100)
        detector = AnomalyDetector(asset_id="test-motor")
        detector.train(data)
        
        test_point = {
            'voltage_rolling_mean_1h': 230.0,
            'current_spike_count': 1,
            'power_factor_efficiency_score': 0.85,
            'vibration_intensity_rms': 0.15
        }
        
        original_score = detector.score_single(test_point)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = detector.save_model(directory=tmpdir)
            loaded = AnomalyDetector.load_model(str(filepath))
            
            loaded_score = loaded.score_single(test_point)
            
            assert abs(original_score - loaded_score) < 0.0001


class TestFeatureInput:
    """Test that only features are used (no raw signals)."""

    def test_uses_only_feature_columns(self):
        """Verify FEATURE_COLUMNS excludes raw signals."""
        # Raw signals that should NOT be in feature columns
        raw_signals = ['voltage_v', 'current_a', 'power_factor', 'vibration_g']
        
        for raw in raw_signals:
            assert raw not in FEATURE_COLUMNS, f"Raw signal '{raw}' should not be in FEATURE_COLUMNS"

    def test_rejects_data_with_only_raw_signals(self):
        """Data with only raw signals should raise error."""
        np.random.seed(42)
        
        data = pd.DataFrame({
            'voltage_v': np.random.normal(230.0, 5.0, 100),
            'current_a': np.random.normal(15.0, 1.5, 100),
        })
        
        detector = AnomalyDetector(asset_id="test-motor")
        
        with pytest.raises(ValueError) as exc_info:
            detector.train(data)
        
        assert "feature" in str(exc_info.value).lower()


class TestAssetSpecific:
    """Test that models are asset-specific."""

    def test_one_model_per_asset(self):
        """Each asset has its own model."""
        data = create_healthy_feature_data(100)
        
        detector1 = AnomalyDetector(asset_id="motor-1")
        detector2 = AnomalyDetector(asset_id="motor-2")
        
        detector1.train(data)
        detector2.train(data)
        
        assert detector1.asset_id == "motor-1"
        assert detector2.asset_id == "motor-2"

    def test_no_auto_retrain(self):
        """Model does not auto-retrain (manual only)."""
        data = create_healthy_feature_data(100)
        detector = AnomalyDetector(asset_id="test-motor")
        detector.train(data)
        
        original_timestamp = detector._training_timestamp
        
        # Scoring new data should NOT retrain
        new_data = create_healthy_feature_data(50)
        detector.score(new_data)
        
        # Training timestamp should be unchanged
        assert detector._training_timestamp == original_timestamp
