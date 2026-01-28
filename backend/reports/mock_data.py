"""
Mock Data Generator — Simulated Historical Data for Reports

Generates realistic 24h statistics and 7-day trends that ALIGN
with the current sensor state. This is simulation data for demo purposes.

Rule: History aligns with current state:
- If current state is CRITICAL, history shows degradation trend
- If current state is LOW, history shows stable baseline

IMPORTANT: This module generates SIMULATED data only.
Real sensor readings come from the persisted HealthReport (Snapshot Rule).
"""

import random
import math
from typing import Dict, List, Optional

from backend.reports.constants import GOLDEN_BASELINE, SIGNAL_METADATA


def generate_24h_stats(
    current_readings: Dict[str, float],
    risk_level: str,
    seed: Optional[int] = None
) -> Dict[str, Dict[str, float]]:
    """
    Generate mock 24h statistics aligned with current state.
    
    Strategy:
    - Start from golden baseline values
    - Adjust ranges based on risk level severity
    - Ensure current reading falls within generated range
    
    Args:
        current_readings: Latest sensor values (voltage_v, current_a, etc.)
        risk_level: Current risk level (LOW, MODERATE, HIGH, CRITICAL)
        seed: Random seed for reproducibility
        
    Returns:
        Dict mapping signal name to {min, max, mean, std}
    """
    if seed is not None:
        random.seed(seed)
    
    # Risk level affects variability
    variability_factor = {
        "LOW": 1.0,
        "MODERATE": 1.5,
        "HIGH": 2.0,
        "CRITICAL": 3.0
    }.get(risk_level, 1.0)
    
    stats: Dict[str, Dict[str, float]] = {}
    
    for signal, baseline in GOLDEN_BASELINE.items():
        current_value = current_readings.get(signal)
        
        if current_value is None:
            # Use baseline if current reading not available
            current_value = baseline["mean"]
        
        base_mean = baseline["mean"]
        base_std = baseline["std"]
        
        # Generate stats that encompass the current reading
        # The mean should be between baseline and current value
        if risk_level in ("HIGH", "CRITICAL"):
            # For high risk, mean shifts toward current abnormal value
            shift_factor = 0.7 if risk_level == "CRITICAL" else 0.4
            generated_mean = base_mean + (current_value - base_mean) * shift_factor
        else:
            # For low risk, mean stays close to baseline
            generated_mean = base_mean + (current_value - base_mean) * 0.2
        
        # Standard deviation increases with risk
        generated_std = base_std * variability_factor
        
        # Calculate min/max ensuring current value is within range
        potential_min = generated_mean - (2.5 * generated_std)
        potential_max = generated_mean + (2.5 * generated_std)
        
        # Adjust to include current value
        actual_min = min(potential_min, current_value * 0.95)
        actual_max = max(potential_max, current_value * 1.05)
        
        # Add some randomness
        noise = random.uniform(-0.02, 0.02) * base_mean
        
        stats[signal] = {
            "min": round(actual_min + noise, 3),
            "max": round(actual_max - noise, 3),
            "mean": round(generated_mean, 3),
            "std": round(generated_std, 3)
        }
    
    return stats


def generate_7day_sparkline(
    current_value: float,
    risk_level: str,
    signal_name: str,
    points: int = 168  # 24 * 7 = 168 hourly points
) -> List[float]:
    """
    Generate 7-day trend data ending at current value.
    
    Trend shape by risk level:
    - LOW: Flat stable line with minor noise around baseline
    - MODERATE: Slight trend toward current value
    - HIGH: Clear trend toward current value
    - CRITICAL: Sharp exponential curve to current value
    
    Args:
        current_value: The current sensor reading (last point in trend)
        risk_level: Determines trend shape
        signal_name: Used to get baseline reference
        points: Number of data points (default 168 = 7 days hourly)
        
    Returns:
        List of float values representing the trend (oldest first)
    """
    # Get baseline for this signal
    baseline = GOLDEN_BASELINE.get(signal_name, {"mean": current_value, "std": 0.1})
    baseline_mean = baseline["mean"]
    baseline_std = baseline["std"]
    
    # Determine if this signal indicates degradation when high or low
    direction = SIGNAL_METADATA.get(signal_name, {}).get("direction", "high")
    
    trend: List[float] = []
    
    # Calculate the deviation from baseline
    deviation = current_value - baseline_mean
    
    for i in range(points):
        t = i / (points - 1)  # Normalized time 0 to 1
        
        if risk_level == "LOW":
            # Flat with minor noise around baseline
            noise = random.gauss(0, baseline_std * 0.3)
            value = baseline_mean + noise
            
        elif risk_level == "MODERATE":
            # Gradual linear trend
            trend_component = deviation * t * 0.6
            noise = random.gauss(0, baseline_std * 0.4)
            value = baseline_mean + trend_component + noise
            
        elif risk_level == "HIGH":
            # More pronounced trend with some acceleration
            # Use quadratic curve
            trend_component = deviation * (t ** 1.5) * 0.8
            noise = random.gauss(0, baseline_std * 0.5)
            value = baseline_mean + trend_component + noise
            
        else:  # CRITICAL
            # Exponential-like curve showing rapid degradation
            # Slower initially, accelerates toward end
            trend_component = deviation * (1 - math.exp(-3 * t)) * 0.95
            noise = random.gauss(0, baseline_std * 0.3)
            value = baseline_mean + trend_component + noise
        
        # Ensure last point is close to current value
        if i == points - 1:
            value = current_value
        
        # Clamp to reasonable values (no negative readings)
        if signal_name == "power_factor":
            value = max(0.3, min(1.0, value))
        else:
            value = max(0.0, value)
        
        trend.append(round(value, 4))
    
    return trend


