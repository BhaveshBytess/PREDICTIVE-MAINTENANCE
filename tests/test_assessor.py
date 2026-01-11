"""
Health Assessment Tests

Tests verify:
- Deterministic health formula: Health = 100 * (1 - anomaly_score)
- Named threshold constants
- Risk monotonicity: More anomalies = Higher risk
- CRITICAL always has explanation
- RUL as heuristic lookup
- Trend calculation as slope
"""

from datetime import datetime, timezone

import pytest

from backend.rules.assessor import (
    HealthAssessor,
    HealthReport,
    RiskLevel,
    THRESHOLD_CRITICAL,
    THRESHOLD_HIGH,
    THRESHOLD_MODERATE,
)


class TestHealthScoreComputation:
    """Test deterministic health score formula."""

    def test_health_formula_is_deterministic(self):
        """Health = 100 * (1.0 - anomaly_score)."""
        assessor = HealthAssessor()
        
        # anomaly_score 0 -> health 100
        assert assessor.compute_health_score(0.0) == 100
        
        # anomaly_score 1 -> health 0
        assert assessor.compute_health_score(1.0) == 0
        
        # anomaly_score 0.5 -> health 50
        assert assessor.compute_health_score(0.5) == 50
        
        # anomaly_score 0.25 -> health 75
        assert assessor.compute_health_score(0.25) == 75

    def test_same_input_same_output(self):
        """Determinism: same input always gives same output."""
        assessor = HealthAssessor()
        
        for _ in range(10):
            assert assessor.compute_health_score(0.3) == 70

    def test_health_score_clamped(self):
        """Out-of-range anomaly scores are clamped."""
        assessor = HealthAssessor()
        
        # Below 0
        assert assessor.compute_health_score(-0.5) == 100
        
        # Above 1
        assert assessor.compute_health_score(1.5) == 0

    def test_health_score_bounds(self):
        """Health score is always [0, 100]."""
        assessor = HealthAssessor()
        
        for score in [0.0, 0.1, 0.5, 0.9, 1.0]:
            health = assessor.compute_health_score(score)
            assert 0 <= health <= 100


class TestRiskClassification:
    """Test risk level classification with named thresholds."""

    def test_uses_named_constants(self):
        """Verify thresholds are explicitly defined constants."""
        # These should be module-level constants
        assert isinstance(THRESHOLD_CRITICAL, int)
        assert isinstance(THRESHOLD_HIGH, int)
        assert isinstance(THRESHOLD_MODERATE, int)
        
        # Verify ordering
        assert THRESHOLD_CRITICAL < THRESHOLD_HIGH < THRESHOLD_MODERATE

    def test_critical_below_threshold(self):
        """Health < THRESHOLD_CRITICAL = CRITICAL."""
        assessor = HealthAssessor()
        
        assert assessor.classify_risk_level(THRESHOLD_CRITICAL - 1) == RiskLevel.CRITICAL
        assert assessor.classify_risk_level(0) == RiskLevel.CRITICAL

    def test_high_between_thresholds(self):
        """THRESHOLD_CRITICAL <= Health < THRESHOLD_HIGH = HIGH."""
        assessor = HealthAssessor()
        
        assert assessor.classify_risk_level(THRESHOLD_CRITICAL) == RiskLevel.HIGH
        assert assessor.classify_risk_level(THRESHOLD_HIGH - 1) == RiskLevel.HIGH

    def test_moderate_between_thresholds(self):
        """THRESHOLD_HIGH <= Health < THRESHOLD_MODERATE = MODERATE."""
        assessor = HealthAssessor()
        
        assert assessor.classify_risk_level(THRESHOLD_HIGH) == RiskLevel.MODERATE
        assert assessor.classify_risk_level(THRESHOLD_MODERATE - 1) == RiskLevel.MODERATE

    def test_low_above_threshold(self):
        """Health >= THRESHOLD_MODERATE = LOW."""
        assessor = HealthAssessor()
        
        assert assessor.classify_risk_level(THRESHOLD_MODERATE) == RiskLevel.LOW
        assert assessor.classify_risk_level(100) == RiskLevel.LOW


class TestRiskMonotonicity:
    """Test that more anomalies = higher risk."""

    def test_monotonicity_holds(self):
        """Higher anomaly score must result in equal or higher risk."""
        assessor = HealthAssessor()
        
        risk_order = {
            RiskLevel.LOW: 0,
            RiskLevel.MODERATE: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }
        
        prev_risk_value = 0
        
        # Increasing anomaly scores
        for anomaly in [0.0, 0.25, 0.5, 0.75, 1.0]:
            health = assessor.compute_health_score(anomaly)
            risk = assessor.classify_risk_level(health)
            risk_value = risk_order[risk]
            
            assert risk_value >= prev_risk_value, (
                f"Monotonicity violated: anomaly {anomaly} -> risk {risk}"
            )
            prev_risk_value = risk_value


