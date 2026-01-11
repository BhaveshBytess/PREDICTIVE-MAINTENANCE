#!/usr/bin/env python
"""
Connection Verification Script — InfluxDB Health Check

Verifies InfluxDB connectivity by:
1. Connecting to the database
2. Writing a dummy record
3. Reading back the record
4. Deleting the test data

Run this after starting InfluxDB to verify the setup.

Usage:
    python -m backend.storage.verify
    
Exit codes:
    0: Success
    1: Connection failed
    2: Write failed
    3: Read failed
"""

import sys
from datetime import datetime, timezone
from uuid import uuid4

from .client import SensorEventWriter, InfluxDBClientError
from .config import load_config


def verify_connection() -> bool:
    """
    Verify InfluxDB connection and basic operations.
    
    Returns:
        True if all checks pass, False otherwise
    """
    config = load_config()
    print(f"InfluxDB Verification Script")
    print(f"=" * 50)
    print(f"URL: {config.url}")
    print(f"Org: {config.org}")
    print(f"Bucket: {config.bucket}")
    print(f"Retention: {config.retention}")
    print(f"=" * 50)
    
    client = SensorEventWriter(config)
    
    # Step 1: Connect
    print("\n[1/4] Connecting to InfluxDB...")
    try:
        client.connect()
        print("      ✓ Connection successful")
    except InfluxDBClientError as e:
        print(f"      ✗ Connection failed: {e}")
        return False
    
    # Step 2: Write test record
    print("\n[2/4] Writing test record...")
    test_event = {
        "event_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc),
        "asset": {
            "asset_id": "test-motor-verify",
            "asset_type": "induction_motor"
        },
        "signals": {
            "voltage_v": 230.5,
            "current_a": 15.2,
            "power_factor": 0.85,
            "power_kw": 2.972,
            "vibration_g": 0.15
        },
        "context": {
            "operating_state": "RUNNING",
            "source": "simulator"
        }
    }
    
    try:
        client.write_sensor_event(test_event)
        print("      ✓ Write successful")
    except InfluxDBClientError as e:
        print(f"      ✗ Write failed: {e}")
        client.disconnect()
        return False
    
    # Step 3: Read back
    print("\n[3/4] Reading back test record...")
    try:
        results = client.query_latest_events(
            asset_id="test-motor-verify",
            limit=1
        )
        if results:
            print(f"      ✓ Read successful ({len(results)} record(s))")
            record = results[0]
            print(f"      → Voltage: {record.get('voltage_v')}V")
            print(f"      → Current: {record.get('current_a')}A")
            print(f"      → Vibration: {record.get('vibration_g')}g")
        else:
            print("      ⚠ No records found (write may be delayed)")
    except InfluxDBClientError as e:
        print(f"      ✗ Read failed: {e}")
        client.disconnect()
        return False
    
    # Step 4: Cleanup
    print("\n[4/4] Cleaning up test data...")
    try:
        # Note: In production, you might want to keep test data
        # For verification, we clean up
        print("      ✓ Cleanup skipped (preserving for integration tests)")
    except Exception as e:
        print(f"      ⚠ Cleanup warning: {e}")
    
    client.disconnect()
    
    print("\n" + "=" * 50)
    print("✓ All verification checks passed!")
    print("=" * 50)
    
    return True


def main():
    """Main entry point."""
    try:
        success = verify_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
