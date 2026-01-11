"""
API Services — Business Logic Layer

Handles derived signal computation and storage orchestration.
"""

from datetime import datetime
from typing import Dict, Any

from backend.storage import SensorEventWriter, InfluxDBClientError


def compute_power_kw(voltage_v: float, current_a: float, power_factor: float) -> float:
    """
    Compute power in kilowatts.
    
    Formula: P(kW) = (V × I × PF) / 1000
    
    This is computed SERVER-SIDE only to prevent client-side data corruption.
    Per CONTRACTS.md and user mandate.
    
    Args:
        voltage_v: Voltage in Volts
        current_a: Current in Amperes  
        power_factor: Power factor (0.0-1.0)
        
    Returns:
        Power in kilowatts, rounded to 3 decimal places
    """
    power_kw = (voltage_v * current_a * power_factor) / 1000.0
    return round(power_kw, 3)


async def ingest_event(
    event_id: str,
    timestamp: datetime,
    asset: Dict[str, str],
    signals: Dict[str, float],
    context: Dict[str, str],
    client: SensorEventWriter
) -> Dict[str, Any]:
    """
    Orchestrate event ingestion: compute derived signals and persist.
    
    Args:
        event_id: UUID v4 event identifier
        timestamp: UTC timestamp
        asset: Asset identification dict
        signals: Raw signal values (without power_kw)
        context: Operating context
        client: Connected InfluxDB client
        
    Returns:
        Complete event dict with computed power_kw
        
    Raises:
        InfluxDBClientError: If storage fails
    """
    # Compute derived signal
    power_kw = compute_power_kw(
        voltage_v=signals["voltage_v"],
        current_a=signals["current_a"],
        power_factor=signals["power_factor"]
    )
    
    # Build complete event for storage
    complete_event = {
        "event_id": event_id,
        "timestamp": timestamp,
        "asset": asset,
        "signals": {
            "voltage_v": signals["voltage_v"],
            "current_a": signals["current_a"],
            "power_factor": signals["power_factor"],
            "power_kw": power_kw,
            "vibration_g": signals["vibration_g"]
        },
        "context": context
    }
    
    # Persist to InfluxDB
    client.write_sensor_event(complete_event)
    
    return complete_event


async def check_database_health(client: SensorEventWriter) -> bool:
    """
    Check if InfluxDB is reachable.
    
    Args:
        client: InfluxDB client instance
        
    Returns:
        True if database is healthy, False otherwise
    """
    try:
        return client.health_check()
    except Exception:
        return False
