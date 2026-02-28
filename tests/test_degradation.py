"""
Phase 20 — Cumulative Prognostics Unit Tests

Tests the degradation engine functions:
- compute_cumulative_degradation: Miner's Rule, monotonicity, clamping
- health_from_degradation: DI → health score
- rul_from_degradation: DI + damage_rate → RUL hours
- risk_from_health: health → risk level string
- crossed_thresholds: DI milestone detection
"""

import pytest

from backend.rules.assessor import (
    SENSITIVITY_CONSTANT,
    HEALTHY_FLOOR,
    DI_THRESHOLD_15,
    DI_THRESHOLD_30,
    DI_THRESHOLD_50,
    DI_THRESHOLD_75,
    compute_cumulative_degradation,
    health_from_degradation,
    rul_from_degradation,
    risk_from_health,
    crossed_thresholds,
)


# ============================================================================
# compute_cumulative_degradation
# ============================================================================

class TestComputeCumulativeDegradation:
    """Tests for the core DI accumulation function."""

    def test_zero_score_produces_no_damage(self):
        """Healthy batch (score=0) should not increase DI."""
        new_di, rate = compute_cumulative_degradation(0.0, 0.0)
        assert new_di == 0.0
        assert rate == 0.0

    def test_formula_matches_spec(self):
        """DI_inc = (effective_severity^2) * 0.0005 for dt=1, after dead-zone remap."""
        raw_score = 0.8
        effective = (raw_score - HEALTHY_FLOOR) / (1.0 - HEALTHY_FLOOR)
        expected_rate = (effective ** 2) * SENSITIVITY_CONSTANT
        new_di, rate = compute_cumulative_degradation(0.0, raw_score)
        assert abs(rate - expected_rate) < 1e-10
        assert abs(new_di - expected_rate) < 1e-10

    def test_max_severity_rate(self):
        """At max score=1.0, effective_severity=1.0, rate = SENSITIVITY_CONSTANT."""
        new_di, rate = compute_cumulative_degradation(0.0, 1.0)
        assert abs(rate - SENSITIVITY_CONSTANT) < 1e-10

    def test_monotonicity_never_decreases(self):
        """DI must never decrease, even with score=0 after accumulation."""
        # Accumulate some damage
        di = 0.0
        di, _ = compute_cumulative_degradation(di, 1.0)
        assert di > 0.0

        # Now apply zero severity — DI must stay the same
        old_di = di
        di, _ = compute_cumulative_degradation(di, 0.0)
        assert di >= old_di

    def test_monotonicity_strict(self):
        """Verify DI only goes up across many iterations."""
        di = 0.0
        prev = -1.0
        for severity in [0.5, 0.0, 0.3, 0.0, 1.0, 0.0, 0.0]:
            di, _ = compute_cumulative_degradation(di, severity)
            assert di >= prev
            prev = di

    def test_clamp_at_one(self):
        """DI should never exceed 1.0."""
        di = 0.999
        new_di, _ = compute_cumulative_degradation(di, 1.0, dt=100.0)
        assert new_di == 1.0

    def test_dt_scaling(self):
        """Larger dt should produce proportionally more damage."""
        di1, r1 = compute_cumulative_degradation(0.0, 0.5, dt=1.0)
        di2, r2 = compute_cumulative_degradation(0.0, 0.5, dt=2.0)
        assert abs(r1 - r2) < 1e-10  # rate is per-second, same
        assert abs(di2 - 2 * di1) < 1e-10  # accumulated damage scales with dt

    def test_severity_clamping(self):
        """Scores outside [0, 1] should be clamped."""
        _, rate_neg = compute_cumulative_degradation(0.0, -0.5)
        assert rate_neg == 0.0  # severity clamped to 0

        _, rate_over = compute_cumulative_degradation(0.0, 1.5)
        assert abs(rate_over - SENSITIVITY_CONSTANT) < 1e-10  # clamped to 1.0

    # ── Dead-zone tests ──

    def test_dead_zone_healthy_noise_zero_damage(self):
        """Scores below HEALTHY_FLOOR must produce EXACTLY zero damage."""
        for score in [0.0, 0.1, 0.3, 0.5, 0.64, 0.649]:
            new_di, rate = compute_cumulative_degradation(0.0, score)
            assert rate == 0.0, f"score={score} should be dead-zone, got rate={rate}"
            assert new_di == 0.0, f"score={score} should not move DI, got {new_di}"

    def test_dead_zone_boundary_exact_floor(self):
        """Score exactly at HEALTHY_FLOOR → effective_severity=0.0 → zero damage."""
        new_di, rate = compute_cumulative_degradation(0.0, HEALTHY_FLOOR)
        assert rate == 0.0
        assert new_di == 0.0

    def test_dead_zone_just_above_floor(self):
        """Score just above HEALTHY_FLOOR → tiny but non-zero damage."""
        score = HEALTHY_FLOOR + 0.01
        new_di, rate = compute_cumulative_degradation(0.0, score)
        assert rate > 0.0
        assert new_di > 0.0

    def test_dead_zone_remap_math(self):
        """Verify effective_severity = (score - FLOOR) / (1 - FLOOR)."""
        score = 0.85
        effective = (score - HEALTHY_FLOOR) / (1.0 - HEALTHY_FLOOR)
        expected_rate = (effective ** 2) * SENSITIVITY_CONSTANT
        _, rate = compute_cumulative_degradation(0.0, score)
        assert abs(rate - expected_rate) < 1e-12

    def test_dead_zone_no_accumulation_over_time(self):
        """1000 cycles of healthy noise (score=0.4) must leave DI at 0.0."""
        di = 0.0
        for _ in range(1000):
            di, _ = compute_cumulative_degradation(di, 0.4)
        assert di == 0.0