class TestRULEstimation:
    """Test RUL heuristic lookup."""

    def test_rul_is_heuristic_lookup(self):
        """RUL should be based on risk level, not physics."""
        assessor = HealthAssessor()
        
        # CRITICAL has lowest RUL
        rul_critical = assessor.estimate_rul(RiskLevel.CRITICAL)
        rul_high = assessor.estimate_rul(RiskLevel.HIGH)
        rul_moderate = assessor.estimate_rul(RiskLevel.MODERATE)
        rul_low = assessor.estimate_rul(RiskLevel.LOW)
        
        assert rul_critical < rul_high < rul_moderate < rul_low

    def test_rul_is_positive(self):
        """RUL should never be negative."""
        assessor = HealthAssessor()
        
        for risk in RiskLevel:
            rul = assessor.estimate_rul(risk)
            assert rul >= 0


class TestTrendCalculation:
    """Test anomaly trend as slope."""

    def test_trend_is_slope(self):
        """Trend = (latest - earliest) / (n - 1)."""
        assessor = HealthAssessor()
        
        # Increasing scores: trend should be positive
        scores = [0.2, 0.3, 0.4, 0.5, 0.6]
        trend = assessor.calculate_trend(scores)
        
        expected = (0.6 - 0.2) / 4  # 0.1
        assert abs(trend - expected) < 0.001

    def test_trend_positive_means_worsening(self):
        """Positive trend = anomaly increasing = worsening."""
        assessor = HealthAssessor()
        
        worsening = [0.1, 0.2, 0.3]
        assert assessor.calculate_trend(worsening) > 0

    def test_trend_negative_means_improving(self):
        """Negative trend = anomaly decreasing = improving."""
        assessor = HealthAssessor()
        
        improving = [0.5, 0.3, 0.1]
        assert assessor.calculate_trend(improving) < 0

    def test_insufficient_data_returns_none(self):
        """Less than 2 points cannot calculate trend."""
        assessor = HealthAssessor()
        
        assert assessor.calculate_trend([]) is None
        assert assessor.calculate_trend([0.5]) is None


class TestExplanations:
    """Test explanation generation."""

    def test_critical_always_has_explanation(self):
        """CRITICAL risk MUST have at least one explanation."""
        assessor = HealthAssessor()
        
        # High anomaly score -> CRITICAL
        report = assessor.assess(asset_id="motor-1", anomaly_score=0.95)
        
        assert report.risk_level == RiskLevel.CRITICAL
        assert len(report.explanations) >= 1

    def test_low_risk_no_explanation_required(self):
        """LOW risk doesn't require explanation."""
        assessor = HealthAssessor()
        
        report = assessor.assess(asset_id="motor-1", anomaly_score=0.1)
        
        assert report.risk_level == RiskLevel.LOW
        # Explanations may or may not be present for LOW


class TestMetadata:
    """Test audit metadata."""

    def test_metadata_includes_versions(self):
        """Metadata must include detector version AND baseline ID."""
        assessor = HealthAssessor(
            detector_version="2.1.0",
            baseline_id="abc123"
        )
        
        report = assessor.assess(asset_id="motor-1", anomaly_score=0.5)
        
        assert "detector:2.1.0" in report.metadata.model_version
        assert "baseline:abc123" in report.metadata.model_version


class TestFullAssessment:
    """Test complete assessment flow."""

    def test_assess_returns_valid_report(self):
        """Complete assessment produces valid HealthReport."""
        assessor = HealthAssessor()
        
        report = assessor.assess(
            asset_id="motor-1",
            anomaly_score=0.6
        )
        
        assert isinstance(report, HealthReport)
        assert report.asset_id == "motor-1"
        assert 0 <= report.health_score <= 100
        assert isinstance(report.risk_level, RiskLevel)
        assert report.maintenance_window_days >= 0

    def test_report_schema_matches_contracts(self):
        """Report has all required fields from CONTRACTS.md."""
        assessor = HealthAssessor()
        
        report = assessor.assess(asset_id="motor-1", anomaly_score=0.5)
        
        # Required fields
        assert hasattr(report, 'report_id')
        assert hasattr(report, 'timestamp')
        assert hasattr(report, 'asset_id')
        assert hasattr(report, 'health_score')
        assert hasattr(report, 'risk_level')
        assert hasattr(report, 'maintenance_window_days')
        assert hasattr(report, 'explanations')
        assert hasattr(report, 'metadata')
