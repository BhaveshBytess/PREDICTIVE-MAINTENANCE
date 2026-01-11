"""
Feature Calculator — Vectorized Feature Computation

Uses Pandas for all calculations (no Python for loops).
Past-only windowing to prevent future data leakage.
Returns NaN for incomplete windows (cold-start).

All calculations are stateless and idempotent.
"""

import math
from typing import Optional

import numpy as np
import pandas as pd


# Window configuration
WINDOW_DURATION = "1h"  # 1 hour rolling window
MIN_PERIODS_RATIO = 0.5  # Require at least 50% of expected points


def calculate_voltage_rolling_mean(
    df: pd.DataFrame,
    evaluation_idx: int,
    window: str = WINDOW_DURATION
) -> Optional[float]:
    """
    Calculate rolling mean of voltage_v over past window.
    
    Window includes data from [evaluation_idx - window, evaluation_idx] (inclusive).
    
    Args:
        df: DataFrame with 'timestamp' index and 'voltage_v' column
        evaluation_idx: Index position of the evaluation point
        window: Window duration (default: 1h) - used for approximate point count
        
    Returns:
        Rolling mean value, or None if insufficient data (NaN)
    """
    if df.empty or 'voltage_v' not in df.columns:
        return None
    
    if evaluation_idx < 0 or evaluation_idx >= len(df):
        return None
    
    # Get window data (past-only, including current point)
    # Approximate 1 hour = 60 points at 1 point/minute
    window_start = max(0, evaluation_idx - 59)  # -59 to include 60 points total
    window_data = df['voltage_v'].iloc[window_start:evaluation_idx + 1]  # +1 to include current
    
    if len(window_data) < 2:  # Need at least 2 points for meaningful mean
        return None
    
    # Calculate mean using vectorized Pandas
    mean_value = window_data.mean()
    
    return float(mean_value) if not pd.isna(mean_value) else None


def calculate_current_spike_count(
    df: pd.DataFrame,
    evaluation_idx: int,
    window: str = WINDOW_DURATION,
    sigma_threshold: float = 2.0
) -> Optional[int]:
    """
    Count current readings > σ_threshold above LOCAL window mean.
    
    Uses local window statistics only (not global baseline).
    
    Args:
        df: DataFrame with 'timestamp' index and 'current_a' column
        evaluation_idx: Index position of the evaluation point
        window: Window duration (default: 1h)
        sigma_threshold: Number of standard deviations for spike detection
        
    Returns:
        Count of spikes, or None if insufficient data (NaN)
    """
    if df.empty or 'current_a' not in df.columns:
        return None
    
    # Get window data (past only)
    # Approximate 1 hour of data points based on index
    window_start = max(0, evaluation_idx - 60)  # Assuming ~1 point/minute
    window_data = df['current_a'].iloc[window_start:evaluation_idx + 1]
    
    if len(window_data) < 3:  # Need at least 3 points for meaningful σ
        return None
    
    # Calculate LOCAL window statistics
    local_mean = window_data.mean()
    local_std = window_data.std()
    
    if pd.isna(local_std) or local_std == 0:
        return 0  # No variation = no spikes
    
    # Count values above threshold
    threshold = local_mean + (sigma_threshold * local_std)
    spike_count = (window_data > threshold).sum()
    
    return int(spike_count)


def calculate_power_factor_efficiency_score(
    power_factor: float
) -> Optional[float]:
    """
    Calculate normalized power factor efficiency score.
    
    Score is strictly bounded [0.0, 1.0] and monotonic.
    Higher power factor = higher score.
    
    This is a pure transformation - no thresholds or "Good/Bad" labels.
    Interpretation belongs in Phase 7 Rules.
    
    Args:
        power_factor: Raw power factor value (0.0 to 1.0)
        
    Returns:
        Efficiency score [0.0, 1.0], or None if invalid input
    """
    if power_factor is None or math.isnan(power_factor):
        return None
    
    # Clamp to valid range
    pf = max(0.0, min(1.0, power_factor))
    
    # Direct mapping: PF is already 0-1, monotonic
    # Score = PF (linear, no transformation needed)
    # This preserves interpretability: score of 0.85 means PF was 0.85
    return round(pf, 4)


def calculate_vibration_rms(
    df: pd.DataFrame,
    evaluation_idx: int,
    window: str = WINDOW_DURATION
) -> Optional[float]:
    """
    Calculate RMS (Root Mean Square) of vibration_g over past window.
    
    Formula: RMS = √(Σ(v²)/n)
    
    Args:
        df: DataFrame with 'timestamp' index and 'vibration_g' column
        evaluation_idx: Index position of the evaluation point
        window: Window duration (default: 1h)
        
    Returns:
        RMS value, or None if insufficient data (NaN)
    """
    if df.empty or 'vibration_g' not in df.columns:
        return None
    
    # Get window data (past only)
    window_start = max(0, evaluation_idx - 60)
    window_data = df['vibration_g'].iloc[window_start:evaluation_idx + 1]
    
    if len(window_data) < 2:  # Need at least 2 points
        return None
    
    # Calculate RMS using vectorized operations
    squared = window_data ** 2
    mean_squared = squared.mean()
    
    if pd.isna(mean_squared):
        return None
    
    rms = np.sqrt(mean_squared)
    
    return round(float(rms), 6)


def compute_all_features(
    df: pd.DataFrame,
    evaluation_idx: int,
    current_power_factor: float
) -> dict:
    """
    Compute all contract-mandated features for a single evaluation point.
    
    This function is stateless and idempotent.
    
    Args:
        df: Historical data DataFrame with timestamp index
        evaluation_idx: Index of the point to compute features FOR
        current_power_factor: Power factor at evaluation point
        
    Returns:
        Dictionary of feature values (None for NaN/insufficient data)
    """
    return {
        "voltage_rolling_mean_1h": calculate_voltage_rolling_mean(df, evaluation_idx),
        "current_spike_count": calculate_current_spike_count(df, evaluation_idx),
        "power_factor_efficiency_score": calculate_power_factor_efficiency_score(current_power_factor),
        "vibration_intensity_rms": calculate_vibration_rms(df, evaluation_idx),
    }
