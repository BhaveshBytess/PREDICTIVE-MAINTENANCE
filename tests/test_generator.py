"""
Unit Tests — Hybrid Data Generator (Phase 1)

Tests verify:
1. Generated events conform to Canonical Sensor Event schema
2. Vibration fault modes trigger correctly
3. Output is deterministic with fixed seeds (deep JSON equality)
4. power_kw calculation is correct (V * I * PF / 1000)
5. IDLE/OFF states do not trigger failure signatures

CONTRACTS.md Reference: Section 3.1
"""

import json
from datetime import datetime, timezone

import pytest

from backend.generator import (
    CanonicalSensorEvent,
    DegradationMode,
    HybridDataGenerator,
    OperatingState,
)
from backend.generator.config import VIBRATION_ENVELOPES


class TestSchemaCompliance:
    """Test that generated events conform to CONTRACTS.md schema."""

    def test_event_has_required_fields(self):
        """Verify all required fields are present."""
        generator = HybridDataGenerator(seed=42)
        event = generator.generate_event()
        
        # Top-level fields
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.asset is not None
        assert event.signals is not None
        assert event.context is not None
        
        # Asset fields
        assert event.asset.asset_id is not None
        assert event.asset.asset_type is not None
        
        # Signal fields
        assert event.signals.voltage_v is not None
        assert event.signals.current_a is not None
        assert event.signals.power_factor is not None
        assert event.signals.power_kw is not None
        assert event.signals.vibration_g is not None
        
        # Context fields
        assert event.context.operating_state is not None
        assert event.context.source == "simulator"

    def test_event_validates_as_pydantic_model(self):
        """Verify event passes Pydantic validation."""
        generator = HybridDataGenerator(seed=42)
        event = generator.generate_event()
        
        # Should not raise
        validated = CanonicalSensorEvent.model_validate(event.model_dump())
        assert validated.event_id == event.event_id

    def test_power_factor_bounded(self):
        """Verify power factor is strictly 0.0 to 1.0."""
        generator = HybridDataGenerator(seed=42)
        
        for _ in range(100):
            event = generator.generate_event()
            assert 0.0 <= event.signals.power_factor <= 1.0

    def test_timestamp_is_utc(self):
        """Verify timestamps are UTC."""
        generator = HybridDataGenerator(seed=42)
        event = generator.generate_event()
        
        assert event.timestamp.tzinfo is not None
        assert event.timestamp.tzinfo == timezone.utc

    def test_source_is_always_simulator(self):
        """Verify source is always 'simulator' per Digital Twin context."""
        generator = HybridDataGenerator(seed=42)
        
        for _ in range(10):
            event = generator.generate_event()
            assert event.context.source == "simulator"


class TestDeterminism:
    """Test deterministic output with fixed seeds."""

    def test_same_seed_produces_identical_events(self):
        """Verify deep JSON equality for same seed."""
        gen1 = HybridDataGenerator(seed=12345)
        gen2 = HybridDataGenerator(seed=12345)
        
        for _ in range(50):
            event1 = gen1.generate_event()
            event2 = gen2.generate_event()
            
            # Convert to JSON for deep comparison (excluding dynamic fields)
            json1 = event1.model_dump(exclude={"event_id", "timestamp"})
            json2 = event2.model_dump(exclude={"event_id", "timestamp"})
            
            assert json1 == json2, "Events should be identical for same seed"

    def test_different_seeds_produce_different_events(self):
        """Verify different seeds produce different outputs."""
        gen1 = HybridDataGenerator(seed=111)
        gen2 = HybridDataGenerator(seed=222)
        
        events1 = [gen.generate_event() for gen in [gen1] * 10]
        events2 = [gen.generate_event() for gen in [gen2] * 10]
        
        # At least some signals should differ
        voltages1 = [e.signals.voltage_v for e in events1]
        voltages2 = [e.signals.voltage_v for e in events2]
        
        assert voltages1 != voltages2

    def test_reset_restores_determinism(self):
        """Verify reset() restores deterministic sequence."""
        generator = HybridDataGenerator(seed=99999)
        
        # Generate some events
        first_run = [generator.generate_event().model_dump(exclude={"event_id", "timestamp"}) 
                     for _ in range(10)]
        
        # Reset and regenerate
        generator.reset()
        second_run = [generator.generate_event().model_dump(exclude={"event_id", "timestamp"}) 
                      for _ in range(10)]
        
        assert first_run == second_run


