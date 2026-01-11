"""
Feature Engineering Tests — Math Correctness & Constraints

Tests verify:
- Rolling mean calculation
- Spike detection with local σ/μ
- Power factor score [0,1] bounds
- Vibration RMS formula
- Past-only windowing (no future leakage)
- NaN for incomplete windows (cold-start)
- Idempotency (same input = same output)
"""

import math
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.features.calculator import (
    calculate_voltage_rolling_mean,
    calculate_current_spike_count,
    calculate_power_factor_efficiency_score,
    calculate_vibration_rms,
    compute_all_features,
)
from backend.features.schemas import DerivedFeatures, FeatureRecord


def create_test_dataframe(
    n_points: int = 60,
    start_time: datetime = None,
    voltage_base: float = 230.0,
    current_base: float = 15.0,
    vibration_base: float = 0.15
) -> pd.DataFrame:
    """Create a test DataFrame with simulated sensor data."""
    if start_time is None:
        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
    
    timestamps = [start_time + timedelta(minutes=i) for i in range(n_points)]
    
    np.random.seed(42)  # Deterministic
    data = {
        'voltage_v': np.random.normal(voltage_base, 5, n_points),
        'current_a': np.random.normal(current_base, 1, n_points),
        'power_factor': np.clip(np.random.normal(0.85, 0.05, n_points), 0, 1),
        'vibration_g': np.abs(np.random.normal(vibration_base, 0.02, n_points)),
    }
    
    df = pd.DataFrame(data, index=pd.DatetimeIndex(timestamps, tz=timezone.utc))
    return df


class TestVoltageRollingMean:
    """Test voltage rolling mean calculation."""

    def test_rolling_mean_calculation(self):
        """Verify mean formula is correct."""
        # Create simple data with known values
        timestamps = [datetime.now(timezone.utc) + timedelta(minutes=i) for i in range(5)]
        df = pd.DataFrame(
            {'voltage_v': [100.0, 200.0, 300.0, 400.0, 500.0]},
            index=pd.DatetimeIndex(timestamps, tz=timezone.utc)
        )
        
        # At index 4, mean of [100, 200, 300, 400, 500] = 300
        result = calculate_voltage_rolling_mean(df, evaluation_idx=4)
        
        assert result is not None
        assert abs(result - 300.0) < 0.1

    def test_rolling_mean_past_only(self):
        """Verify no future data is included."""
        timestamps = [datetime.now(timezone.utc) + timedelta(minutes=i) for i in range(10)]
        df = pd.DataFrame(
            {'voltage_v': [100.0] * 5 + [1000.0] * 5},  # Big jump at index 5
            index=pd.DatetimeIndex(timestamps, tz=timezone.utc)
        )
        
        # At index 4, should only see values before/at 4, not the 1000s
        result = calculate_voltage_rolling_mean(df, evaluation_idx=4)
        
        assert result is not None
        assert result < 200  # Should be ~100, not influenced by 1000s

    def test_empty_dataframe_returns_none(self):
        """Empty DataFrame should return None (NaN)."""
        df = pd.DataFrame()
        result = calculate_voltage_rolling_mean(df, evaluation_idx=0)
        assert result is None

    def test_single_point_returns_none(self):
        """Single point is insufficient for meaningful mean."""
        timestamps = [datetime.now(timezone.utc)]
        df = pd.DataFrame(
            {'voltage_v': [230.0]},
            index=pd.DatetimeIndex(timestamps, tz=timezone.utc)
        )
        result = calculate_voltage_rolling_mean(df, evaluation_idx=0)
        # Need at least 2 points
        assert result is None


class TestCurrentSpikeCount:
    """Test current spike detection."""

    def test_spike_detection_local_sigma(self):
        """Verify spikes detected using LOCAL window σ."""
        timestamps = [datetime.now(timezone.utc) + timedelta(minutes=i) for i in range(10)]
        # 8 normal values, 2 spikes
        data = [15.0, 15.1, 14.9, 15.2, 14.8, 15.0, 15.1, 14.9, 25.0, 30.0]
        df = pd.DataFrame(
            {'current_a': data},
            index=pd.DatetimeIndex(timestamps, tz=timezone.utc)
        )
        
        result = calculate_current_spike_count(df, evaluation_idx=9)
        
        # Should detect the 25.0 and 30.0 as spikes (> 2σ above mean)
        assert result is not None
        assert result >= 1  # At least one spike detected

    def test_no_spikes_in_uniform_data(self):
        """Uniform data should have no spikes."""
        timestamps = [datetime.now(timezone.utc) + timedelta(minutes=i) for i in range(10)]
        df = pd.DataFrame(
            {'current_a': [15.0] * 10},
            index=pd.DatetimeIndex(timestamps, tz=timezone.utc)
        )
        
        result = calculate_current_spike_count(df, evaluation_idx=9)
        
        assert result == 0  # No variation = no spikes

    def test_insufficient_data_returns_none(self):
        """Less than 3 points should return None."""
        timestamps = [datetime.now(timezone.utc) + timedelta(minutes=i) for i in range(2)]
        df = pd.DataFrame(
            {'current_a': [15.0, 16.0]},
            index=pd.DatetimeIndex(timestamps, tz=timezone.utc)
        )
        
        result = calculate_current_spike_count(df, evaluation_idx=1)
        
        # Need at least 3 points for meaningful σ
        assert result is None


