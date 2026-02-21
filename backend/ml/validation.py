"""
Baseline Validation — Read-Only Verification Against Profiles

Validates that data fits within the baseline profile using 3-Sigma Rule.
All functions are read-only - no self-healing or adaptive baselines.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# pandas lazy-loaded to speed up cold start

from .baseline import BaselineProfile, SignalProfile


class ValidationResult:
    """Result of baseline validation."""
    
    def __init__(self):
        self.passed = True
        self.total_checks = 0
        self.failed_checks = 0
        self.violations: List[Dict] = []
    
    def add_violation(self, column: str, value: float, expected_range: Tuple[float, float]):
        """Record a violation."""
        self.violations.append({
            "column": column,
            "value": value,
            "expected_min": expected_range[0],
            "expected_max": expected_range[1]
        })
        self.failed_checks += 1
        self.passed = False
    
    def add_pass(self):
        """Record a passing check."""
        self.total_checks += 1
    
    @property
    def pass_rate(self) -> float:
        """Percentage of checks that passed."""
        if self.total_checks == 0:
            return 1.0
        return (self.total_checks - self.failed_checks) / self.total_checks


def calculate_3sigma_bounds(profile: SignalProfile) -> Tuple[float, float]:
    """
    Calculate 3-Sigma bounds from profile.
    
    Returns (lower_bound, upper_bound) where:
    - lower_bound = mean - 3 * std
    - upper_bound = mean + 3 * std
    """
    lower = profile.mean - (3 * profile.std)
    upper = profile.mean + (3 * profile.std)
    return (lower, upper)


def validate_baseline(profile: BaselineProfile) -> List[str]:
    """
    Validate that a baseline profile is complete and well-formed.
    
    This is a READ-ONLY check of the profile structure.
    
    Args:
        profile: BaselineProfile to validate
        
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    # Check required fields
    if not profile.asset_id:
        errors.append("asset_id is required")
    
    if not profile.signal_profiles:
        errors.append("At least one signal profile is required")
    
    # Check each signal profile
    for name, sig_profile in profile.signal_profiles.items():
        if sig_profile.std < 0:
            errors.append(f"Signal '{name}' has negative std: {sig_profile.std}")
        if sig_profile.sample_count == 0:
            errors.append(f"Signal '{name}' has zero samples")
        if sig_profile.min > sig_profile.max:
            errors.append(f"Signal '{name}' has min > max")
    
    # Check training window
    if profile.training_window.sample_count == 0:
        errors.append("Training window has zero samples")
    
    return errors


def check_data_against_baseline(
    data,
    profile: BaselineProfile,
    sigma_multiplier: float = 3.0
) -> ValidationResult:
    """
    Verify that data fits within the baseline profile using N-Sigma Rule.
    
    This is a READ-ONLY validation - no modifications to profile or data.
    
    Default uses 3-Sigma Rule: values should be within mean ± 3*std.
    
    Args:
        data: DataFrame with sensor data to validate
        profile: BaselineProfile to validate against
        sigma_multiplier: Number of standard deviations for bounds (default: 3.0)
        
    Returns:
        ValidationResult with pass/fail status and violations
    """
    result = ValidationResult()
    
    if data.empty:
        return result
    
    # Check each signal
    for col_name, sig_profile in profile.signal_profiles.items():
        if col_name not in data.columns:
            continue
        
        # Calculate bounds
        lower = sig_profile.mean - (sigma_multiplier * sig_profile.std)
        upper = sig_profile.mean + (sigma_multiplier * sig_profile.std)
        
        # Check each value (ignoring NaN)
        series = data[col_name].dropna()
        
        for idx, value in series.items():
            result.add_pass()
            result.total_checks += 1
            
            if value < lower or value > upper:
                result.add_violation(col_name, value, (lower, upper))
    
    # Check features if available
    for col_name, feat_profile in profile.feature_profiles.items():
        if col_name not in data.columns:
            continue
        
        lower = feat_profile.mean - (sigma_multiplier * feat_profile.std)
        upper = feat_profile.mean + (sigma_multiplier * feat_profile.std)
        
        series = data[col_name].dropna()
        
        for idx, value in series.items():
            result.add_pass()
            result.total_checks += 1
            
            if value < lower or value > upper:
                result.add_violation(col_name, value, (lower, upper))
    
    return result


def get_expected_range(
    profile: BaselineProfile,
    column: str,
    sigma_multiplier: float = 3.0
) -> Tuple[float, float]:
    """
    Get expected range for a column based on N-Sigma Rule.
    
    Args:
        profile: BaselineProfile
        column: Column name (signal or feature)
        sigma_multiplier: Number of standard deviations
        
    Returns:
        (lower_bound, upper_bound) tuple
        
    Raises:
        KeyError: If column not in profile
    """
    if column in profile.signal_profiles:
        sig = profile.signal_profiles[column]
    elif column in profile.feature_profiles:
        sig = profile.feature_profiles[column]
    else:
        raise KeyError(f"Column '{column}' not found in profile")
    
    lower = sig.mean - (sigma_multiplier * sig.std)
    upper = sig.mean + (sigma_multiplier * sig.std)
    
    return (lower, upper)
