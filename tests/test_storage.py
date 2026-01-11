"""
Integration Tests — InfluxDB Storage Layer (Phase 2)

REAL integration tests against a running InfluxDB instance.
No mocking - tests verify actual writes and reads.

Prerequisites:
    1. InfluxDB must be running: docker-compose up -d
    2. Environment variables must be set (or use defaults)

CONTRACTS.md Reference: Section 3.1
"""

import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.generator import HybridDataGenerator, DegradationMode
from backend.storage import (
    SensorEventWriter,
    InfluxDBClientError,
    load_config,
    MEASUREMENT_NAME,
)


# Unique test run ID to avoid conflicts
TEST_RUN_ID = uuid4().hex[:8]


def get_test_asset_id(suffix: str) -> str:
    """Generate unique asset_id for this test run."""
    return f"test-{TEST_RUN_ID}-{suffix}"


@pytest.fixture(scope="session")
def influx_client():
    """Session-scoped fixture providing a connected InfluxDB client."""
    try:
        client = SensorEventWriter()
        client.connect()
        if not client.health_check():
            pytest.skip("InfluxDB is not available")
        
        # Seed with initial data to ensure tests have something to query
        seed_event = {
            "event_id": "session-seed-event",
            "timestamp": datetime.now(timezone.utc),
            "asset": {
                "asset_id": f"seed-{TEST_RUN_ID}",
                "asset_type": "induction_motor"
            },
            "signals": {
                "voltage_v": 230.0,
                "current_a": 15.0,
                "power_factor": 0.85,
                "power_kw": 2.9,
                "vibration_g": 0.15
            },
            "context": {
                "operating_state": "RUNNING",
                "source": "simulator"
            }
        }
        client.write_sensor_event(seed_event)
        # Wait for seed data to be available
        time.sleep(3)
        
        yield client
        client.disconnect()
    except Exception as e:
        pytest.skip(f"InfluxDB connection failed: {e}")


class TestConnection:
    """Test InfluxDB connection functionality."""

    def test_connection_succeeds(self, influx_client):
        """Verify connection is established."""
        assert influx_client.health_check() is True

    def test_ping_responds(self, influx_client):
        """Verify InfluxDB responds to ping."""
        assert influx_client._client.ping() is True

    def test_config_loads_from_environment(self):
        """Verify configuration loads correctly."""
        config = load_config()
        assert config.host is not None
        assert config.port > 0
        assert config.org is not None
        assert config.bucket is not None
        assert config.token is not None


class TestWriteAndRead:
    """Test write and read operations together."""

    def test_write_and_read_single_event(self, influx_client):
        """Verify event can be written and read back."""
        asset_id = get_test_asset_id("single")
        
        event = {
            "event_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc),
            "asset": {
                "asset_id": asset_id,
                "asset_type": "induction_motor"
            },
            "signals": {
                "voltage_v": 235.7,
                "current_a": 18.5,
                "power_factor": 0.92,
                "power_kw": 4.013,
                "vibration_g": 0.28
            },
            "context": {
                "operating_state": "RUNNING",
                "source": "simulator"
            }
        }
        
        # Write
        influx_client.write_sensor_event(event)
        
        # Wait for data to be available
        time.sleep(5)
        
        # Read back - query ALL data first 
        all_results = influx_client.query_latest_events(limit=50)
        
        # Check our data is in there
        matching = [r for r in all_results if r.get("asset_id") == asset_id]
        assert len(matching) >= 1, f"Expected data for {asset_id}, got 0. All results: {len(all_results)}"
        
        record = matching[0]
        assert record["voltage_v"] == 235.7
        assert record["current_a"] == 18.5
        assert record["power_factor"] == 0.92
        assert record["power_kw"] == 4.013
        assert record["vibration_g"] == 0.28

    def test_write_batch_events(self, influx_client):
        """Verify batch writes work correctly."""
        events = []
        for i in range(5):
            events.append({
                "event_id": str(uuid4()),
                "timestamp": datetime.now(timezone.utc),
                "asset": {
                    "asset_id": get_test_asset_id("batch"),
                    "asset_type": "induction_motor"
                },
                "signals": {
                    "voltage_v": 230.0 + i,
                    "current_a": 15.0 + i * 0.5,
                    "power_factor": 0.85,
                    "power_kw": 2.9 + i * 0.1,
                    "vibration_g": 0.15
                },
                "context": {
                    "operating_state": "RUNNING",
                    "source": "simulator"
                }
            })
        
        count = influx_client.write_sensor_events(events)
        assert count == 5

    def test_write_from_generator_output(self, influx_client):
        """Verify generator output can be written directly."""
        asset_id = get_test_asset_id("generator")
        generator = HybridDataGenerator(
            seed=42,
            asset_id=asset_id,
            degradation_mode=DegradationMode.HEALTHY
        )
        
        # Generate and write events
        for event in generator.generate(count=3):
            event_dict = event.model_dump()
            event_dict["context"]["operating_state"] = event.context.operating_state.value
            influx_client.write_sensor_event(event_dict)
        
        # Wait and verify
        time.sleep(5)
        
        all_results = influx_client.query_latest_events(limit=50)
        matching = [r for r in all_results if r.get("asset_id") == asset_id]
        assert len(matching) >= 3