# ============================================================================
# health_from_degradation
# ============================================================================

class TestHealthFromDegradation:
    """Tests for DI → health score conversion."""

    def test_new_asset(self):
        """DI=0 → health=100."""
        assert health_from_degradation(0.0) == 100

    def test_dead_asset(self):
        """DI=1.0 → health=0."""
        assert health_from_degradation(1.0) == 0

    def test_midpoint(self):
        """DI=0.5 → health=50."""
        assert health_from_degradation(0.5) == 50

    def test_quarter(self):
        """DI=0.25 → health=75."""
        assert health_from_degradation(0.25) == 75

    def test_clamped_high(self):
        """Negative DI shouldn't produce health > 100."""
        assert health_from_degradation(-0.1) == 100

    def test_clamped_low(self):
        """DI > 1.0 shouldn't produce health < 0."""
        assert health_from_degradation(1.5) == 0


# ============================================================================
# rul_from_degradation
# ============================================================================

class TestRulFromDegradation:
    """Tests for RUL estimation from DI + damage rate."""

    def test_zero_damage_rate(self):
        """Zero damage rate → max sentinel RUL."""
        rul = rul_from_degradation(0.5, 0.0)
        assert rul == 99999.0

    def test_known_rate(self):
        """DI=0.5, rate=0.0005/s → remaining=0.5 → 0.5/0.0005 = 1000s = 0.28h."""
        rul = rul_from_degradation(0.5, SENSITIVITY_CONSTANT)
        expected = (1.0 - 0.5) / SENSITIVITY_CONSTANT / 3600.0
        assert abs(rul - expected) < 0.01

    def test_fully_degraded(self):
        """DI=1.0 → remaining=0 → RUL=0."""
        rul = rul_from_degradation(1.0, SENSITIVITY_CONSTANT)
        assert rul == 0.0


# ============================================================================
# risk_from_health
# ============================================================================

class TestRiskFromHealth:
    """Tests for health → risk level mapping."""

    def test_critical(self):
        assert risk_from_health(20) == "CRITICAL"

    def test_high(self):
        assert risk_from_health(40) == "HIGH"

    def test_moderate(self):
        assert risk_from_health(60) == "MODERATE"

    def test_low(self):
        assert risk_from_health(90) == "LOW"

    def test_boundary_critical(self):
        assert risk_from_health(25) == "CRITICAL"

    def test_boundary_high(self):
        assert risk_from_health(50) == "HIGH"

    def test_boundary_moderate(self):
        assert risk_from_health(75) == "MODERATE"