class TestPowerFactorScore:
    """Test power factor efficiency score."""

    def test_score_bounded_0_to_1(self):
        """Score must be strictly bounded [0.0, 1.0]."""
        for pf in [0.0, 0.5, 0.85, 1.0]:
            score = calculate_power_factor_efficiency_score(pf)
            assert score is not None
            assert 0.0 <= score <= 1.0

    def test_score_monotonic(self):
        """Higher PF should give higher score."""
        scores = []
        for pf in [0.5, 0.7, 0.85, 0.95, 1.0]:
            score = calculate_power_factor_efficiency_score(pf)
            scores.append(score)
        
        # Verify monotonically increasing
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i-1], f"Score not monotonic: {scores}"

    def test_invalid_pf_clamped(self):
        """Out-of-range PF should be clamped, not cause error."""
        # Above 1.0
        score = calculate_power_factor_efficiency_score(1.5)
        assert score == 1.0
        
        # Below 0.0
        score = calculate_power_factor_efficiency_score(-0.5)
        assert score == 0.0

    def test_nan_returns_none(self):
        """NaN input should return None."""
        result = calculate_power_factor_efficiency_score(float('nan'))
        assert result is None

    def test_none_returns_none(self):
        """None input should return None."""
        result = calculate_power_factor_efficiency_score(None)
        assert result is None


class TestVibrationRMS:
    """Test vibration RMS calculation."""

    def test_rms_formula_correct(self):
        """Verify RMS = √(Σ(v²)/n)."""
        timestamps = [datetime.now(timezone.utc) + timedelta(minutes=i) for i in range(4)]
        # Values: 1, 2, 3, 4
        # Squares: 1, 4, 9, 16
        # Mean of squares: 30/4 = 7.5
        # RMS = √7.5 ≈ 2.7386
        df = pd.DataFrame(
            {'vibration_g': [1.0, 2.0, 3.0, 4.0]},
            index=pd.DatetimeIndex(timestamps, tz=timezone.utc)
        )
        
        result = calculate_vibration_rms(df, evaluation_idx=3)
        
        expected_rms = math.sqrt(7.5)
        assert result is not None
        assert abs(result - expected_rms) < 0.001

    def test_single_point_returns_none(self):
        """Single point is insufficient."""
        timestamps = [datetime.now(timezone.utc)]
        df = pd.DataFrame(
            {'vibration_g': [0.5]},
            index=pd.DatetimeIndex(timestamps, tz=timezone.utc)
        )
        
        result = calculate_vibration_rms(df, evaluation_idx=0)
        assert result is None


class TestComputeAllFeatures:
    """Test the combined feature computation."""

    def test_all_features_computed(self):
        """Verify all four features are returned."""
        df = create_test_dataframe(n_points=60)
        
        result = compute_all_features(df, evaluation_idx=59, current_power_factor=0.85)
        
        assert 'voltage_rolling_mean_1h' in result
        assert 'current_spike_count' in result
        assert 'power_factor_efficiency_score' in result
        assert 'vibration_intensity_rms' in result

    def test_idempotency(self):
        """Same inputs must produce same outputs."""
        df = create_test_dataframe(n_points=60)
        
        result1 = compute_all_features(df, evaluation_idx=30, current_power_factor=0.85)
        result2 = compute_all_features(df, evaluation_idx=30, current_power_factor=0.85)
        
        assert result1 == result2


class TestFeatureSchemas:
    """Test Pydantic schema validation."""

    def test_derived_features_allows_none(self):
        """Features can be None (for NaN/cold-start)."""
        features = DerivedFeatures(
            voltage_rolling_mean_1h=None,
            current_spike_count=None,
            power_factor_efficiency_score=None,
            vibration_intensity_rms=None
        )
        
        assert features.voltage_rolling_mean_1h is None
        assert features.current_spike_count is None

    def test_pf_score_validation(self):
        """PF score must be [0.0, 1.0] or None."""
        # Valid
        DerivedFeatures(power_factor_efficiency_score=0.5)
        DerivedFeatures(power_factor_efficiency_score=0.0)
        DerivedFeatures(power_factor_efficiency_score=1.0)
        
        # Invalid - out of range
        with pytest.raises(ValueError):
            DerivedFeatures(power_factor_efficiency_score=1.5)

    def test_feature_record_timestamp_required_utc(self):
        """FeatureRecord timestamp must be timezone-aware."""
        with pytest.raises(ValueError):
            FeatureRecord(
                feature_id="test",
                asset_id="motor-1",
                timestamp=datetime(2026, 1, 1, 12, 0),  # Naive datetime
                features=DerivedFeatures()
            )

    def test_feature_record_valid(self):
        """Valid FeatureRecord should pass."""
        record = FeatureRecord(
            feature_id="test-123",
            asset_id="motor-1",
            timestamp=datetime.now(timezone.utc),
            features=DerivedFeatures(
                voltage_rolling_mean_1h=230.5,
                current_spike_count=2,
                power_factor_efficiency_score=0.85,
                vibration_intensity_rms=0.15
            )
        )
        
        assert record.asset_id == "motor-1"
        assert record.features.voltage_rolling_mean_1h == 230.5