class TestQueryFeatures:
    """Test query functionality."""

    def test_query_all_returns_data(self, influx_client):
        """Verify query without filter returns data."""
        # Write a known event first
        event = {
            "event_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc),
            "asset": {
                "asset_id": get_test_asset_id("query-all"),
                "asset_type": "induction_motor"
            },
            "signals": {
                "voltage_v": 228.3,
                "current_a": 16.7,
                "power_factor": 0.88,
                "power_kw": 3.355,
                "vibration_g": 0.22
            },
            "context": {
                "operating_state": "IDLE",
                "source": "simulator"
            }
        }
        
        influx_client.write_sensor_event(event)
        time.sleep(5)
        
        results = influx_client.query_latest_events(limit=50)
        assert len(results) >= 1
        
        # Check data has expected structure
        record = results[0]
        assert "timestamp" in record
        assert "asset_id" in record
        assert "voltage_v" in record
        assert "current_a" in record
        assert "power_factor" in record
        assert "power_kw" in record
        assert "vibration_g" in record


class TestSchemaCompliance:
    """Test that storage schema matches CONTRACTS.md."""

    def test_event_id_is_stored_as_field_not_tag(self, influx_client):
        """Verify event_id is retrievable (stored as field, not tag)."""
        known_event_id = "schema-test-event-id-12345"
        asset_id = get_test_asset_id("schema")
        
        event = {
            "event_id": known_event_id,
            "timestamp": datetime.now(timezone.utc),
            "asset": {
                "asset_id": asset_id,
                "asset_type": "induction_motor"
            },
            "signals": {
                "voltage_v": 230.0,
                "current_a": 15.0,
                "power_factor": 0.85,
                "power_kw": 2.9,
                "vibration_g": 0.15
            },
            "context": {
                "operating_state": "RUNNING",
                "source": "simulator"
            }
        }
        
        influx_client.write_sensor_event(event)
        time.sleep(5)
        
        results = influx_client.query_latest_events(limit=50)
        matching = [r for r in results if r.get("asset_id") == asset_id]
        
        assert len(matching) >= 1
        assert matching[0]["event_id"] == known_event_id


class TestErrorHandling:
    """Test error handling for edge cases."""

    def test_write_missing_field_raises_error(self, influx_client):
        """Verify missing required field raises error."""
        incomplete_event = {
            "event_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc),
            "asset": {
                "asset_id": "test-incomplete"
            },
            "signals": {
                "voltage_v": 230.0
            },
            "context": {
                "operating_state": "RUNNING",
                "source": "simulator"
            }
        }
        
        with pytest.raises(InfluxDBClientError):
            influx_client.write_sensor_event(incomplete_event)

    def test_not_connected_raises_error(self):
        """Verify operations on disconnected client raise error."""
        client = SensorEventWriter()
        
        with pytest.raises(InfluxDBClientError) as excinfo:
            client.write_sensor_event({})
        
        assert "Not connected" in str(excinfo.value)
