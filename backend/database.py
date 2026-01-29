"""
InfluxDB Database Wrapper — Singleton with Fallback

Provides a unified interface for InfluxDB operations with automatic
fallback to mock mode if connection fails or credentials are missing.

Usage:
    from backend.database import db
    
    # Write data
    db.write_point("sensor_events", {"asset_id": "Motor-01"}, {"voltage_v": 230.0})
    
    # Query data
    results = db.query_data('from(bucket: "sensor_data") |> range(start: -1h)')
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from threading import Lock

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError

from backend.config import settings


logger = logging.getLogger(__name__)


class InfluxWrapper:
    """
    Singleton wrapper for InfluxDB operations with automatic fallback.
    
    Features:
    - Singleton pattern ensures single connection across app
    - Automatic fallback to mock mode if connection fails
    - Graceful degradation when InfluxDB is unavailable
    - Thread-safe initialization
    
    Mock Mode:
    - Activated when INFLUX_TOKEN is empty or connection fails
    - Logs all writes to console instead of database
    - Returns empty results for queries
    - Prevents app crashes due to database issues
    """
    
    _instance: Optional['InfluxWrapper'] = None
    _lock: Lock = Lock()
    
    def __new__(cls) -> 'InfluxWrapper':
        """Thread-safe singleton instantiation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the wrapper (only runs once due to singleton)."""
        if self._initialized:
            return
            
        self._client: Optional[InfluxDBClient] = None
        self._mock_mode: bool = False
        self._mock_buffer: List[Dict[str, Any]] = []  # Store mock writes for testing
        self._initialized = True
        
        self._connect()
    
    def _connect(self) -> None:
        """
        Attempt to connect to InfluxDB.
        
        Falls back to mock mode if:
        - INFLUX_TOKEN is empty
        - Connection fails
        - Ping fails
        """
        # Check if credentials are configured
        if not settings.INFLUX_TOKEN:
            logger.warning(
                "⚠️  INFLUX_TOKEN not configured — running in MOCK MODE\n"
                "   Data will be logged to console instead of InfluxDB.\n"
                "   Set INFLUX_TOKEN in .env to enable persistence."
            )
            self._mock_mode = True
            return
        
        try:
            self._client = InfluxDBClient(
                url=settings.INFLUX_URL,
                token=settings.INFLUX_TOKEN,
                org=settings.INFLUX_ORG,
            )
            
            # Verify connection
            if not self._client.ping():
                raise ConnectionError("InfluxDB ping failed")
            
            logger.info(f"✅ Connected to InfluxDB at {settings.INFLUX_URL}")
            self._mock_mode = False
            
        except Exception as e:
            logger.warning(
                f"⚠️  InfluxDB connection failed: {e}\n"
                "   Running in MOCK MODE — data will be logged to console."
            )
            self._mock_mode = True
            if self._client:
                try:
                    self._client.close()
                except:
                    pass
                self._client = None
    
    @property
    def is_mock_mode(self) -> bool:
        """Check if running in mock mode."""
        return self._mock_mode
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to InfluxDB."""
        return self._client is not None and not self._mock_mode
    
    def write_point(
        self,
        measurement: str,
        tags: Dict[str, str],
        fields: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Write a data point to InfluxDB or mock buffer.
        
        Args:
            measurement: Measurement name (e.g., "sensor_events")
            tags: Tag key-value pairs (low cardinality identifiers)
            fields: Field key-value pairs (actual data values)
            timestamp: Point timestamp (defaults to now UTC)
            
        Returns:
            True if write succeeded, False otherwise
            
        Example:
            db.write_point(
                "sensor_events",
                {"asset_id": "Motor-01", "asset_type": "motor"},
                {"voltage_v": 230.5, "current_a": 15.2}
            )
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        
        if self._mock_mode:
            # Mock mode: log to console and buffer
            mock_data = {
                "measurement": measurement,
                "tags": tags,
                "fields": fields,
                "timestamp": timestamp.isoformat(),
            }
            self._mock_buffer.append(mock_data)
            
            # Keep buffer bounded (last 1000 points)
            if len(self._mock_buffer) > 1000:
                self._mock_buffer = self._mock_buffer[-1000:]
            
            logger.debug(
                f"[MOCK WRITE] {measurement} | "
                f"tags={tags} | fields={fields}"
            )
            return True
        
        try:
            # Build InfluxDB point
            point = Point(measurement)
            
            for key, value in tags.items():
                point = point.tag(key, str(value))
            
            for key, value in fields.items():
                if isinstance(value, (int, float)):
                    point = point.field(key, float(value))
                elif isinstance(value, bool):
                    point = point.field(key, value)
                else:
                    point = point.field(key, str(value))
            
            point = point.time(timestamp, WritePrecision.NS)
            
            # Write synchronously
            write_api = self._client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=settings.INFLUX_BUCKET, record=point)
            
            logger.debug(f"[INFLUX WRITE] {measurement} | tags={tags}")
            return True
            
        except InfluxDBError as e:
            logger.error(f"InfluxDB write failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected write error: {e}")
            return False
    
    def query_data(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a Flux query and return results.
        
        Args:
            query: Flux query string
            
        Returns:
            List of record dictionaries
            
        Example:
            results = db.query_data('''
                from(bucket: "sensor_data")
                |> range(start: -1h)
                |> filter(fn: (r) => r["asset_id"] == "Motor-01")
            ''')
        """
        if self._mock_mode:
            logger.debug(f"[MOCK QUERY] Returning mock buffer ({len(self._mock_buffer)} points)")
            return self._mock_buffer.copy()
        
        try:
            query_api = self._client.query_api()
            tables = query_api.query(query, org=settings.INFLUX_ORG)
            
            results = []
            for table in tables:
                for record in table.records:
                    results.append({
                        "time": record.get_time(),
                        "measurement": record.get_measurement(),
                        "field": record.get_field(),
                        "value": record.get_value(),
                        **{k: v for k, v in record.values.items() if k.startswith("_") is False}
                    })
            
            logger.debug(f"[INFLUX QUERY] Returned {len(results)} records")
            return results
            
        except InfluxDBError as e:
            logger.error(f"InfluxDB query failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected query error: {e}")
            return []
    
    def get_mock_buffer(self) -> List[Dict[str, Any]]:
        """Get the mock write buffer (for testing/debugging)."""
        return self._mock_buffer.copy()
    
    def clear_mock_buffer(self) -> None:
        """Clear the mock write buffer."""
        self._mock_buffer.clear()
    
    def close(self) -> None:
        """Close the InfluxDB connection."""
        if self._client:
            try:
                self._client.close()
            except:
                pass
            self._client = None
        logger.info("InfluxDB connection closed")
    
    def reconnect(self) -> bool:
        """
        Attempt to reconnect to InfluxDB.
        
        Useful for recovering from temporary connection issues.
        
        Returns:
            True if reconnection succeeded
        """
        self.close()
        self._connect()
        return self.is_connected


# Singleton instance — import this in other modules
db = InfluxWrapper()