class TestPowerCalculation:
    """Test power_kw calculation correctness."""

    def test_power_kw_formula(self):
        """Verify power_kw = (V * I * PF) / 1000."""
        generator = HybridDataGenerator(seed=42)
        
        for _ in range(100):
            event = generator.generate_event()
            
            expected_power = (
                event.signals.voltage_v * 
                event.signals.current_a * 
                event.signals.power_factor
            ) / 1000.0
            
            # Allow for rounding differences (tolerance of 0.01 kW)
            assert abs(event.signals.power_kw - round(expected_power, 3)) < 0.01

    def test_power_kw_is_zero_when_off(self):
        """Verify power is zero when motor is OFF."""
        generator = HybridDataGenerator(seed=42)
        generator.set_operating_state(OperatingState.OFF)
        
        event = generator.generate_event()
        
        # Current should be 0, so power should be 0
        assert event.signals.current_a == 0.0
        assert event.signals.power_kw == 0.0


class TestVibrationFaultModes:
    """Test NASA/IMS vibration signature injection."""

    def test_healthy_mode_low_vibration(self):
        """Verify healthy mode produces low vibration."""
        generator = HybridDataGenerator(
            seed=42,
            degradation_mode=DegradationMode.HEALTHY
        )
        
        vibrations = [generator.generate_event().signals.vibration_g 
                      for _ in range(100)]
        
        avg_vibration = sum(vibrations) / len(vibrations)
        healthy_envelope = VIBRATION_ENVELOPES[DegradationMode.HEALTHY]
        
        # Should be close to healthy baseline
        assert avg_vibration < healthy_envelope.base_g * 2

    def test_fault_mode_higher_vibration(self):
        """Verify fault modes produce higher vibration than healthy."""
        seed = 42
        
        # Healthy baseline
        healthy_gen = HybridDataGenerator(
            seed=seed,
            degradation_mode=DegradationMode.HEALTHY
        )
        healthy_vibs = [healthy_gen.generate_event().signals.vibration_g 
                        for _ in range(100)]
        healthy_avg = sum(healthy_vibs) / len(healthy_vibs)
        
        # Fault mode with progression
        fault_gen = HybridDataGenerator(
            seed=seed,
            degradation_mode=DegradationMode.INNER_RACE_FAULT,
            degradation_progress=0.5
        )
        fault_vibs = [fault_gen.generate_event().signals.vibration_g 
                      for _ in range(100)]
        fault_avg = sum(fault_vibs) / len(fault_vibs)
        
        assert fault_avg > healthy_avg

    def test_degradation_progresses_over_time(self):
        """Verify degradation advances during RUNNING state."""
        generator = HybridDataGenerator(
            seed=42,
            degradation_mode=DegradationMode.NORMAL_WEAR,
            degradation_progress=0.0
        )
        
        initial_progress = generator.degradation_progress
        
        # Generate events to advance degradation
        for _ in range(100):
            generator.generate_event()
        
        assert generator.degradation_progress > initial_progress


