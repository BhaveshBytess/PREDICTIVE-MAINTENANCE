#!/usr/bin/env python
"""
Data Generator — Synthetic Sensor Data Simulator

Generates realistic sensor data and POSTs to the /ingest endpoint.
Supports healthy and faulty data modes for testing.

Usage:
    python scripts/generate_data.py --asset_id motor_01 --duration 60 --healthy
    python scripts/generate_data.py --asset_id motor_01 --duration 10 --faulty
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
import uuid
import random
from datetime import datetime, timezone

import requests


# API Configuration
API_BASE_URL = os.environ.get("API_URL", "http://localhost:8000")
INGEST_ENDPOINT = f"{API_BASE_URL}/api/v1/data/simple"


def generate_healthy_reading():
    """Generate normal operating sensor values."""
    return {
        "voltage_v": round(random.gauss(230, 3), 2),      # 230V +/- 3V
        "current_a": round(random.gauss(15, 1), 2),       # 15A +/- 1A
        "power_factor": round(random.uniform(0.88, 0.95), 3),  # Good PF
        "vibration_g": round(random.gauss(0.15, 0.02), 4) # Low vibration
    }


def generate_faulty_reading(fault_type=None):
    """Generate EXTREME anomalous sensor values to force CRITICAL state."""
    if fault_type is None:
        fault_type = random.choice(["voltage_spike", "vibration_drift", "pf_drop", "catastrophic"])
    
    reading = generate_healthy_reading()
    
    if fault_type == "voltage_spike":
        # MASSIVE voltage surge - way beyond normal
        reading["voltage_v"] = round(random.gauss(320, 20), 2)  # +90V from normal!
        
    elif fault_type == "vibration_drift":
        # EXTREME vibration - machine shaking apart
        reading["vibration_g"] = round(random.gauss(3.0, 0.5), 4)  # 20x normal!
        
    elif fault_type == "pf_drop":
        # SEVERE power factor degradation
        reading["power_factor"] = round(random.uniform(0.35, 0.50), 3)  # Way below acceptable
        
    elif fault_type == "catastrophic":
        # EVERYTHING fails at once - total system failure
        reading["voltage_v"] = round(random.gauss(310, 25), 2)
        reading["vibration_g"] = round(random.gauss(5.0, 1.0), 4)
        reading["power_factor"] = round(random.uniform(0.30, 0.45), 3)
        reading["current_a"] = round(random.gauss(35, 5), 2)  # Overcurrent!
    
    return reading


def send_event(asset_id: str, sensor_data: dict, is_faulty: bool = False) -> bool:
    """Send a single sensor event to the ingest endpoint."""
    event_id = str(uuid.uuid4())
    
    # Use simple flat structure for demo endpoint
    payload = {
        "asset_id": asset_id,
        "voltage_v": sensor_data["voltage_v"],
        "current_a": sensor_data["current_a"],
        "power_factor": sensor_data["power_factor"],
        "vibration_g": sensor_data["vibration_g"],
        "is_faulty": is_faulty
    }
    
    try:
        response = requests.post(INGEST_ENDPOINT, json=payload, timeout=5)
        
        if response.status_code == 200 or response.status_code == 201:
            print(f"[OK] Sent event {event_id[:8]}... | "
                  f"V={sensor_data['voltage_v']:.1f}V, "
                  f"I={sensor_data['current_a']:.1f}A, "
                  f"PF={sensor_data['power_factor']:.2f}, "
                  f"Vib={sensor_data['vibration_g']:.3f}g"
                  f"{' [FAULT]' if is_faulty else ''}")
            return True
        else:
            print(f"[ERROR] HTTP {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Cannot connect to {INGEST_ENDPOINT}")
        print("       Make sure the backend is running: uvicorn backend.api.main:app")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def run_generator(asset_id: str, duration: int, interval: float, faulty: bool):
    """Run the data generator for specified duration."""
    print("=" * 60)
    print("PREDICTIVE MAINTENANCE - DATA GENERATOR")
    print("=" * 60)
    print(f"Asset ID:   {asset_id}")
    print(f"Duration:   {duration} seconds")
    print(f"Interval:   {interval} seconds")
    print(f"Mode:       {'FAULTY (injecting anomalies)' if faulty else 'HEALTHY (normal operation)'}")
    print(f"Endpoint:   {INGEST_ENDPOINT}")
    print("=" * 60)
    print()
    
    start_time = time.time()
    events_sent = 0
    events_failed = 0
    
    try:
        while (time.time() - start_time) < duration:
            # Generate reading based on mode
            if faulty:
                sensor_data = generate_faulty_reading()
            else:
                sensor_data = generate_healthy_reading()
            
            # Send to API
            if send_event(asset_id, sensor_data, is_faulty=faulty):
                events_sent += 1
            else:
                events_failed += 1
            
            # Wait for next interval
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n[STOPPED] Generator interrupted by user")
    
    print()
    print("=" * 60)
    print(f"[COMPLETE] Sent {events_sent} events, {events_failed} failed")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic sensor data for Predictive Maintenance"
    )
    parser.add_argument(
        "--asset_id", "-a",
        type=str,
        default="Motor-01",
        help="Asset identifier (default: Motor-01)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=60,
        help="Duration in seconds (default: 60)"
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=1.0,
        help="Interval between events in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--faulty", "-f",
        action="store_true",
        help="Generate faulty/anomalous data instead of healthy"
    )
    parser.add_argument(
        "--healthy",
        action="store_true",
        help="Generate healthy data (default)"
    )
    
    args = parser.parse_args()
    
    # --healthy overrides --faulty for explicit clarity
    is_faulty = args.faulty and not args.healthy
    
    run_generator(
        asset_id=args.asset_id,
        duration=args.duration,
        interval=args.interval,
        faulty=is_faulty
    )


if __name__ == "__main__":
    main()
