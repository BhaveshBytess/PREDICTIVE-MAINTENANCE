"""
Generator Configuration — Constants and Patterns

This module defines all configuration constants for the hybrid data generator.
Values are based on Indian Grid standards and NASA/IMS failure patterns.

CONTRACTS.md Reference:
- Section 3.3: Signal Constraints
- Indian Grid: 230V, 50Hz
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict


# =============================================================================
# INDIAN GRID CONSTANTS (Base Layer)
# =============================================================================

# Nominal voltage (Indian Grid Standard)
NOMINAL_VOLTAGE_V: float = 230.0

# Grid frequency (Hz)
GRID_FREQUENCY_HZ: float = 50.0

# Voltage fluctuation range (±10% as per Indian Grid tolerance)
VOLTAGE_FLUCTUATION_MIN: float = 0.90  # -10%
VOLTAGE_FLUCTUATION_MAX: float = 1.10  # +10%

# Nominal current for a typical 5kW induction motor at full load
NOMINAL_CURRENT_A: float = 22.0  # ~5kW motor at 230V, PF=0.85


# =============================================================================
# POWER FACTOR CONFIGURATION
# =============================================================================

# Healthy motor power factor range
PF_HEALTHY_MIN: float = 0.80
PF_HEALTHY_MAX: float = 0.92

# Degraded motor power factor (drops during mechanical issues)
PF_DEGRADED_MIN: float = 0.60
PF_DEGRADED_MAX: float = 0.75


# =============================================================================
# VIBRATION CONFIGURATION (NASA/IMS Patterns)
# =============================================================================

class DegradationMode(str, Enum):
    """
    Failure modes based on NASA/IMS bearing dataset patterns.
    
    Reference: IMS Bearing Dataset (Qiu et al., 2006)
    - Inner race defect: High-frequency periodic impulses
    - Outer race defect: Lower frequency, amplitude modulated
    - Rolling element defect: Irregular impulses
    - Normal wear: Gradual broadband increase
    """
    HEALTHY = "healthy"
    INNER_RACE_FAULT = "inner_race_fault"
    OUTER_RACE_FAULT = "outer_race_fault"
    ROLLING_ELEMENT_FAULT = "rolling_element_fault"
    NORMAL_WEAR = "normal_wear"


@dataclass(frozen=True)
class VibrationEnvelope:
    """
    Vibration envelope parameters extracted from NASA/IMS patterns.
    
    These are SCALED envelopes, not raw values.
    The generator uses these to synthesize realistic degradation profiles.
    """
    base_g: float           # Baseline RMS vibration (g)
    noise_std: float        # Noise standard deviation
    spike_probability: float  # Probability of impulse spike per sample
    spike_amplitude: float   # Amplitude multiplier for spikes
    progression_rate: float  # Rate of degradation progression (0-1)


# NASA/IMS Pattern Envelopes (Extracted and Scaled)
# These represent characteristic signatures, not raw sensor values
VIBRATION_ENVELOPES: Dict[DegradationMode, VibrationEnvelope] = {
    DegradationMode.HEALTHY: VibrationEnvelope(
        base_g=0.15,
        noise_std=0.02,
        spike_probability=0.001,
        spike_amplitude=1.2,
        progression_rate=0.0
    ),
    DegradationMode.INNER_RACE_FAULT: VibrationEnvelope(
        base_g=0.8,
        noise_std=0.15,
        spike_probability=0.15,  # High-frequency periodic impulses
        spike_amplitude=2.5,
        progression_rate=0.02
    ),
    DegradationMode.OUTER_RACE_FAULT: VibrationEnvelope(
        base_g=0.6,
        noise_std=0.12,
        spike_probability=0.08,  # Lower frequency
        spike_amplitude=2.0,
        progression_rate=0.015
    ),
    DegradationMode.ROLLING_ELEMENT_FAULT: VibrationEnvelope(
        base_g=0.5,
        noise_std=0.18,
        spike_probability=0.05,  # Irregular impulses
        spike_amplitude=3.0,
        progression_rate=0.01
    ),
    DegradationMode.NORMAL_WEAR: VibrationEnvelope(
        base_g=0.25,
        noise_std=0.05,
        spike_probability=0.01,
        spike_amplitude=1.5,
        progression_rate=0.005  # Slow progression
    ),
}


# =============================================================================
# OPERATING STATE CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class StateProfile:
    """Signal profile for each operating state."""
    current_multiplier: float   # Multiplier for nominal current
    voltage_noise_factor: float  # Noise factor for voltage
    vibration_active: bool       # Whether vibration is meaningful


STATE_PROFILES: Dict[str, StateProfile] = {
    "RUNNING": StateProfile(
        current_multiplier=1.0,
        voltage_noise_factor=1.0,
        vibration_active=True
    ),
    "IDLE": StateProfile(
        current_multiplier=0.15,  # Minimal draw when idle
        voltage_noise_factor=0.5,
        vibration_active=False    # No meaningful vibration
    ),
    "OFF": StateProfile(
        current_multiplier=0.0,
        voltage_noise_factor=0.2,
        vibration_active=False
    ),
}


# =============================================================================
# GENERATOR DEFAULTS
# =============================================================================

DEFAULT_ASSET_ID: str = "motor-001"
DEFAULT_SAMPLE_INTERVAL_MS: int = 1000  # 1 second between samples
