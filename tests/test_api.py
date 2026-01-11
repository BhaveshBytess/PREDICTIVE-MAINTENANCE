"""
API Tests — Ingestion & Validation Endpoint Tests

Tests cover:
- Valid payload acceptance (200)
- Schema validation failures (422)
- power_kw rejection
- UUIDv4 validation
- UTC timestamp validation
- Integration with InfluxDB

Prerequisites:
- Docker Desktop running
- InfluxDB container: docker-compose up -d
"""

from datetime import datetime, timezone
from uuid import uuid4
import time

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.storage import SensorEventWriter


# Test client
client = TestClient(app)


def is_influxdb_available() -> bool:
    """Check if InfluxDB is running."""
    try:
        db_client = SensorEventWriter()
        db_client.connect()
        result = db_client.health_check()
        db_client.disconnect()
        return result
    except Exception:
        return False


def get_valid_payload() -> dict:
    """Generate a valid sensor event payload."""
    return {
        "event_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asset": {
            "asset_id": f"test-motor-{uuid4().hex[:8]}",
            "asset_type": "induction_motor"
        },
        "signals": {
            "voltage_v": 230.5,
            "current_a": 15.2,
            "power_factor": 0.85,
            "vibration_g": 0.15
        },
        "context": {
            "operating_state": "RUNNING",
            "source": "test"
        }
    }


class TestValidPayloads:
    """Test valid payload acceptance."""

    @pytest.mark.skipif(
        not is_influxdb_available(),
        reason="InfluxDB not available"
    )
    def test_valid_event_returns_200(self):
        """Valid payload should return 200 OK."""
        payload = get_valid_payload()
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["event_id"] == payload["event_id"]
        assert "power_kw" in data["signals"]

    @pytest.mark.skipif(
        not is_influxdb_available(),
        reason="InfluxDB not available"
    )
    def test_power_kw_computed_correctly(self):
        """Server should compute power_kw from raw signals."""
        payload = get_valid_payload()
        payload["signals"]["voltage_v"] = 230.0
        payload["signals"]["current_a"] = 10.0
        payload["signals"]["power_factor"] = 0.85
        
        # Expected: (230 * 10 * 0.85) / 1000 = 1.955
        expected_power_kw = round((230.0 * 10.0 * 0.85) / 1000.0, 3)
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 200
        assert response.json()["signals"]["power_kw"] == expected_power_kw


class TestPowerKwRejection:
    """Test that client-provided power_kw is rejected."""

    def test_power_kw_in_request_returns_422(self):
        """Request with power_kw should be rejected with 422."""
        payload = get_valid_payload()
        payload["signals"]["power_kw"] = 2.5  # Not allowed!
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 422
        detail = response.json()["detail"]
        # Check error message mentions power_kw
        assert any("power_kw" in str(err).lower() for err in detail)


class TestEventIdValidation:
    """Test UUIDv4 validation for event_id."""

    def test_invalid_uuid_returns_422(self):
        """Invalid UUID should return 422."""
        payload = get_valid_payload()
        payload["event_id"] = "not-a-valid-uuid"
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 422

    def test_uuid_v1_returns_422(self):
        """UUID v1 (not v4) should ideally trigger validation."""
        payload = get_valid_payload()
        # UUID v1 format (time-based, different structure)
        payload["event_id"] = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
        
        response = client.post("/ingest", json=payload)
        
        # v1 UUIDs should be rejected
        assert response.status_code == 422

    def test_empty_event_id_returns_422(self):
        """Empty event_id should return 422."""
        payload = get_valid_payload()
        payload["event_id"] = ""
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 422


class TestTimestampValidation:
    """Test UTC timestamp validation."""

    def test_naive_datetime_returns_422(self):
        """Timestamp without timezone should return 422."""
        payload = get_valid_payload()
        payload["timestamp"] = "2026-01-11T12:00:00"  # No timezone
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 422

    def test_utc_timestamp_accepted(self):
        """UTC timestamp with Z suffix should be accepted."""
        payload = get_valid_payload()
        payload["timestamp"] = "2026-01-11T12:00:00Z"
        
        # Only check if DB is available
        if is_influxdb_available():
            response = client.post("/ingest", json=payload)
            assert response.status_code == 200


class TestOperatingStateValidation:
    """Test operating_state enum validation."""

    def test_invalid_operating_state_returns_422(self):
        """Invalid operating_state should return 422."""
        payload = get_valid_payload()
        payload["context"]["operating_state"] = "INVALID_STATE"
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 422

    @pytest.mark.skipif(
        not is_influxdb_available(),
        reason="InfluxDB not available"
    )
    def test_valid_operating_states_accepted(self):
        """All valid operating states should be accepted."""
        for state in ["RUNNING", "IDLE", "OFF"]:
            payload = get_valid_payload()
            payload["context"]["operating_state"] = state
            
            response = client.post("/ingest", json=payload)
            
            assert response.status_code == 200


class TestPowerFactorValidation:
    """Test power_factor bounds validation."""

    def test_power_factor_above_1_returns_422(self):
        """power_factor > 1.0 should return 422."""
        payload = get_valid_payload()
        payload["signals"]["power_factor"] = 1.5
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 422

    def test_power_factor_negative_returns_422(self):
        """power_factor < 0.0 should return 422."""
        payload = get_valid_payload()
        payload["signals"]["power_factor"] = -0.5
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 422


class TestMissingFields:
    """Test required field validation."""

    def test_missing_event_id_returns_422(self):
        """Missing event_id should return 422."""
        payload = get_valid_payload()
        del payload["event_id"]
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 422

    def test_missing_signals_returns_422(self):
        """Missing signals should return 422."""
        payload = get_valid_payload()
        del payload["signals"]
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 422

    def test_missing_voltage_returns_422(self):
        """Missing voltage_v should return 422."""
        payload = get_valid_payload()
        del payload["signals"]["voltage_v"]
        
        response = client.post("/ingest", json=payload)
        
        assert response.status_code == 422


class TestHealthEndpoint:
    """Test /health endpoint."""

    @pytest.mark.skipif(
        not is_influxdb_available(),
        reason="InfluxDB not available"
    )
    def test_health_returns_200_when_db_healthy(self):
        """Health check should return 200 when DB is reachable."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"


class TestIntegration:
    """Integration tests - verify data reaches InfluxDB."""

    @pytest.mark.skipif(
        not is_influxdb_available(),
        reason="InfluxDB not available"
    )
    def test_event_written_to_influxdb(self):
        """Verify event is actually written to InfluxDB."""
        asset_id = f"integration-test-{uuid4().hex[:8]}"
        payload = get_valid_payload()
        payload["asset"]["asset_id"] = asset_id
        
        # Ingest via API
        response = client.post("/ingest", json=payload)
        assert response.status_code == 200
        
        # Wait for data availability
        time.sleep(5)
        
        # Query directly from InfluxDB
        db_client = SensorEventWriter()
        db_client.connect()
        results = db_client.query_latest_events(limit=50)
        db_client.disconnect()
        
        # Find our event
        matching = [r for r in results if r.get("asset_id") == asset_id]
        assert len(matching) >= 1, f"Event not found in InfluxDB. Results: {len(results)}"
