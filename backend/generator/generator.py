"""
Hybrid Data Generator — Digital Twin Sensor Simulator

This module generates realistic sensor events for an induction motor
operating in the Indian electrical grid context with optional NASA/IMS
failure signature injection.

CONTRACTS.md Reference: Section 3.1 - Canonical Sensor Event
agent.md Reference: Section 2 - Hybrid Data Approach

CRITICAL: This is a SIMULATOR. It does NOT claim to have real sensors attached.
"""

import random
from datetime import datetime, timezone
from typing import Iterator, Optional
from uuid import uuid4

from .config import (
    DEFAULT_ASSET_ID,
    DegradationMode,
    GRID_FREQUENCY_HZ,
    NOMINAL_CURRENT_A,
    NOMINAL_VOLTAGE_V,
    PF_DEGRADED_MAX,
    PF_DEGRADED_MIN,
    PF_HEALTHY_MAX,
    PF_HEALTHY_MIN,
    STATE_PROFILES,
    VIBRATION_ENVELOPES,
    VOLTAGE_FLUCTUATION_MAX,
    VOLTAGE_FLUCTUATION_MIN,
    VibrationEnvelope,
)
from .schemas import (
    Asset,
    AssetType,
    CanonicalSensorEvent,
    Context,
    OperatingState,
    Signals,
)


