"""
Batch Feature Retraining Script — Phase 5

Pulls historical 100Hz data from InfluxDB, extracts batch features from
1-second windows, and trains a new IsolationForest + StandardScaler.

Usage:
    python -m scripts.retrain_batch_model --asset Motor-01 --seconds 300

The script can also be imported and called programmatically:
    from scripts.retrain_batch_model import retrain_batch_model
    detector = retrain_batch_model("Motor-01", range_seconds=300)
"""

import argparse
import sys
import os
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import db
from backend.ml.batch_features import extract_multi_window_features, BATCH_FEATURE_NAMES
from backend.ml.batch_detector import BatchAnomalyDetector


def fetch_raw_100hz_data(asset_id: str, range_seconds: int = 300, healthy_only: bool = True):
    """
    Fetch raw 100Hz data from InfluxDB WITHOUT server-side aggregation.
    
    Args:
        asset_id: Asset identifier.
        range_seconds: How many seconds of history to pull.
        healthy_only: If True, filter to is_faulty == false only.
    
    Returns:
        List of dicts with voltage_v, current_a, power_factor, vibration_g.
    """
    # Build Flux query — NO aggregateWindow, get raw 100Hz points
    fault_filter = ""
    if healthy_only:
        fault_filter = '  |> filter(fn: (r) => r["is_faulty"] == false or r["is_faulty"] == 0 or r["is_faulty"] == 0.0)\n'
    
    flux_query = f'''
from(bucket: "{db._bucket}")
  |> range(start: -{range_seconds}s)
  |> filter(fn: (r) => r["_measurement"] == "sensor_events")
  |> filter(fn: (r) => r["asset_id"] == "{asset_id}")
{fault_filter}  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: false)
'''
    
    print(f"[Retrain] Querying {range_seconds}s of raw 100Hz data for {asset_id}...")
    
    if db.is_mock_mode:
        print("[Retrain] WARNING: InfluxDB in mock mode — using mock buffer")
        results = []
        for p in db.get_mock_buffer():
            if p.get("tags", {}).get("asset_id") == asset_id:
                fields = p.get("fields", {})
                is_f = fields.get("is_faulty", False)
                if healthy_only and is_f:
                    continue
                results.append({
                    "voltage_v": fields.get("voltage_v", 230.0),
                    "current_a": fields.get("current_a", 15.0),
                    "power_factor": fields.get("power_factor", 0.92),
                    "vibration_g": fields.get("vibration_g", 0.15),
                })
        return results
    
    try:
        query_api = db._client.query_api()
        tables = query_api.query(flux_query, org=db._org)
        
        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "voltage_v": record.values.get("voltage_v", 0.0),
                    "current_a": record.values.get("current_a", 0.0),
                    "power_factor": record.values.get("power_factor", 0.0),
                    "vibration_g": record.values.get("vibration_g", 0.0),
                })
        
        print(f"[Retrain] Fetched {len(results)} raw points")
        return results
        
    except Exception as e:
        print(f"[Retrain] ERROR fetching data: {e}")
        return []


def retrain_batch_model(
    asset_id: str = "Motor-01",
    range_seconds: int = 300,
    window_size: int = 100,
    save_dir: str = "backend/models",
) -> BatchAnomalyDetector:
    """
    Full retraining pipeline:
    1. Fetch raw 100Hz healthy data from InfluxDB
    2. Slice into 1-second windows of `window_size` points
    3. Extract 16-D batch feature vectors
    4. Train BatchAnomalyDetector
    5. Save model to disk
    
    Returns the trained detector.
    """
    # Step 1: Fetch raw data
    raw_points = fetch_raw_100hz_data(asset_id, range_seconds, healthy_only=True)
    
    if len(raw_points) < window_size:
        raise ValueError(
            f"Insufficient raw data: got {len(raw_points)} points, "
            f"need at least {window_size} (1 window)"
        )
    
    print(f"[Retrain] {len(raw_points)} raw points → "
          f"~{len(raw_points) // window_size} windows of {window_size}")
    
    # Step 2-3: Extract batch features from 1-second windows
    feature_rows = extract_multi_window_features(raw_points, window_size=window_size)
    
    if len(feature_rows) < 10:
        raise ValueError(
            f"Only {len(feature_rows)} valid feature windows. Need >= 10 for training."
        )
    
    print(f"[Retrain] Extracted {len(feature_rows)} feature vectors "
          f"({len(BATCH_FEATURE_NAMES)} features each)")
    
    # Step 4: Train
    detector = BatchAnomalyDetector(asset_id=asset_id)
    detector.train(feature_rows)
    
    print(f"[Retrain] Model trained successfully on {len(feature_rows)} windows")
    
    # Step 5: Save
    filepath = detector.save(save_dir)
    print(f"[Retrain] Model saved to {filepath}")
    
    return detector


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrain batch feature model")
    parser.add_argument("--asset", default="Motor-01", help="Asset ID")
    parser.add_argument("--seconds", type=int, default=300, help="Seconds of history to use")
    parser.add_argument("--window", type=int, default=100, help="Points per window (100Hz = 100)")
    parser.add_argument("--save-dir", default="backend/models", help="Directory to save model")
    
    args = parser.parse_args()
    
    try:
        detector = retrain_batch_model(
            asset_id=args.asset,
            range_seconds=args.seconds,
            window_size=args.window,
            save_dir=args.save_dir,
        )
        print(f"\n✅ Retraining complete. Model version: v3 (batch features)")
        print(f"   Asset: {args.asset}")
        print(f"   Features: {len(BATCH_FEATURE_NAMES)}")
        print(f"   Training windows: {detector._training_sample_count}")
    except Exception as e:
        print(f"\n❌ Retraining failed: {e}")
        sys.exit(1)
