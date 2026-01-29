"""
Storage Module — InfluxDB Time-Series Storage (Phase 2)

Public API:
- SensorEventWriter: Main client class for write/query operations
- InfluxDBConfig: Configuration dataclass
- load_config: Load configuration from environment

Note: This module requires the influxdb-client package.
In serverless environments without InfluxDB, imports will raise ImportError.
"""

try:
    from .client import SensorEventWriter, InfluxDBClientError
    from .config import InfluxDBConfig, load_config, MEASUREMENT_NAME
    
    __all__ = [
        "SensorEventWriter",
        "InfluxDBClientError",
        "InfluxDBConfig",
        "load_config",
        "MEASUREMENT_NAME",
    ]
except ImportError as e:
    # InfluxDB client not installed - this is expected in serverless deployments
    raise ImportError(
        f"InfluxDB client not available: {e}. "
        "This is expected in serverless deployments. "
        "Demo features are available via /system/* endpoints."
    ) from e