class TestOperatingStates:
    """Test operating state behavior."""

    def test_idle_state_low_current(self):
        """Verify IDLE state has reduced current."""
        generator = HybridDataGenerator(seed=42)
        
        # Running current
        generator.set_operating_state(OperatingState.RUNNING)
        running_event = generator.generate_event()
        running_current = running_event.signals.current_a
        
        # Idle current (reset seed for fair comparison of state effect)
        generator.reset(seed=42)
        generator.set_operating_state(OperatingState.IDLE)
        idle_event = generator.generate_event()
        idle_current = idle_event.signals.current_a
        
        assert idle_current < running_current

    def test_off_state_zero_current(self):
        """Verify OFF state has zero current."""
        generator = HybridDataGenerator(seed=42)
        generator.set_operating_state(OperatingState.OFF)
        
        event = generator.generate_event()
        
        assert event.signals.current_a == 0.0

    def test_idle_does_not_trigger_failure_vibration(self):
        """Verify IDLE state does not produce failure signatures."""
        generator = HybridDataGenerator(
            seed=42,
            degradation_mode=DegradationMode.INNER_RACE_FAULT,
            degradation_progress=0.8
        )
        generator.set_operating_state(OperatingState.IDLE)
        
        vibrations = [generator.generate_event().signals.vibration_g 
                      for _ in range(50)]
        
        # All vibrations should be minimal (baseline idle vibration)
        for vib in vibrations:
            assert vib < 0.1  # Well below fault thresholds

    def test_off_does_not_trigger_failure_vibration(self):
        """Verify OFF state does not produce failure signatures."""
        generator = HybridDataGenerator(
            seed=42,
            degradation_mode=DegradationMode.INNER_RACE_FAULT,
            degradation_progress=0.9
        )
        generator.set_operating_state(OperatingState.OFF)
        
        vibrations = [generator.generate_event().signals.vibration_g 
                      for _ in range(50)]
        
        # All vibrations should be minimal
        for vib in vibrations:
            assert vib < 0.1

    def test_degradation_does_not_progress_when_idle(self):
        """Verify degradation only progresses when RUNNING."""
        generator = HybridDataGenerator(
            seed=42,
            degradation_mode=DegradationMode.NORMAL_WEAR,
            degradation_progress=0.5
        )
        generator.set_operating_state(OperatingState.IDLE)
        
        initial_progress = generator.degradation_progress
        
        # Generate events in IDLE state
        for _ in range(50):
            generator.generate_event()
        
        # Progress should not have changed
        assert generator.degradation_progress == initial_progress

    def test_degradation_does_not_progress_when_off(self):
        """Verify degradation does not progress when OFF."""
        generator = HybridDataGenerator(
            seed=42,
            degradation_mode=DegradationMode.NORMAL_WEAR,
            degradation_progress=0.5
        )
        generator.set_operating_state(OperatingState.OFF)
        
        initial_progress = generator.degradation_progress
        
        for _ in range(50):
            generator.generate_event()
        
        assert generator.degradation_progress == initial_progress


class TestJSONSerialization:
    """Test JSON output format."""

    def test_event_serializes_to_valid_json(self):
        """Verify event can be serialized to JSON."""
        generator = HybridDataGenerator(seed=42)
        event = generator.generate_event()
        
        # Should not raise
        json_str = event.model_dump_json()
        parsed = json.loads(json_str)
        
        assert "event_id" in parsed
        assert "timestamp" in parsed
        assert "asset" in parsed
        assert "signals" in parsed
        assert "context" in parsed

    def test_json_structure_matches_contract(self):
        """Verify JSON structure matches CONTRACTS.md."""
        generator = HybridDataGenerator(seed=42)
        event = generator.generate_event()
        
        data = event.model_dump()
        
        # Asset structure
        assert "asset_id" in data["asset"]
        assert "asset_type" in data["asset"]
        
        # Signals structure
        assert "voltage_v" in data["signals"]
        assert "current_a" in data["signals"]
        assert "power_factor" in data["signals"]
        assert "power_kw" in data["signals"]
        assert "vibration_g" in data["signals"]
        
        # Context structure
        assert "operating_state" in data["context"]
        assert "source" in data["context"]
