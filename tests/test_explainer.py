"""
Explainability Engine Tests

Tests verify:
- Math safety: std=0, epsilon rule
- Fixed templates with observed value + baseline
- Top 3 contributors only
- LOW risk returns empty list
- Text matches data values
"""

from datetime import datetime, timezone

import pytest

from backend.ml.baseline import BaselineProfile, SignalProfile, TrainingWindow
from backend.rules.assessor import RiskLevel
from backend.rules.explainer import (
    ExplanationGenerator,
    FeatureContribution,
    EPSILON_RELATIVE,
    MAX_EXPLANATIONS,
)


def create_test_baseline() -> BaselineProfile:
    """Create a test baseline profile."""
    return BaselineProfile(
        baseline_id="test-baseline",
        asset_id="motor-1",
        training_window=TrainingWindow(
            start=datetime.now(timezone.utc),
            end=datetime.now(timezone.utc),
            sample_count=100,
            valid_sample_ratio=1.0
        ),
        signal_profiles={
            'voltage_v': SignalProfile(mean=230.0, std=5.0, min=215.0, max=245.0, sample_count=100),
            'current_a': SignalProfile(mean=15.0, std=1.5, min=10.0, max=20.0, sample_count=100),
            'vibration_g': SignalProfile(mean=0.15, std=0.03, min=0.05, max=0.3, sample_count=100),
        },
        feature_profiles={
            'voltage_rolling_mean_1h': SignalProfile(mean=230.0, std=2.0, min=225.0, max=235.0, sample_count=100),
            'vibration_intensity_rms': SignalProfile(mean=0.15, std=0.02, min=0.1, max=0.25, sample_count=100),
        }
    )


class TestMathSafety:
    """Test math safety constraints."""

    def test_handles_std_zero(self):
        """std=0 should not cause division by zero."""
        baseline = create_test_baseline()
        # Set std to 0
        baseline.signal_profiles['voltage_v'] = SignalProfile(
            mean=230.0, std=0.0, min=230.0, max=230.0, sample_count=100
        )
        
        generator = ExplanationGenerator(baseline)
        
        features = {'voltage_v': 235.0}
        contributions = generator.analyze_contributions(features)
        
        # Should not raise, zscore should be 0
        assert len(contributions) == 1
        assert contributions[0].zscore == 0.0

    def test_epsilon_rule_ignores_tiny_differences(self):
        """Tiny absolute differences (<1% of mean) should be ignored."""
        baseline = create_test_baseline()
        generator = ExplanationGenerator(baseline)
        
        # Voltage mean is 230, 1% is 2.3
        # A difference of 2.0 should be ignored even with high z-score
        features = {'voltage_v': 232.0}  # Only 0.87% difference
        
        contributions = generator.analyze_contributions(features)
        
        # Should be marked as not significant
        voltage_contrib = [c for c in contributions if c.feature_name == 'voltage_v'][0]
        assert not voltage_contrib.is_significant

    def test_large_difference_is_significant(self):
        """Large absolute differences should be significant."""
        baseline = create_test_baseline()
        generator = ExplanationGenerator(baseline)
        
        # 20% above mean
        features = {'voltage_v': 276.0}  # +20%
        
        contributions = generator.analyze_contributions(features)
        
        voltage_contrib = [c for c in contributions if c.feature_name == 'voltage_v'][0]
        assert voltage_contrib.is_significant


class TestTemplates:
    """Test fixed template usage."""

    def test_explanation_includes_observed_value(self):
        """Explanation must include observed value."""
        baseline = create_test_baseline()
        generator = ExplanationGenerator(baseline)
        
        features = {'vibration_g': 0.5}  # High vibration
        
        explanations = generator.generate(features, RiskLevel.HIGH, baseline)
        
        assert len(explanations) > 0
        # Check that value appears in reason
        assert "0.50" in explanations[0].reason or "0.5" in explanations[0].reason

    def test_explanation_includes_baseline_reference(self):
        """Explanation must include baseline reference."""
        baseline = create_test_baseline()
        generator = ExplanationGenerator(baseline)
        
        features = {'vibration_g': 0.5}
        
        explanations = generator.generate(features, RiskLevel.HIGH, baseline)
        
        assert len(explanations) > 0
        # Should reference baseline (mean, max, or min)
        reason = explanations[0].reason.lower()
        assert 'baseline' in reason or 'normal' in reason or 'maximum' in reason or 'minimum' in reason