def generate_derived_features(
    current_readings: Dict[str, float],
    risk_level: str
) -> Dict[str, float]:
    """
    Calculate derived features for report display.
    
    Features:
    - voltage_stability: Simulated voltage standard deviation over 1 hour
    - power_vibration_ratio: power_kw / vibration_g (health indicator)
    - efficiency_index: Combined metric
    
    Args:
        current_readings: Current sensor values
        risk_level: Current risk level
        
    Returns:
        Dict of derived feature names to values
    """
    voltage = current_readings.get("voltage_v", 230.0)
    current = current_readings.get("current_a", 15.0)
    pf = current_readings.get("power_factor", 0.92)
    vibration = current_readings.get("vibration_g", 0.15)
    power = current_readings.get("power_kw", 3.17)
    
    # Voltage stability (lower is better)
    # In critical conditions, voltage is more unstable
    stability_base = {
        "LOW": 1.5,
        "MODERATE": 3.0,
        "HIGH": 5.0,
        "CRITICAL": 8.0
    }.get(risk_level, 2.0)
    voltage_stability = stability_base + random.uniform(-0.5, 0.5)
    
    # Power to vibration ratio (higher is better for healthy motors)
    # Healthy: high power, low vibration = high ratio
    # Unhealthy: power drops or vibration increases = low ratio
    if vibration > 0.01:
        power_vib_ratio = power / vibration
    else:
        power_vib_ratio = power / 0.01  # Avoid division by zero
    
    # Efficiency index (0-100, higher is better)
    # Based on power factor and current efficiency
    nominal_power = 230 * 15 * 0.92 / 1000  # ~3.17 kW
    power_efficiency = min(100, (power / nominal_power) * 100) if nominal_power > 0 else 0
    pf_contribution = pf * 100
    efficiency_index = (power_efficiency * 0.4 + pf_contribution * 0.6)
    
    return {
        "voltage_stability": round(voltage_stability, 2),
        "power_vibration_ratio": round(power_vib_ratio, 2),
        "efficiency_index": round(efficiency_index, 1),
        "apparent_power_kva": round(voltage * current / 1000, 2),
        "reactive_power_kvar": round(voltage * current * math.sqrt(1 - pf**2) / 1000, 2)
    }


def generate_feature_contributions(
    current_readings: Dict[str, float],
    risk_level: str
) -> List[Dict[str, any]]:
    """
    Generate feature contribution breakdown for ML explainability.
    
    Simulates which features contributed most to the anomaly score.
    Contributions are weighted based on deviation from baseline.
    
    Args:
        current_readings: Current sensor values
        risk_level: Current risk level
        
    Returns:
        List of dicts with feature, percent, status, value
    """
    contributions = []
    total_deviation = 0.0
    deviations = {}
    
    # Calculate raw deviations from baseline
    for signal, baseline in GOLDEN_BASELINE.items():
        current = current_readings.get(signal, baseline["mean"])
        mean = baseline["mean"]
        std = baseline["std"]
        
        if std > 0:
            z_score = abs(current - mean) / std
        else:
            z_score = 0.0
        
        deviations[signal] = z_score
        total_deviation += z_score
    
    # Normalize to percentages
    if total_deviation < 0.01:
        total_deviation = 1.0  # Avoid division by zero
    
    for signal, z_score in deviations.items():
        percent = (z_score / total_deviation) * 100
        
        # Determine status based on z-score
        if z_score < 1.0:
            status = "normal"
        elif z_score < 2.5:
            status = "elevated"
        else:
            status = "critical"
        
        # Get human-readable name
        display_name = SIGNAL_METADATA.get(signal, {}).get("name", signal.replace("_", " ").title())
        
        contributions.append({
            "feature": display_name,
            "feature_key": signal,
            "percent": round(percent, 1),
            "status": status,
            "value": current_readings.get(signal, 0),
            "z_score": round(z_score, 2)
        })
    
    # Sort by contribution percentage (highest first)
    contributions.sort(key=lambda x: x["percent"], reverse=True)
    
    return contributions


def get_primary_driver(contributions: List[Dict]) -> str:
    """
    Identify the primary driver (highest contributing feature).
    
    Args:
        contributions: List of feature contributions
        
    Returns:
        Feature key of the primary driver (e.g., "vibration_g")
    """
    if not contributions:
        return "default"
    
    primary = contributions[0]
    feature_key = primary.get("feature_key", "default")
    
    # Map to action categories
    if "vibration" in feature_key:
        return "vibration"
    elif "voltage" in feature_key:
        return "voltage"
    elif "power_factor" in feature_key or "pf" in feature_key.lower():
        return "power_factor"
    elif "current" in feature_key:
        return "current"
    else:
        return "default"
