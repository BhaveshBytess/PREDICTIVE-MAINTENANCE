"""
InfluxDB Configuration — Environment-Driven Settings

Loads configuration from environment variables for secure credential management.
Defaults are for development; production should use proper secrets management.

CONTRACTS.md Reference: Section 3 - Time semantics (UTC only)
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class InfluxDBConfig:
    """
    InfluxDB connection configuration.
    
    All values are loaded from environment variables with development defaults.
    """
    host: str
    port: int
    org: str
    bucket: str
    token: str
    retention: str
    
    @property
    def url(self) -> str:
        """Full InfluxDB URL."""
        return f"http://{self.host}:{self.port}"


def load_config() -> InfluxDBConfig:
    """
    Load InfluxDB configuration from environment variables.
    
    Environment Variables:
        INFLUXDB_HOST: InfluxDB hostname (default: localhost)
        INFLUXDB_PORT: InfluxDB port (default: 8086)
        INFLUXDB_ORG: Organization name (default: predictive-maintenance)
        INFLUXDB_BUCKET: Bucket name (default: sensor_data)
        INFLUXDB_TOKEN: Authentication token (required in production)
        INFLUXDB_RETENTION: Data retention period (default: 30d)
    
    Returns:
        InfluxDBConfig instance with loaded values
    """
    return InfluxDBConfig(
        host=os.getenv("INFLUXDB_HOST", "localhost"),
        port=int(os.getenv("INFLUXDB_PORT", "8086")),
        org=os.getenv("INFLUXDB_ORG", "predictive-maintenance"),
        bucket=os.getenv("INFLUXDB_BUCKET", "sensor_data"),
        token=os.getenv("INFLUXDB_TOKEN", "predictive-maintenance-dev-token"),
        retention=os.getenv("INFLUXDB_RETENTION", "30d"),
    )


# Measurement schema constants (mirrors CONTRACTS.md)
# These define HOW data maps to InfluxDB, not WHAT it means

MEASUREMENT_NAME = "sensor_events"

# Tags: Low-cardinality identity fields ONLY
# Per guardrails: asset_id and operating_state
TAGS = ["asset_id", "asset_type", "operating_state"]

# Fields: All numeric signals + high-cardinality identifiers
# Per guardrails: event_id as string Field (not Tag)
FIELDS = [
    "event_id",      # String field (high cardinality - NOT a tag)
    "voltage_v",     # Float
    "current_a",     # Float
    "power_factor",  # Float
    "power_kw",      # Float
    "vibration_g",   # Float
]
