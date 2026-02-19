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


# Configure logging to show INFO level for this module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class InfluxWrapper:
    """
    Singleton wrapper for InfluxDB operations with automatic fallback.
    
    Features:
    - Singleton pattern ensures single connection across app
    - Automatic fallback to mock mode if connection fails
    - Graceful degradation when InfluxDB is unavailable
    - Thread-safe initialization
    - LOUD LOGGING for debugging
    
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
        self._write_api = None
        self._mock_mode: bool = False
        self._mock_buffer: List[Dict[str, Any]] = []  # Store mock writes for testing
        self._initialized = True
        
        # Store config for use in writes
        self._org = settings.INFLUX_ORG
        self._bucket = settings.INFLUX_BUCKET
        
        self._connect()
    
    def _connect(self) -> None:
        """
        Attempt to connect to InfluxDB.
        
        Falls back to mock mode if:
        - INFLUX_TOKEN is empty
        - Connection fails
        
        NOTE: We do NOT check ping() because InfluxDB Cloud health endpoint
        often returns 'fail' even when the service is working.
        """
        print(f"[DB] Initializing InfluxDB connection...")
        print(f"[DB] URL: {settings.INFLUX_URL}")
        print(f"[DB] ORG: {settings.INFLUX_ORG}")
        print(f"[DB] BUCKET: {settings.INFLUX_BUCKET}")
        print(f"[DB] TOKEN: {'*' * 10}...{settings.INFLUX_TOKEN[-10:] if settings.INFLUX_TOKEN else 'EMPTY'}")
        
        # Check if credentials are configured
        if not settings.INFLUX_TOKEN:
            print("[DB] ⚠️  INFLUX_TOKEN not configured — running in MOCK MODE")
            logger.warning(
                "⚠️  INFLUX_TOKEN not configured — running in MOCK MODE\n"
                "   Data will be logged to console instead of InfluxDB.\n"
                "   Set INFLUX_TOKEN in .env to enable persistence."
            )
            self._mock_mode = True
            return
        
        try:
            # Create client - same as debug script
            self._client = InfluxDBClient(
                url=settings.INFLUX_URL,
                token=settings.INFLUX_TOKEN,
                org=settings.INFLUX_ORG,
            )
            
            # Create write API once and reuse
            self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
            
            # NOTE: We skip ping() check because InfluxDB Cloud returns 'fail' 
            # even when working. The debug script proved writes work regardless.
            
            print(f"[DB] ✅ InfluxDB client initialized (Real Mode)")
            logger.info(f"✅ Connected to InfluxDB at {settings.INFLUX_URL}")
            self._mock_mode = False
            
        except Exception as e:
            print(f"[DB] ❌ InfluxDB connection failed: {e}")
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
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        
        # LOUD LOGGING - always print to console
        print(f"[DB] Writing to Influx: {measurement} | tags={tags} | fields={list(fields.keys())}")
        
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
            
            print(f"[DB] [MOCK] Data buffered (mock mode)")
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
            
            # Write with EXPLICIT org and bucket - matching debug script
            self._write_api.write(
                bucket=self._bucket,
                org=self._org,
                record=point
            )
            
            print(f"[DB] ✅ Write SUCCESS to bucket '{self._bucket}'")
            return True
            
        except InfluxDBError as e:
            print(f"[DB] ❌ InfluxDB write FAILED: {e}")
            logger.error(f"InfluxDB write failed: {e}")
            return False
        except Exception as e:
            print(f"[DB] ❌ Unexpected write error: {e}")
            logger.error(f"Unexpected write error: {e}")
            return False
    
    def query_data(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a Flux query and return results.
        
        Args:
            query: Flux query string
            
        Returns:
            List of record dictionaries
        """
        print(f"[DB] Executing query...")
        
        if self._mock_mode:
            print(f"[DB] [MOCK] Returning mock buffer ({len(self._mock_buffer)} points)")
            return self._mock_buffer.copy()
        
        try:
            query_api = self._client.query_api()
            tables = query_api.query(query, org=self._org)
            
            results = []
            for table in tables:
                for record in table.records:
                    results.append({
                        "time": record.get_time(),
                        "measurement": record.get_measurement(),
                        "field": record.get_field(),
                        "value": record.get_value(),
                        **{k: v for k, v in record.values.items() if not k.startswith("_")}
                    })
            
            print(f"[DB] Query returned {len(results)} records")
            return results
            
        except InfluxDBError as e:
            print(f"[DB] ❌ InfluxDB query FAILED: {e}")
            logger.error(f"InfluxDB query failed: {e}")
            return []
        except Exception as e:
            print(f"[DB] ❌ Unexpected query error: {e}")
            logger.error(f"Unexpected query error: {e}")
            return []

    def query_sensor_history(
        self,
        asset_id: str,
        range_seconds: int = 60,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query sensor history from InfluxDB for a specific asset.
        
        Uses Flux pivot to combine all fields into single rows.
        Returns data in the format expected by the frontend.
        
        Args:
            asset_id: Asset identifier to filter by
            range_seconds: How far back to query (default 60s)
            limit: Maximum number of points to return (default 100)
            
        Returns:
            List of sensor readings with timestamp, voltage_v, current_a,
            power_factor, vibration_g, and is_faulty fields.
        """
        print(f"[DB] Querying sensor history for {asset_id} (last {range_seconds}s, limit {limit})")
        
        if self._mock_mode:
            # Mock mode: filter mock buffer by asset_id and return formatted data
            print(f"[DB] [MOCK] Filtering mock buffer for asset_id={asset_id}")
            mock_results = []
            for point in self._mock_buffer:
                if point.get("tags", {}).get("asset_id") == asset_id:
                    # is_faulty is now stored as a FIELD (boolean), not a tag
                    is_faulty_val = point.get("fields", {}).get("is_faulty", False)
                    mock_results.append({
                        "timestamp": point.get("timestamp"),
                        "voltage_v": point.get("fields", {}).get("voltage_v", 0.0),
                        "current_a": point.get("fields", {}).get("current_a", 0.0),
                        "power_factor": point.get("fields", {}).get("power_factor", 0.0),
                        "vibration_g": point.get("fields", {}).get("vibration_g", 0.0),
                        "is_faulty": bool(is_faulty_val) if not isinstance(is_faulty_val, bool) else is_faulty_val
                    })
            # Return last N points, sorted by timestamp
            mock_results = mock_results[-limit:]
            print(f"[DB] [MOCK] Returning {len(mock_results)} mock points")
            return mock_results
        
        # Build Flux query with pivot to combine fields into rows
        # NOTE: No group() needed since is_faulty is now a FIELD, not a tag
        # All data points are in a single series (asset_id + asset_type tags only)
        flux_query = f'''
from(bucket: "{self._bucket}")
  |> range(start: -{range_seconds}s)
  |> filter(fn: (r) => r["_measurement"] == "sensor_events")
  |> filter(fn: (r) => r["asset_id"] == "{asset_id}")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: false)
  |> limit(n: {limit})
'''
        
        try:
            query_api = self._client.query_api()
            tables = query_api.query(flux_query, org=self._org)
            
            results = []
            for table in tables:
                for record in table.records:
                    # is_faulty is now a FIELD (boolean), pivoted alongside other fields
                    is_faulty_val = record.values.get("is_faulty", False)
                    is_faulty = bool(is_faulty_val) if not isinstance(is_faulty_val, bool) else is_faulty_val
                    
                    # Map to frontend-expected format
                    results.append({
                        "timestamp": record.get_time().isoformat(),
                        "voltage_v": record.values.get("voltage_v", 0.0),
                        "current_a": record.values.get("current_a", 0.0),
                        "power_factor": record.values.get("power_factor", 0.0),
                        "vibration_g": record.values.get("vibration_g", 0.0),
                        "is_faulty": is_faulty
                    })
            
            # FAILSAFE: Python-side sort guarantees chronological order
            results.sort(key=lambda x: x["timestamp"])
            
            print(f"[DB] ✅ Sensor history query returned {len(results)} records")
            return results
            
        except InfluxDBError as e:
            print(f"[DB] ❌ Sensor history query FAILED: {e}")
            logger.error(f"Sensor history query failed: {e}")
            return []
        except Exception as e:
            print(f"[DB] ❌ Unexpected sensor history query error: {e}")
            logger.error(f"Unexpected sensor history query error: {e}")
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
        print("[DB] InfluxDB connection closed")
    
    def reconnect(self) -> bool:
        """
        Attempt to reconnect to InfluxDB.
        
        Useful for recovering from temporary connection issues.
        
        Returns:
            True if reconnection succeeded
        """
        print("[DB] Attempting reconnect...")
        self.close()
        self._initialized = False
        self.__init__()
        return self.is_connected


# Singleton instance — import this in other modules
db = InfluxWrapper()
