"""Debug write-then-read in same connection."""
from datetime import datetime, timezone
from uuid import uuid4
import time

from backend.storage import SensorEventWriter
from backend.storage.config import load_config, MEASUREMENT_NAME

def main():
    config = load_config()
    client = SensorEventWriter()
    client.connect()
    
    test_asset_id = f"debug-{uuid4().hex[:8]}"
    print(f"Writing event with asset_id={test_asset_id}")
    
    event = {
        "event_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc),
        "asset": {"asset_id": test_asset_id, "asset_type": "induction_motor"},
        "signals": {"voltage_v": 230.0, "current_a": 15.0, "power_factor": 0.85, "power_kw": 2.9, "vibration_g": 0.15},
        "context": {"operating_state": "RUNNING", "source": "simulator"}
    }
    
    try:
        client.write_sensor_event(event)
        print("Write succeeded")
    except Exception as e:
        print(f"Write FAILED: {e}")
        client.disconnect()
        return
    
    print("Waiting 3s...")
    time.sleep(3)
    
    # Query ALL data (no filter)
    print("\nQuerying ALL data - no filter:")
    results_all = client.query_latest_events(limit=10)
    print(f"  Results: {len(results_all)}")
    
    # Query with filter
    print(f"\nQuerying with asset_id={test_asset_id}:")
    results_filtered = client.query_latest_events(asset_id=test_asset_id, limit=5)
    print(f"  Results: {len(results_filtered)}")
    if results_filtered:
        print(f"  First record: {results_filtered[0]}")
    
    client.disconnect()

if __name__ == "__main__":
    main()
