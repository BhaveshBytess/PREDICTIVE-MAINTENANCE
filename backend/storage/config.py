"""
InfluxDB Configuration — Environment-Driven Settings

Loads configuration from environment variables for secure credential management.
Supports both local InfluxDB (host:port) and InfluxDB Cloud (full URL).

CONTRACTS.md Reference: Section 3 - Time semantics (UTC only)
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class InfluxDBConfig:
    """
    InfluxDB connection configuration.
    
    Supports two modes:
    1. Local: Uses host + port (e.g., localhost:8086)
    2. Cloud: Uses full URL (e.g., https://us-east-1-1.aws.cloud2.influxdata.com)
    
    Set INFLUXDB_URL for cloud, or INFLUXDB_HOST + INFLUXDB_PORT for local.
    """
    url: str
    org: str
    bucket: str
    token: str
    retention: str


def load_config() -> InfluxDBConfig:
    """
    Load InfluxDB configuration from environment variables.
    
    Environment Variables:
        INFLUXDB_URL: Full InfluxDB URL (for Cloud - takes precedence)
        INFLUXDB_HOST: InfluxDB hostname (default: localhost, used if URL not set)
        INFLUXDB_PORT: InfluxDB port (default: 8086, used if URL not set)
        INFLUXDB_ORG: Organization name (default: predictive-maintenance)
        INFLUXDB_BUCKET: Bucket name (default: sensor_data)
        INFLUXDB_TOKEN: Authentication token (required in production)
        INFLUXDB_RETENTION: Data retention period (default: 30d)
    
    Returns:
        InfluxDBConfig instance with loaded values
    """
    # Check for full URL first (InfluxDB Cloud)
    url = os.getenv("INFLUXDB_URL")
    if not url:
        # Fall back to host:port for local InfluxDB
        host = os.getenv("INFLUXDB_HOST", "localhost")
        port = os.getenv("INFLUXDB_PORT", "8086")
        url = f"http://{host}:{port}"
    
    return InfluxDBConfig(
        url=url,
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