class HybridDataGenerator:
    """
    Hybrid Data Generator for Digital Twin simulation.
    
    Produces Canonical Sensor Events conforming to CONTRACTS.md.
    
    Features:
    - Indian Grid baseline (230V/50Hz) with realistic fluctuations
    - NASA/IMS failure signature injection (mathematically synthesized)
    - Deterministic output with fixed random seed
    - Operating state awareness (RUNNING/IDLE/OFF)
    
    Usage:
        generator = HybridDataGenerator(seed=42)
        for event in generator.generate(count=100):
            print(event.model_dump_json())
    """

    def __init__(
        self,
        asset_id: str = DEFAULT_ASSET_ID,
        seed: Optional[int] = None,
        degradation_mode: DegradationMode = DegradationMode.HEALTHY,
        degradation_progress: float = 0.0,
    ):
        """
        Initialize the generator.
        
        Args:
            asset_id: Unique identifier for the simulated asset
            seed: Random seed for deterministic output (None for random)
            degradation_mode: Type of failure to simulate
            degradation_progress: Initial degradation level (0.0 = start, 1.0 = severe)
        """
        self.asset_id = asset_id
        self.seed = seed
        self.degradation_mode = degradation_mode
        self.degradation_progress = min(max(degradation_progress, 0.0), 1.0)
        
        # Initialize random state
        self._rng = random.Random(seed)
        
        # Current operating state
        self._operating_state = OperatingState.RUNNING
        
        # Event counter for progression
        self._event_count = 0

    def set_operating_state(self, state: OperatingState) -> None:
        """Set the current operating state."""
        self._operating_state = state

    def set_degradation_mode(
        self,
        mode: DegradationMode,
        initial_progress: float = 0.0
    ) -> None:
        """
        Set the degradation mode for failure injection.
        
        Args:
            mode: The failure mode to simulate
            initial_progress: Starting degradation level (0.0-1.0)
        """
        self.degradation_mode = mode
        self.degradation_progress = min(max(initial_progress, 0.0), 1.0)

    def _generate_voltage(self) -> float:
        """
        Generate voltage reading with Indian Grid characteristics.
        
        Simulates realistic voltage fluctuations around 230V nominal.
        """
        profile = STATE_PROFILES[self._operating_state.value]
        
        # Base fluctuation within grid tolerance
        fluctuation = self._rng.uniform(
            VOLTAGE_FLUCTUATION_MIN,
            VOLTAGE_FLUCTUATION_MAX
        )
        
        # Add noise based on operating state
        noise = self._rng.gauss(0, 2.0 * profile.voltage_noise_factor)
        
        voltage = NOMINAL_VOLTAGE_V * fluctuation + noise
        return max(0.0, voltage)

    def _generate_current(self, voltage: float) -> float:
        """
        Generate current reading based on operating state and load.
        
        Current varies with operating state and has load-dependent noise.
        """
        profile = STATE_PROFILES[self._operating_state.value]
        
        if profile.current_multiplier == 0.0:
            return 0.0
        
        # Base current with state multiplier
        base_current = NOMINAL_CURRENT_A * profile.current_multiplier
        
        # Add load variation noise (±10%)
        noise = self._rng.gauss(0, base_current * 0.05)
        
        # Degradation affects current draw (stressed motor draws more)
        if self._operating_state == OperatingState.RUNNING:
            degradation_factor = 1.0 + (self.degradation_progress * 0.15)
            base_current *= degradation_factor
        
        return max(0.0, base_current + noise)

    def _generate_power_factor(self) -> float:
        """
        Generate power factor based on motor health.
        
        Healthy motors: 0.80-0.92
        Degraded motors: 0.60-0.75 (drops during mechanical issues)
        """
        if self._operating_state == OperatingState.OFF:
            return 0.0
        
        if self._operating_state == OperatingState.IDLE:
            # Idle has lower but stable PF
            return self._rng.uniform(0.70, 0.80)
        
        # Running state - PF depends on degradation
        if self.degradation_mode == DegradationMode.HEALTHY:
            pf = self._rng.uniform(PF_HEALTHY_MIN, PF_HEALTHY_MAX)
        else:
            # Interpolate based on degradation progress
            healthy_pf = self._rng.uniform(PF_HEALTHY_MIN, PF_HEALTHY_MAX)
            degraded_pf = self._rng.uniform(PF_DEGRADED_MIN, PF_DEGRADED_MAX)
            pf = healthy_pf - (healthy_pf - degraded_pf) * self.degradation_progress
        
        return min(max(pf, 0.0), 1.0)

    def _generate_vibration(self) -> float:
        """
        Generate vibration reading using NASA/IMS pattern envelopes.
        
        CRITICAL: Only RUNNING state produces meaningful vibration.
        IDLE/OFF states do NOT trigger failure signatures.
        """
        profile = STATE_PROFILES[self._operating_state.value]
        
        if not profile.vibration_active:
            # Minimal baseline vibration for non-running states
            return self._rng.uniform(0.01, 0.03)
        
        # Get the vibration envelope for current degradation mode
        envelope: VibrationEnvelope = VIBRATION_ENVELOPES[self.degradation_mode]
        
        # Calculate effective amplitude based on progression
        effective_base = envelope.base_g * (1.0 + self.degradation_progress)
        
        # Base vibration with Gaussian noise
        vibration = self._rng.gauss(effective_base, envelope.noise_std)
        
        # Apply impulse spikes (characteristic of bearing faults)
        if self._rng.random() < envelope.spike_probability:
            spike = envelope.spike_amplitude * (1.0 + self.degradation_progress * 0.5)
            vibration += self._rng.uniform(0.5, 1.0) * spike * envelope.base_g
        
        return max(0.0, vibration)

    def _calculate_power_kw(
        self,
        voltage_v: float,
        current_a: float,
        power_factor: float
    ) -> float:
        """
        Calculate power in Kilowatts.
        
        Formula: P(kW) = (V × I × PF) / 1000
        
        Per user mandate: Convert Watts to Kilowatts.
        """
        return (voltage_v * current_a * power_factor) / 1000.0

    def _advance_degradation(self) -> None:
        """
        Advance degradation progression based on mode.
        
        Only advances when RUNNING (degradation doesn't progress when off/idle).
        """
        if self._operating_state != OperatingState.RUNNING:
            return
        
        if self.degradation_mode == DegradationMode.HEALTHY:
            return
        
        envelope = VIBRATION_ENVELOPES[self.degradation_mode]
        self.degradation_progress = min(
            1.0,
            self.degradation_progress + envelope.progression_rate
        )

    def generate_event(self) -> CanonicalSensorEvent:
        """
        Generate a single Canonical Sensor Event.
        
        Returns:
            A validated CanonicalSensorEvent conforming to CONTRACTS.md
        """
        # Generate signals
        voltage = self._generate_voltage()
        current = self._generate_current(voltage)
        power_factor = self._generate_power_factor()
        power_kw = self._calculate_power_kw(voltage, current, power_factor)
        vibration = self._generate_vibration()
        
        # Build event
        event = CanonicalSensorEvent(
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            asset=Asset(
                asset_id=self.asset_id,
                asset_type=AssetType.INDUCTION_MOTOR
            ),
            signals=Signals(
                voltage_v=round(voltage, 2),
                current_a=round(current, 2),
                power_factor=round(power_factor, 3),
                power_kw=round(power_kw, 3),
                vibration_g=round(vibration, 4)
            ),
            context=Context(
                operating_state=self._operating_state,
                source="simulator"
            )
        )
        
        # Advance degradation for next event
        self._advance_degradation()
        self._event_count += 1
        
        return event

    def generate(self, count: int) -> Iterator[CanonicalSensorEvent]:
        """
        Generate multiple sensor events.
        
        Args:
            count: Number of events to generate
            
        Yields:
            CanonicalSensorEvent instances
        """
        for _ in range(count):
            yield self.generate_event()

    def reset(self, seed: Optional[int] = None) -> None:
        """
        Reset the generator state.
        
        Args:
            seed: New random seed (uses original if None)
        """
        if seed is not None:
            self.seed = seed
        self._rng = random.Random(self.seed)
        self._event_count = 0
        self.degradation_progress = 0.0
        self._operating_state = OperatingState.RUNNING
