"""
InfluxDB Client — Time-Series Storage Interface

Provides a clean interface for writing and reading sensor events to/from InfluxDB.
Schema follows CONTRACTS.md with proper tag/field separation per guardrails.

CONTRACTS.md Reference: Section 3.1 - Canonical Sensor Event
Guardrails:
- Tags: asset_id, asset_type, operating_state (low-cardinality)
- Fields: event_id, voltage_v, current_a, power_factor, power_kw, vibration_g
- event_id is a STRING FIELD, not a Tag
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError

from .config import InfluxDBConfig, MEASUREMENT_NAME, load_config


class InfluxDBClientError(Exception):
    """Custom exception for InfluxDB client errors."""
    pass


class SensorEventWriter:
    """
    InfluxDB client wrapper for sensor event storage.
    
    Handles connection management, writes, and reads for sensor events.
    All timestamps are stored as UTC per CONTRACTS.md.
    """

    def __init__(self, config: Optional[InfluxDBConfig] = None):
        """
        Initialize the client.
        
        Args:
            config: InfluxDB configuration. If None, loads from environment.
        """
        self.config = config or load_config()
        self._client: Optional[InfluxDBClient] = None

    def connect(self) -> None:
        """
        Establish connection to InfluxDB.
        
        Raises:
            InfluxDBClientError: If connection fails
        """
        try:
            self._client = InfluxDBClient(
                url=self.config.url,
                token=self.config.token,
                org=self.config.org
            )
            # Verify connection
            if not self._client.ping():
                raise InfluxDBClientError("Failed to ping InfluxDB")
        except Exception as e:
            raise InfluxDBClientError(f"Connection failed: {e}") from e

    def disconnect(self) -> None:
        """Close the connection."""
        if self._client:
            self._client.close()
            self._client = None

    @contextmanager
    def connection(self):
        """Context manager for connection handling."""
        try:
            self.connect()
            yield self
        finally:
            self.disconnect()

    def _ensure_connected(self) -> None:
        """Ensure client is connected."""
        if self._client is None:
            raise InfluxDBClientError("Not connected. Call connect() first.")

    def write_sensor_event(self, event_data: Dict[str, Any]) -> None:
        """
        Write a sensor event to InfluxDB.
        
        Args:
            event_data: Dictionary containing sensor event data.
                       Must match Canonical Sensor Event schema.
        
        Schema mapping:
            Tags (low-cardinality identity):
                - asset_id
                - asset_type
                - operating_state
            Fields (numeric signals + high-cardinality):
                - event_id (string)
                - voltage_v (float)
                - current_a (float)
                - power_factor (float)
                - power_kw (float)
                - vibration_g (float)
            Timestamp:
                - event timestamp (UTC)
        
        Raises:
            InfluxDBClientError: If write fails
        """
        self._ensure_connected()
        
        try:
            # Build point with proper tag/field separation
            point = (
                Point(MEASUREMENT_NAME)
                # Tags (low-cardinality identity)
                .tag("asset_id", event_data["asset"]["asset_id"])
                .tag("asset_type", event_data["asset"]["asset_type"])
                .tag("operating_state", event_data["context"]["operating_state"])
                # Fields (numeric signals)
                .field("event_id", str(event_data["event_id"]))
                .field("voltage_v", float(event_data["signals"]["voltage_v"]))
                .field("current_a", float(event_data["signals"]["current_a"]))
                .field("power_factor", float(event_data["signals"]["power_factor"]))
                .field("power_kw", float(event_data["signals"]["power_kw"]))
                .field("vibration_g", float(event_data["signals"]["vibration_g"]))
                # Timestamp (UTC)
                .time(event_data["timestamp"], WritePrecision.NS)
            )
            
            write_api = self._client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=self.config.bucket, record=point)
            
        except InfluxDBError as e:
            raise InfluxDBClientError(f"Write failed: {e}") from e
        except KeyError as e:
            raise InfluxDBClientError(f"Missing required field in event data: {e}") from e

    def write_sensor_events(self, events: List[Dict[str, Any]]) -> int:
        """
        Write multiple sensor events to InfluxDB.
        
        Args:
            events: List of event dictionaries
            
        Returns:
            Number of events written
            
        Raises:
            InfluxDBClientError: If write fails
        """
        self._ensure_connected()
        
        points = []
        for event_data in events:
            point = (
                Point(MEASUREMENT_NAME)
                .tag("asset_id", event_data["asset"]["asset_id"])
                .tag("asset_type", event_data["asset"]["asset_type"])
                .tag("operating_state", event_data["context"]["operating_state"])
                .field("event_id", str(event_data["event_id"]))
                .field("voltage_v", float(event_data["signals"]["voltage_v"]))
                .field("current_a", float(event_data["signals"]["current_a"]))
                .field("power_factor", float(event_data["signals"]["power_factor"]))
                .field("power_kw", float(event_data["signals"]["power_kw"]))
                .field("vibration_g", float(event_data["signals"]["vibration_g"]))
                .time(event_data["timestamp"], WritePrecision.NS)
            )
            points.append(point)
        
        try:
            write_api = self._client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=self.config.bucket, record=points)
            return len(points)
        except InfluxDBError as e:
            raise InfluxDBClientError(f"Batch write failed: {e}") from e

    def query_latest_events(
        self,
        asset_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query the latest sensor events.
        
        Args:
            asset_id: Filter by asset_id (optional)
            limit: Maximum number of events to return
            
        Returns:
            List of event records as dictionaries
            
        Raises:
            InfluxDBClientError: If query fails
        """
        self._ensure_connected()
        
        # Build Flux query
        # CRITICAL: Must pivot FIRST, then filter by asset_id tag
        # After pivot, tags become regular columns and can be filtered
        asset_filter = ""
        if asset_id:
            asset_filter = f'|> filter(fn: (r) => r.asset_id == "{asset_id}")'
        
        query = f'''
        from(bucket: "{self.config.bucket}")
            |> range(start: -30d)
            |> filter(fn: (r) => r._measurement == "{MEASUREMENT_NAME}")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            {asset_filter}
            |> sort(columns: ["_time"], desc: true)
            |> limit(n: {limit})
        '''
        
        try:
            query_api = self._client.query_api()
            tables = query_api.query(query, org=self.config.org)
            
            results = []
            for table in tables:
                for record in table.records:
                    results.append({
                        "timestamp": record.get_time(),
                        "asset_id": record.values.get("asset_id"),
                        "asset_type": record.values.get("asset_type"),
                        "operating_state": record.values.get("operating_state"),
                        "event_id": record.values.get("event_id"),
                        "voltage_v": record.values.get("voltage_v"),
                        "current_a": record.values.get("current_a"),
                        "power_factor": record.values.get("power_factor"),
                        "power_kw": record.values.get("power_kw"),
                        "vibration_g": record.values.get("vibration_g"),
                    })
            return results
            
        except InfluxDBError as e:
            raise InfluxDBClientError(f"Query failed: {e}") from e

    def health_check(self) -> bool:
        """
        Check if InfluxDB is healthy and accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            if self._client is None:
                self.connect()
            return self._client.ping()
        except Exception:
            return False

    def delete_all_data(self, confirm: bool = False) -> None:
        """
        Delete all data from the bucket. USE WITH CAUTION.
        
        Args:
            confirm: Must be True to proceed with deletion
            
        Raises:
            InfluxDBClientError: If confirmation not provided or delete fails
        """
        if not confirm:
            raise InfluxDBClientError(
                "Deletion requires explicit confirmation. "
                "Call with confirm=True to proceed."
            )
        
        self._ensure_connected()
        
        try:
            delete_api = self._client.delete_api()
            delete_api.delete(
                start="1970-01-01T00:00:00Z",
                stop="2100-01-01T00:00:00Z",
                predicate=f'_measurement="{MEASUREMENT_NAME}"',
                bucket=self.config.bucket,
                org=self.config.org
            )
        except InfluxDBError as e:
            raise InfluxDBClientError(f"Delete failed: {e}") from e
