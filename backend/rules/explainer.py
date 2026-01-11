"""
Explainability Engine — Surface Understandable Reasoning

Generates human-readable explanations for anomaly detection results.
"Why is risk high?" -> "Vibration at 0.45g exceeds baseline (0.15g)"

Constraints:
- Handle std=0 (no division by zero)
- Epsilon rule: ignore tiny absolute differences (<1% of mean)
- Fixed string templates (no free-form generation)
- Explanations include observed value AND baseline reference
- Top 3 contributors only
- Only generate for MODERATE/HIGH/CRITICAL (not LOW)
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum

from backend.ml.baseline import BaselineProfile, SignalProfile
from backend.rules.assessor import RiskLevel, Explanation


# ============================================================================
# CONSTANTS
# ============================================================================

# Minimum relative difference to consider significant (1% of mean)
EPSILON_RELATIVE = 0.01

# Maximum number of explanations to return
MAX_EXPLANATIONS = 3

# Z-score threshold for "significant" deviation
ZSCORE_THRESHOLD = 2.0


# ============================================================================
# Explanation Templates (Fixed, No Free-Form)
# ============================================================================

class ExplanationTemplate(str, Enum):
    """Fixed string templates for explanations."""
    
    HIGH_VALUE = "{feature} value ({value:.2f}) is {deviation:.1f}σ above normal (baseline: {baseline_mean:.2f})"
    LOW_VALUE = "{feature} value ({value:.2f}) is {deviation:.1f}σ below normal (baseline: {baseline_mean:.2f})"
    EXCEEDS_MAX = "{feature} value ({value:.2f}) exceeds observed maximum ({baseline_max:.2f})"
    BELOW_MIN = "{feature} value ({value:.2f}) below observed minimum ({baseline_min:.2f})"
    SYSTEMS_NOMINAL = "All systems operating within normal parameters"


# ============================================================================
# Feature Contribution
# ============================================================================

@dataclass
class FeatureContribution:
    """Contribution of a feature to anomaly detection."""
    feature_name: str
    observed_value: float
    baseline_mean: float
    baseline_std: float
    baseline_min: float
    baseline_max: float
    zscore: float  # Signed z-score (+ = above, - = below)
    absolute_deviation: float  # |observed - mean|
    is_significant: bool  # Passes epsilon rule


# ============================================================================
# Explanation Generator
# ============================================================================

class ExplanationGenerator:
    """
    Generates human-readable explanations for anomaly alerts.
    
    Uses fixed templates with actual data values.
    Only generates for MODERATE/HIGH/CRITICAL risk levels.
    """
    
    # Human-readable feature names
    FEATURE_NAMES = {
        'voltage_v': 'Voltage',
        'current_a': 'Current',
        'power_factor': 'Power Factor',
        'vibration_g': 'Vibration',
        'voltage_rolling_mean_1h': 'Avg Voltage (1h)',
        'current_spike_count': 'Current Spikes',
        'power_factor_efficiency_score': 'PF Efficiency',
        'vibration_intensity_rms': 'Vibration RMS',
    }
    
    def __init__(self, baseline: Optional[BaselineProfile] = None):
        """
        Initialize generator with baseline profile.
        
        Args:
            baseline: Optional baseline profile for comparison
        """
        self.baseline = baseline
    
    def analyze_contributions(
        self,
        features: Dict[str, float],
        baseline: Optional[BaselineProfile] = None
    ) -> List[FeatureContribution]:
        """
        Analyze feature contributions to anomaly.
        
        Args:
            features: Dict of feature name -> observed value
            baseline: Baseline profile (or use stored)
            
        Returns:
            List of FeatureContribution, sorted by |zscore| descending
        """
        profile = baseline or self.baseline
        if profile is None:
            return []
        
        contributions = []
        
        # Combine signal and feature profiles
        all_profiles = {
            **profile.signal_profiles,
            **profile.feature_profiles
        }
        
        for feature_name, value in features.items():
            if feature_name not in all_profiles:
                continue
            
            if value is None:
                continue
            
            sig = all_profiles[feature_name]
            
            # Calculate contribution
            contrib = self._calculate_contribution(feature_name, value, sig)
            if contrib is not None:
                contributions.append(contrib)
        
        # Sort by absolute z-score (most significant first)
        contributions.sort(key=lambda c: abs(c.zscore), reverse=True)
        
        return contributions
    
    def _calculate_contribution(
        self,
        feature_name: str,
        value: float,
        profile: SignalProfile
    ) -> Optional[FeatureContribution]:
        """
        Calculate contribution for a single feature.
        
        Handles:
        - Division by zero (std=0)
        - Epsilon rule (tiny absolute differences)
        """
        deviation = value - profile.mean
        absolute_deviation = abs(deviation)
        
        # Handle std=0: treat as no statistical deviation
        if profile.std == 0 or profile.std is None:
            zscore = 0.0
        else:
            zscore = deviation / profile.std
        
        # Epsilon rule: ignore if absolute diff < 1% of mean
        is_significant = True
        if profile.mean != 0:
            relative_diff = absolute_deviation / abs(profile.mean)
            if relative_diff < EPSILON_RELATIVE:
                is_significant = False
        
        return FeatureContribution(
            feature_name=feature_name,
            observed_value=value,
            baseline_mean=profile.mean,
            baseline_std=profile.std,
            baseline_min=profile.min,
            baseline_max=profile.max,
            zscore=zscore,
            absolute_deviation=absolute_deviation,
            is_significant=is_significant
        )
    
    def generate(
        self,
        features: Dict[str, float],
        risk_level: RiskLevel,
        baseline: Optional[BaselineProfile] = None
    ) -> List[Explanation]:
        """
        Generate explanations for current risk level.
        
        Args:
            features: Current feature values
            risk_level: Current risk classification
            baseline: Baseline profile (or use stored)
            
        Returns:
            List of Explanation objects (empty for LOW risk)
        """
        # Only generate for MODERATE/HIGH/CRITICAL
        if risk_level == RiskLevel.LOW:
            return []
        
        # Analyze contributions
        contributions = self.analyze_contributions(features, baseline)
        
        # Filter to significant only
        significant = [c for c in contributions if c.is_significant]
        
        # Take top 3
        top_contributors = significant[:MAX_EXPLANATIONS]
        
        # Generate explanations using templates
        explanations = []
        for contrib in top_contributors:
            explanation = self._generate_single(contrib)
            if explanation:
                explanations.append(explanation)
        
        return explanations
    
    def _generate_single(self, contrib: FeatureContribution) -> Optional[Explanation]:
        """Generate explanation for a single feature contribution."""
        
        # Get human-readable name
        display_name = self.FEATURE_NAMES.get(
            contrib.feature_name, 
            contrib.feature_name.replace('_', ' ').title()
        )
        
        # Choose template based on deviation
        if contrib.observed_value > contrib.baseline_max:
            # Exceeds observed maximum
            reason = ExplanationTemplate.EXCEEDS_MAX.value.format(
                feature=display_name,
                value=contrib.observed_value,
                baseline_max=contrib.baseline_max
            )
        elif contrib.observed_value < contrib.baseline_min:
            # Below observed minimum
            reason = ExplanationTemplate.BELOW_MIN.value.format(
                feature=display_name,
                value=contrib.observed_value,
                baseline_min=contrib.baseline_min
            )
        elif contrib.zscore > ZSCORE_THRESHOLD:
            # Above normal
            reason = ExplanationTemplate.HIGH_VALUE.value.format(
                feature=display_name,
                value=contrib.observed_value,
                deviation=abs(contrib.zscore),
                baseline_mean=contrib.baseline_mean
            )
        elif contrib.zscore < -ZSCORE_THRESHOLD:
            # Below normal
            reason = ExplanationTemplate.LOW_VALUE.value.format(
                feature=display_name,
                value=contrib.observed_value,
                deviation=abs(contrib.zscore),
                baseline_mean=contrib.baseline_mean
            )
        else:
            # Not significant enough for explanation
            return None
        
        # Calculate confidence based on z-score magnitude
        confidence = min(0.99, 0.5 + abs(contrib.zscore) * 0.1)
        
        return Explanation(
            reason=reason,
            related_features=[contrib.feature_name],
            confidence_score=round(confidence, 2)
        )
    
    def generate_nominal(self) -> Explanation:
        """Generate 'systems nominal' explanation for LOW risk."""
        return Explanation(
            reason=ExplanationTemplate.SYSTEMS_NOMINAL.value,
            related_features=[],
            confidence_score=1.0
        )