# ============================================================================
# crossed_thresholds
# ============================================================================

class TestCrossedThresholds:
    """Tests for DI milestone detection."""

    def test_no_crossing(self):
        """DI stays within same zone → no crossings."""
        assert crossed_thresholds(0.10, 0.12) == []

    def test_cross_15(self):
        """DI crosses 15% threshold."""
        result = crossed_thresholds(0.10, 0.16)
        assert len(result) == 1
        assert result[0][1] == "15%"

    def test_cross_multiple(self):
        """DI jumps across multiple thresholds at once."""
        result = crossed_thresholds(0.10, 0.55)
        labels = [r[1] for r in result]
        assert "15%" in labels
        assert "30%" in labels
        assert "50%" in labels
        assert "75%" not in labels

    def test_cross_all(self):
        """DI jumps from 0 to 1 → crosses all 4 thresholds."""
        result = crossed_thresholds(0.0, 1.0)
        assert len(result) == 4

    def test_exact_boundary(self):
        """DI lands exactly on a threshold."""
        result = crossed_thresholds(0.14, DI_THRESHOLD_15)
        assert len(result) == 1
        assert result[0][1] == "15%"

    def test_already_past_threshold(self):
        """DI was already past threshold → no crossing."""
        result = crossed_thresholds(0.20, 0.25)
        assert len(result) == 0  # 15% was already passed


# ============================================================================
# Integration: Full lifecycle
# ============================================================================

class TestDegradationLifecycle:
    """End-to-end lifecycle test simulating a monitoring session."""

    def test_healthy_to_degraded_lifecycle(self):
        """
        Simulate: 100 healthy seconds → 500 fault seconds → verify DI progression.

        With dead-zone (HEALTHY_FLOOR=0.65):
        - 100s of healthy (score=0.02 < 0.65) → DI stays at 0.0  (dead-zone)
        - 500s of fault (score=0.9) → effective = (0.9 - 0.65) / 0.35 ≈ 0.7143
          damage_rate = (0.7143^2) * 0.0005 ≈ 0.000255
          DI ≈ 500 * 0.000255 ≈ 0.1276
        """
        di = 0.0

        # 100 seconds of healthy (score=0.02 < HEALTHY_FLOOR) → zero damage
        for _ in range(100):
            di, rate = compute_cumulative_degradation(di, 0.02)
        assert di == 0.0  # Dead-zone: exactly zero

        # 500 seconds of severe fault (score=0.9 > HEALTHY_FLOOR)
        for _ in range(500):
            old = di
            di, rate = compute_cumulative_degradation(di, 0.9)
            assert di >= old  # Monotonicity

        # DI should be meaningful but not maxed
        effective = (0.9 - HEALTHY_FLOOR) / (1.0 - HEALTHY_FLOOR)
        expected_di = 500 * (effective ** 2) * SENSITIVITY_CONSTANT
        assert abs(di - expected_di) < 0.001
        assert di > 0.05
        assert di < 1.0

        # Health should reflect damage
        health = health_from_degradation(di)
        assert health < 95

        # RUL should be finite
        rul = rul_from_degradation(di, rate)
        assert rul < 99999.0
        assert rul > 0

    def test_prolonged_fault_causes_escalation(self):
        """
        N seconds of max severity (score=1.0) → DI=1.0, health=0, CRITICAL.
        effective_severity = (1.0 - 0.65) / 0.35 = 1.0
        damage_rate = 1.0^2 * 0.0005 = 0.0005/s
        DI=1.0 after 2000 seconds.
        """
        di = 0.0
        for _ in range(2000):
            di, rate = compute_cumulative_degradation(di, 1.0)
        
        assert di == 1.0 or abs(di - 1.0) < 1e-6  # float precision
        assert health_from_degradation(di) == 0
        assert risk_from_health(health_from_degradation(di)) == "CRITICAL"
