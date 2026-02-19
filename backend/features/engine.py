"""
Feature Engine — Feature Extraction Orchestrator

Stateless, idempotent feature extraction.
Fetches historical data from InfluxDB and computes features.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import pandas as pd

from backend.storage import SensorEventWriter

from .calculator import compute_all_features
from .schemas import FeatureRecord, DerivedFeatures


class FeatureEngine:
    """
    Stateless feature extraction engine.
    
    Computes features for a given asset at a specific evaluation timestamp.
    All operations are idempotent - same inputs always produce same outputs.
    """
    
    def __init__(self, storage_client: Optional[SensorEventWriter] = None):
        """
        Initialize the feature engine.
        
        Args:
            storage_client: Optional pre-connected storage client.
                          If None, creates new connection per operation.
        """
        self._client = storage_client
        self._owns_client = storage_client is None
    
    def _get_client(self) -> SensorEventWriter:
        """Get or create storage client."""
        if self._client is None:
            client = SensorEventWriter()
            client.connect()
            return client
        return self._client
    
    def _release_client(self, client: SensorEventWriter) -> None:
        """Release client if we created it."""
        if self._owns_client and client is not None:
            client.disconnect()
    
    def compute_features(
        self,
        asset_id: str,
        evaluation_timestamp: datetime,
        lookback_hours: int = 2
    ) -> FeatureRecord:
        """
        Compute all features for an asset at a specific timestamp.
        
        Args:
            asset_id: Asset to compute features for
            evaluation_timestamp: The "right now" timestamp to evaluate at
            lookback_hours: Hours of historical data to fetch (default: 2)
            
        Returns:
            FeatureRecord with computed features
            
        Note:
            - timestamp in the result is the EVALUATION timestamp
            - Features use past-only windowing
            - NaN (None) is returned for incomplete windows
        """
        client = self._get_client()
        
        try:
            # Fetch historical data
            df = self._fetch_historical_data(
                client,
                asset_id,
                evaluation_timestamp,
                lookback_hours
            )
            
            # Find evaluation point index
            if df.empty:
                # No data at all - return all NaN
                return self._create_empty_record(asset_id, evaluation_timestamp)
            
            # Get index of evaluation point (or closest prior point)
            evaluation_idx = self._find_evaluation_index(df, evaluation_timestamp)
            
            if evaluation_idx is None or evaluation_idx < 0:
                return self._create_empty_record(asset_id, evaluation_timestamp)
            
            # Get power factor at evaluation point
            current_pf = df.iloc[evaluation_idx].get('power_factor', 0.0)
            
            # Compute all features
            features = compute_all_features(df, evaluation_idx, current_pf)
            
            return FeatureRecord(
                feature_id=str(uuid4()),
                asset_id=asset_id,
                timestamp=evaluation_timestamp,
                features=DerivedFeatures(**features)
            )
            
        finally:
            self._release_client(client)
    
    def _fetch_historical_data(
        self,
        client: SensorEventWriter,
        asset_id: str,
        end_time: datetime,
        lookback_hours: int
    ) -> pd.DataFrame:
        """
        Fetch historical sensor data from InfluxDB.
        
        Returns DataFrame with timestamp index and signal columns.
        """
        # Query recent events
        # Note: query_latest_events returns most recent first
        results = client.query_latest_events(
            asset_id=asset_id,
            limit=lookback_hours * 60  # Approximate points
        )
        
        if not results:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(results)
        
        # Set timestamp as index
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True)
            df = df.set_index('timestamp')
            df = df.sort_index()  # Ensure chronological order
        
        return df
    
    def _find_evaluation_index(
        self,
        df: pd.DataFrame,
        evaluation_timestamp: datetime
    ) -> Optional[int]:
        """Find the index of the evaluation point in the DataFrame."""
        if df.empty:
            return None
        
        # Make sure evaluation_timestamp is timezone-aware
        if evaluation_timestamp.tzinfo is None:
            evaluation_timestamp = evaluation_timestamp.replace(tzinfo=timezone.utc)
        
        # Find closest point at or before evaluation timestamp
        mask = df.index <= evaluation_timestamp
        valid_indices = df.index[mask]
        
        if len(valid_indices) == 0:
            return None
        
        # Return position of the last valid point
        return len(valid_indices) - 1
    
    def _create_empty_record(
        self,
        asset_id: str,
        evaluation_timestamp: datetime
    ) -> FeatureRecord:
        """Create a FeatureRecord with all NaN values."""
        return FeatureRecord(
            feature_id=str(uuid4()),
            asset_id=asset_id,
            timestamp=evaluation_timestamp,
            features=DerivedFeatures(
                voltage_rolling_mean_1h=None,
                current_spike_count=None,
                power_factor_efficiency_score=None,
                vibration_intensity_rms=None
            )
        )