class TestRiskFiltering:
    """Test explanation filtering by risk level."""

    def test_low_risk_returns_empty(self):
        """LOW risk should return empty explanations."""
        baseline = create_test_baseline()
        generator = ExplanationGenerator(baseline)
        
        features = {'voltage_v': 230.0}  # Normal
        
        explanations = generator.generate(features, RiskLevel.LOW, baseline)
        
        assert explanations == []

    def test_moderate_risk_generates_explanations(self):
        """MODERATE risk should generate explanations."""
        baseline = create_test_baseline()
        generator = ExplanationGenerator(baseline)
        
        features = {'vibration_g': 0.5}  # Elevated
        
        explanations = generator.generate(features, RiskLevel.MODERATE, baseline)
        
        assert len(explanations) >= 1

    def test_critical_risk_generates_explanations(self):
        """CRITICAL risk should generate explanations."""
        baseline = create_test_baseline()
        generator = ExplanationGenerator(baseline)
        
        features = {'vibration_g': 1.0}  # Very high
        
        explanations = generator.generate(features, RiskLevel.CRITICAL, baseline)
        
        assert len(explanations) >= 1


class TestTop3Limit:
    """Test that only top 3 contributors are returned."""

    def test_max_three_explanations(self):
        """Should return at most 3 explanations."""
        baseline = create_test_baseline()
        generator = ExplanationGenerator(baseline)
        
        # All features anomalous
        features = {
            'voltage_v': 280.0,  # High
            'current_a': 25.0,   # High
            'vibration_g': 0.8,  # High
            'voltage_rolling_mean_1h': 260.0,  # High
            'vibration_intensity_rms': 0.5,    # High
        }
        
        explanations = generator.generate(features, RiskLevel.CRITICAL, baseline)
        
        assert len(explanations) <= MAX_EXPLANATIONS

    def test_ranked_by_significance(self):
        """Explanations should be ranked by significance."""
        baseline = create_test_baseline()
        generator = ExplanationGenerator(baseline)
        
        # Vibration is most anomalous
        features = {
            'voltage_v': 240.0,        # +2 std
            'vibration_g': 1.0,        # +28 std (most anomalous)
            'current_a': 18.0,         # +2 std
        }
        
        contributions = generator.analyze_contributions(features, baseline)
        
        # Vibration should be first (highest z-score)
        assert contributions[0].feature_name == 'vibration_g'


class TestFeatureContribution:
    """Test feature contribution analysis."""

    def test_zscore_calculation(self):
        """Z-score should be (value - mean) / std."""
        baseline = create_test_baseline()
        generator = ExplanationGenerator(baseline)
        
        # voltage mean=230, std=5
        # value=240 -> zscore = (240-230)/5 = 2.0
        features = {'voltage_v': 240.0}
        
        contributions = generator.analyze_contributions(features, baseline)
        
        voltage_contrib = contributions[0]
        expected_zscore = (240.0 - 230.0) / 5.0
        assert abs(voltage_contrib.zscore - expected_zscore) < 0.01

    def test_negative_zscore_for_low_values(self):
        """Values below mean should have negative z-score."""
        baseline = create_test_baseline()
        generator = ExplanationGenerator(baseline)
        
        features = {'voltage_v': 220.0}  # Below mean
        
        contributions = generator.analyze_contributions(features, baseline)
        
        assert contributions[0].zscore < 0


class TestSystemsNominal:
    """Test nominal explanation generation."""

    def test_generate_nominal_message(self):
        """Should generate 'systems nominal' for LOW risk."""
        generator = ExplanationGenerator()
        
        nominal = generator.generate_nominal()
        
        assert "normal" in nominal.reason.lower() or "nominal" in nominal.reason.lower()
        assert nominal.confidence_score == 1.0
