"""
Baseline Construction — Statistical Profiling for "Normal" Behavior

Learns expected operating ranges from HEALTHY data only.
Profiles are asset-specific and immutable once created.

Constraints:
- Healthy data = is_fault_injected == False
- Ignores NaN values during calculation
- Fails if feature coverage < 80%
- min/max are descriptive (what happened), not prescriptive
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import uuid4

# numpy and pandas are lazy-loaded inside methods to speed up cold start
from pydantic import BaseModel, Field, field_validator


# Minimum valid sample ratio for baseline construction
MIN_COVERAGE_RATIO = 0.80  # 80%


class SignalProfile(BaseModel):
    """Statistical profile for a single signal or feature."""
    mean: float = Field(..., description="Mean value from healthy data")
    std: float = Field(..., ge=0, description="Standard deviation")
    min: float = Field(..., description="Minimum observed value (descriptive)")
    max: float = Field(..., description="Maximum observed value (descriptive)")
    sample_count: int = Field(..., ge=0, description="Number of valid samples used")


class TrainingWindow(BaseModel):
    """Training period metadata."""
    start: datetime
    end: datetime
    sample_count: int = Field(..., ge=0)
    valid_sample_ratio: float = Field(..., ge=0, le=1)


class BaselineProfile(BaseModel):
    """
    Complete baseline profile for an asset.
    
    One asset = one profile. Profiles are immutable once created.
    """
    baseline_id: str = Field(default_factory=lambda: str(uuid4()))
    asset_id: str = Field(..., description="Asset this baseline belongs to")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    training_window: TrainingWindow
    
    signal_profiles: Dict[str, SignalProfile] = Field(
        default_factory=dict,
        description="Profiles for raw signals (voltage_v, current_a, etc.)"
    )
    feature_profiles: Dict[str, SignalProfile] = Field(
        default_factory=dict,
        description="Profiles for derived features"
    )
    
    @field_validator('created_at')
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class BaselineBuildError(Exception):
    """Raised when baseline construction fails."""
    pass


class BaselineBuilder:
    """
    Constructs baseline profiles from healthy sensor data.
    
    Healthy data is strictly defined as: is_fault_injected == False
    """
    
    # Signals to profile
    SIGNAL_COLUMNS = ['voltage_v', 'current_a', 'power_factor', 'vibration_g']
    
    # Features to profile (if available)
    FEATURE_COLUMNS = [
        'voltage_rolling_mean_1h',
        'current_spike_count', 
        'power_factor_efficiency_score',
        'vibration_intensity_rms'
    ]
    
    def __init__(self, min_coverage: float = MIN_COVERAGE_RATIO):
        """
        Initialize baseline builder.
        
        Args:
            min_coverage: Minimum valid sample ratio required (default: 0.80)
        """
        self.min_coverage = min_coverage
    
    def build(
        self,
        data,
        asset_id: str,
        training_window: Optional[tuple] = None
    ) -> BaselineProfile:
        """
        Build baseline profile from healthy data.
        
        Args:
            data: DataFrame with sensor data and optional features
            asset_id: Asset identifier
            training_window: Optional (start, end) datetime tuple to filter data
            
        Returns:
            BaselineProfile with computed statistics
            
        Raises:
            BaselineBuildError: If data is insufficient or invalid
        """
        if data.empty:
            raise BaselineBuildError("Cannot build baseline from empty data")
        
        # Apply training window filter if specified
        if training_window is not None:
            start, end = training_window
            if 'timestamp' in data.columns:
                data = data[(data['timestamp'] >= start) & (data['timestamp'] <= end)]
            elif data.index.name == 'timestamp':
                import pandas as pd
                if isinstance(data.index, pd.DatetimeIndex):
                    data = data[(data.index >= start) & (data.index <= end)]
        
        # Filter to HEALTHY data only (is_fault_injected == False)
        data = self._filter_healthy_data(data)
        
        if data.empty:
            raise BaselineBuildError("No healthy data available after filtering")
        
        # Determine training window from data
        window_start, window_end = self._get_time_range(data)
        
        # Build signal profiles
        signal_profiles = {}
        for col in self.SIGNAL_COLUMNS:
            if col in data.columns:
                profile = self._compute_profile(data, col)
                if profile is not None:
                    signal_profiles[col] = profile
        
        if not signal_profiles:
            raise BaselineBuildError("No valid signal profiles could be computed")
        
        # Build feature profiles (optional)
        feature_profiles = {}
        for col in self.FEATURE_COLUMNS:
            if col in data.columns:
                profile = self._compute_profile(data, col)
                if profile is not None:
                    feature_profiles[col] = profile
        
        # Create training window metadata
        total_samples = len(data)
        valid_samples = sum(
            data[col].notna().sum() for col in signal_profiles.keys()
        ) / len(signal_profiles)
        valid_ratio = valid_samples / total_samples if total_samples > 0 else 0
        
        training_meta = TrainingWindow(
            start=window_start,
            end=window_end,
            sample_count=total_samples,
            valid_sample_ratio=round(valid_ratio, 4)
        )
        
        return BaselineProfile(
            asset_id=asset_id,
            training_window=training_meta,
            signal_profiles=signal_profiles,
            feature_profiles=feature_profiles
        )
    
    def _filter_healthy_data(self, data):
        """
        Filter to healthy data only (is_fault_injected == False).
        
        If is_fault_injected column doesn't exist, assumes all data is healthy.
        """
        if 'is_fault_injected' in data.columns:
            return data[data['is_fault_injected'] == False].copy()
        return data.copy()
    
    def _get_time_range(self, data) -> tuple:
        """Get start and end timestamps from data."""
        import pandas as pd
        if isinstance(data.index, pd.DatetimeIndex):
            return data.index.min(), data.index.max()
        elif 'timestamp' in data.columns:
            return data['timestamp'].min(), data['timestamp'].max()
        else:
            # Fallback to current time
            now = datetime.now(timezone.utc)
            return now, now
    
    def _compute_profile(
        self,
        data,
        column: str
    ) -> Optional[SignalProfile]:
        """
        Compute statistical profile for a column.
        
        Ignores NaN values. Fails if coverage < min_coverage.
        """
        if column not in data.columns:
            return None
        
        series = data[column]
        total_count = len(series)
        valid_count = series.notna().sum()
        
        # Check coverage
        if total_count == 0:
            return None
        
        coverage = valid_count / total_count
        if coverage < self.min_coverage:
            raise BaselineBuildError(
                f"Insufficient coverage for '{column}': {coverage:.1%} < {self.min_coverage:.0%} required"
            )
        
        # Compute statistics (ignoring NaN)
        valid_data = series.dropna()
        
        return SignalProfile(
            mean=round(float(valid_data.mean()), 6),
            std=round(float(valid_data.std()), 6),
            min=round(float(valid_data.min()), 6),
            max=round(float(valid_data.max()), 6),
            sample_count=int(valid_count)
        )


def save_baseline(profile: BaselineProfile, directory: str = "backend/models") -> Path:
    """
    Save baseline profile to JSON file.
    
    File naming: baseline_{asset_id}_{baseline_id}.json
    
    Args:
        profile: BaselineProfile to save
        directory: Target directory (default: backend/models)
        
    Returns:
        Path to saved file
    """
    dir_path = Path(directory)
    dir_path.mkdir(parents=True, exist_ok=True)
    
    filename = f"baseline_{profile.asset_id}_{profile.baseline_id[:8]}.json"
    filepath = dir_path / filename
    
    with open(filepath, 'w') as f:
        json.dump(profile.model_dump(mode='json'), f, indent=2, default=str)
    
    return filepath


def load_baseline(filepath: str) -> BaselineProfile:
    """
    Load baseline profile from JSON file.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        BaselineProfile instance
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    return BaselineProfile.model_validate(data)
