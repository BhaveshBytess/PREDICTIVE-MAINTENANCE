"""
Baseline Construction Tests

Tests verify:
- Statistical profiling from healthy data
- Filtering by is_fault_injected == False
- Coverage checks (fail if < 80%)
- JSON serialization/deserialization
- 3-Sigma validation
- Healthy data passes validation
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
import pytest

from backend.ml.baseline import (
    BaselineProfile,
    BaselineBuilder,
    BaselineBuildError,
    SignalProfile,
    save_baseline,
    load_baseline,
)
from backend.ml.validation import (
    validate_baseline,
    check_data_against_baseline,
    get_expected_range,
)


def create_healthy_data(n_points: int = 100) -> pd.DataFrame:
    """Create sample healthy sensor data."""
    np.random.seed(42)
    
    timestamps = [
        datetime.now(timezone.utc) - timedelta(minutes=i)
        for i in range(n_points, 0, -1)
    ]
    
    data = {
        'timestamp': timestamps,
        'voltage_v': np.random.normal(230.0, 5.0, n_points),
        'current_a': np.random.normal(15.0, 1.5, n_points),
        'power_factor': np.clip(np.random.normal(0.85, 0.05, n_points), 0, 1),
        'vibration_g': np.abs(np.random.normal(0.15, 0.03, n_points)),
        'is_fault_injected': [False] * n_points,
    }
    
    return pd.DataFrame(data)


def create_mixed_data(n_healthy: int = 80, n_fault: int = 20) -> pd.DataFrame:
    """Create data with both healthy and fault periods."""
    np.random.seed(42)
    
    timestamps = [
        datetime.now(timezone.utc) - timedelta(minutes=i)
        for i in range(n_healthy + n_fault, 0, -1)
    ]
    
    # Healthy data
    healthy_voltage = np.random.normal(230.0, 5.0, n_healthy)
    # Fault data (higher voltage variance to simulate issues)
    fault_voltage = np.random.normal(250.0, 15.0, n_fault)
    
    data = {
        'timestamp': timestamps,
        'voltage_v': np.concatenate([healthy_voltage, fault_voltage]),
        'current_a': np.random.normal(15.0, 1.5, n_healthy + n_fault),
        'power_factor': np.clip(np.random.normal(0.85, 0.05, n_healthy + n_fault), 0, 1),
        'vibration_g': np.abs(np.random.normal(0.15, 0.03, n_healthy + n_fault)),
        'is_fault_injected': [False] * n_healthy + [True] * n_fault,
    }
    
    return pd.DataFrame(data)


class TestBaselineBuilder:
    """Test baseline construction."""

    def test_build_from_healthy_data(self):
        """Baseline can be built from healthy data."""
        data = create_healthy_data(100)
        builder = BaselineBuilder()
        
        profile = builder.build(data, asset_id="test-motor")
        
        assert profile.asset_id == "test-motor"
        assert "voltage_v" in profile.signal_profiles
        assert "current_a" in profile.signal_profiles
        assert profile.signal_profiles["voltage_v"].sample_count == 100

    def test_filters_fault_injected_data(self):
        """Only healthy data (is_fault_injected=False) is used."""
        data = create_mixed_data(n_healthy=80, n_fault=20)
        builder = BaselineBuilder()
        
        profile = builder.build(data, asset_id="test-motor")
        
        # Should only use 80 healthy samples, not 100
        assert profile.training_window.sample_count == 80
        assert profile.signal_profiles["voltage_v"].sample_count == 80

    def test_explicit_training_window(self):
        """Training window filter works correctly."""
        data = create_healthy_data(100)
        builder = BaselineBuilder()
        
        start = datetime.now(timezone.utc) - timedelta(minutes=50)
        end = datetime.now(timezone.utc) - timedelta(minutes=20)
        
        profile = builder.build(
            data,
            asset_id="test-motor",
            training_window=(start, end)
        )
        
        # Should only include points in the window
        assert profile.training_window.sample_count < 100

    def test_fails_on_empty_data(self):
        """Empty data raises error."""
        data = pd.DataFrame()
        builder = BaselineBuilder()
        
        with pytest.raises(BaselineBuildError):
            builder.build(data, asset_id="test-motor")

    def test_fails_on_low_coverage(self):
        """Insufficient coverage raises error."""
        data = create_healthy_data(100)
        # Set 50% of voltage to NaN
        data.loc[data.index[:50], 'voltage_v'] = np.nan
        
        builder = BaselineBuilder(min_coverage=0.80)
        
        with pytest.raises(BaselineBuildError) as exc_info:
            builder.build(data, asset_id="test-motor")
        
        assert "coverage" in str(exc_info.value).lower()

    def test_ignores_nan_in_statistics(self):
        """NaN values are ignored, not included in mean/std."""
        data = create_healthy_data(100)
        # Set a few values to NaN (still above 80% coverage)
        data.loc[data.index[:10], 'voltage_v'] = np.nan
        
        builder = BaselineBuilder()
        profile = builder.build(data, asset_id="test-motor")
        
        # Sample count should reflect valid samples only
        assert profile.signal_profiles["voltage_v"].sample_count == 90


class TestSignalProfile:
    """Test signal profile structure."""

    def test_profile_has_required_fields(self):
        """Profile has mean, std, min, max, sample_count."""
        profile = SignalProfile(
            mean=230.0,
            std=5.0,
            min=215.0,
            max=245.0,
            sample_count=100
        )
        
        assert profile.mean == 230.0
        assert profile.std == 5.0
        assert profile.min == 215.0
        assert profile.max == 245.0
        assert profile.sample_count == 100

    def test_min_max_are_descriptive(self):
        """min/max reflect observed data, not prescriptive bounds."""
        data = create_healthy_data(100)
        builder = BaselineBuilder()
        
        profile = builder.build(data, asset_id="test-motor")
        
        voltage_profile = profile.signal_profiles["voltage_v"]
        # min/max should match actual data range
        assert voltage_profile.min <= data['voltage_v'].min()
        # Allow small floating point differences
        assert abs(voltage_profile.max - data['voltage_v'].max()) < 0.001


class TestBaselinePersistence:
    """Test JSON save/load."""

    def test_save_and_load_roundtrip(self):
        """Baseline can be saved and loaded from JSON."""
        data = create_healthy_data(100)
        builder = BaselineBuilder()
        profile = builder.build(data, asset_id="test-motor")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = save_baseline(profile, directory=tmpdir)
            
            assert filepath.exists()
            assert filepath.suffix == ".json"
            
            loaded = load_baseline(str(filepath))
            
            assert loaded.asset_id == profile.asset_id
            assert loaded.signal_profiles["voltage_v"].mean == profile.signal_profiles["voltage_v"].mean


class TestValidation:
    """Test baseline validation."""

    def test_validate_baseline_structure(self):
        """Valid baseline passes structure validation."""
        data = create_healthy_data(100)
        builder = BaselineBuilder()
        profile = builder.build(data, asset_id="test-motor")
        
        errors = validate_baseline(profile)
        
        assert len(errors) == 0

    def test_check_healthy_data_passes_3sigma(self):
        """Healthy data used to build baseline should pass 3-sigma check."""
        data = create_healthy_data(100)
        builder = BaselineBuilder()
        profile = builder.build(data, asset_id="test-motor")
        
        result = check_data_against_baseline(data, profile)
        
        # Most healthy data should pass (allowing some outliers)
        assert result.pass_rate > 0.95

    def test_get_expected_range(self):
        """Expected range calculation is correct."""
        data = create_healthy_data(100)
        builder = BaselineBuilder()
        profile = builder.build(data, asset_id="test-motor")
        
        lower, upper = get_expected_range(profile, "voltage_v", sigma_multiplier=3.0)
        
        voltage = profile.signal_profiles["voltage_v"]
        expected_lower = voltage.mean - 3 * voltage.std
        expected_upper = voltage.mean + 3 * voltage.std
        
        assert abs(lower - expected_lower) < 0.001
        assert abs(upper - expected_upper) < 0.001

    def test_validation_is_read_only(self):
        """Validation does not modify the profile."""
        data = create_healthy_data(100)
        builder = BaselineBuilder()
        profile = builder.build(data, asset_id="test-motor")
        
        original_mean = profile.signal_profiles["voltage_v"].mean
        
        # Run validation multiple times
        for _ in range(3):
            check_data_against_baseline(data, profile)
        
        # Profile should be unchanged
        assert profile.signal_profiles["voltage_v"].mean == original_mean


class TestAssetSpecific:
    """Test that profiles are asset-specific."""

    def test_one_asset_one_profile(self):
        """Each asset gets its own profile."""
        data1 = create_healthy_data(100)
        data2 = create_healthy_data(100)
        
        builder = BaselineBuilder()
        
        profile1 = builder.build(data1, asset_id="motor-1")
        profile2 = builder.build(data2, asset_id="motor-2")
        
        assert profile1.asset_id == "motor-1"
        assert profile2.asset_id == "motor-2"
        assert profile1.baseline_id != profile2.baseline_id
