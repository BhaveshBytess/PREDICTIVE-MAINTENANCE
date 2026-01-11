"""
Reporting Layer Tests

Tests verify:
- PDF generation produces valid bytes
- Excel generation produces valid bytes
- Smart filename pattern
- Report uses persisted data (snapshot rule)
- All required fields included
"""

from datetime import datetime, timezone
import io

import pytest

from backend.rules.assessor import HealthReport, RiskLevel, Explanation, ReportMetadata
from backend.reports.generator import (
    generate_pdf_report,
    generate_excel_report,
    generate_filename,
)


def create_test_health_report() -> HealthReport:
    """Create a sample health report for testing."""
    return HealthReport(
        report_id="test-report-123",
        timestamp=datetime(2026, 1, 11, 17, 30, 0, tzinfo=timezone.utc),
        asset_id="Motor-01",
        health_score=65,
        risk_level=RiskLevel.MODERATE,
        maintenance_window_days=14.5,
        explanations=[
            Explanation(
                reason="Vibration value (0.45g) is 3.2σ above normal (baseline: 0.15g)",
                related_features=["vibration_g", "vibration_intensity_rms"],
                confidence_score=0.85
            ),
            Explanation(
                reason="Power Factor showing degradation trend",
                related_features=["power_factor"],
                confidence_score=0.72
            )
        ],
        metadata=ReportMetadata(
            model_version="detector:1.0.0|baseline:abc123"
        )
    )


class TestPDFGeneration:
    """Test PDF report generation."""

    def test_generates_valid_pdf_bytes(self):
        """PDF generation returns non-empty bytes."""
        report = create_test_health_report()
        
        pdf_bytes = generate_pdf_report(report)
        
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

    def test_pdf_starts_with_magic_bytes(self):
        """PDF should start with %PDF header."""
        report = create_test_health_report()
        
        pdf_bytes = generate_pdf_report(report)
        
        # PDF files start with %PDF-
        assert pdf_bytes[:5] == b'%PDF-'

    def test_pdf_is_substantial(self):
        """PDF should have meaningful content (not just header)."""
        report = create_test_health_report()
        
        pdf_bytes = generate_pdf_report(report)
        
        # A real PDF with content should be larger than 1KB
        assert len(pdf_bytes) > 1000

    def test_pdf_ends_with_eof(self):
        """PDF should end with EOF marker."""
        report = create_test_health_report()
        
        pdf_bytes = generate_pdf_report(report)
        
        # PDF files end with %%EOF
        assert b'%%EOF' in pdf_bytes[-50:]


class TestExcelGeneration:
    """Test Excel report generation."""

    def test_generates_valid_excel_bytes(self):
        """Excel generation returns non-empty bytes."""
        report = create_test_health_report()
        
        excel_bytes = generate_excel_report(report)
        
        assert isinstance(excel_bytes, bytes)
        assert len(excel_bytes) > 0

    def test_excel_starts_with_magic_bytes(self):
        """Excel (xlsx) should start with PK (zip) header."""
        report = create_test_health_report()
        
        excel_bytes = generate_excel_report(report)
        
        # XLSX files are ZIP archives, start with PK
        assert excel_bytes[:2] == b'PK'

    def test_excel_can_be_read_by_pandas(self):
        """Excel file should be readable by pandas."""
        import pandas as pd
        
        report = create_test_health_report()
        excel_bytes = generate_excel_report(report)
        
        # Read back with pandas
        buffer = io.BytesIO(excel_bytes)
        df = pd.read_excel(buffer, sheet_name='Summary')
        
        # Should have Field and Value columns
        assert 'Field' in df.columns
        assert 'Value' in df.columns
        
        # Should contain asset ID
        assert 'Motor-01' in df['Value'].values


class TestFilenameGeneration:
    """Test smart filename generation."""

    def test_filename_pattern(self):
        """Filename follows Report_{AssetID}_{YYYYMMDD_HHMM}.ext pattern."""
        asset_id = "Motor-01"
        timestamp = datetime(2026, 1, 11, 17, 30, 0, tzinfo=timezone.utc)
        
        filename = generate_filename(asset_id, timestamp, "pdf")
        
        assert filename == "Report_Motor-01_20260111_1730.pdf"

    def test_filename_sanitizes_spaces(self):
        """Spaces in asset ID should be converted to underscores."""
        asset_id = "Motor Test 01"
        timestamp = datetime(2026, 1, 11, 17, 30, 0, tzinfo=timezone.utc)
        
        filename = generate_filename(asset_id, timestamp, "xlsx")
        
        assert " " not in filename
        assert "Motor_Test_01" in filename

    def test_filename_sanitizes_slashes(self):
        """Slashes in asset ID should be converted to dashes."""
        asset_id = "Plant/Motor/01"
        timestamp = datetime(2026, 1, 11, 17, 30, 0, tzinfo=timezone.utc)
        
        filename = generate_filename(asset_id, timestamp, "pdf")
        
        assert "/" not in filename
        assert "Plant-Motor-01" in filename


class TestSnapshotRule:
    """Test that reports use persisted data, not recomputed values."""

    def test_uses_provided_health_score_in_excel(self):
        """Report should use provided health score in Excel."""
        import pandas as pd
        
        report = create_test_health_report()
        report.health_score = 42  # Specific value
        
        excel_bytes = generate_excel_report(report)
        buffer = io.BytesIO(excel_bytes)
        df = pd.read_excel(buffer, sheet_name='Summary')
        
        # The exact value should be in the Excel
        assert 42 in df['Value'].values

    def test_uses_provided_timestamp_in_excel(self):
        """Report should use provided timestamp in Excel."""
        import pandas as pd
        
        report = create_test_health_report()
        excel_bytes = generate_excel_report(report)
        
        buffer = io.BytesIO(excel_bytes)
        df = pd.read_excel(buffer, sheet_name='Summary')
        
        # The specific date should be in values
        values_str = ' '.join(str(v) for v in df['Value'].values)
        assert '2026-01-11' in values_str


class TestContentCompleteness:
    """Test Manager Test - all actionable info included in Excel."""

    def test_includes_maintenance_window(self):
        """Report must include maintenance window days."""
        import pandas as pd
        
        report = create_test_health_report()
        excel_bytes = generate_excel_report(report)
        
        buffer = io.BytesIO(excel_bytes)
        df = pd.read_excel(buffer, sheet_name='Summary')
        
        # Maintenance window should be in values
        assert 14.5 in df['Value'].values or '14.5' in str(df['Value'].values)

    def test_includes_risk_level(self):
        """Report must include risk level."""
        import pandas as pd
        
        report = create_test_health_report()
        excel_bytes = generate_excel_report(report)
        
        buffer = io.BytesIO(excel_bytes)
        df = pd.read_excel(buffer, sheet_name='Summary')
        
        assert 'MODERATE' in df['Value'].values

    def test_includes_model_version(self):
        """Report must include model version."""
        import pandas as pd
        
        report = create_test_health_report()
        excel_bytes = generate_excel_report(report)
        
        buffer = io.BytesIO(excel_bytes)
        df = pd.read_excel(buffer, sheet_name='Summary')
        
        values_str = ' '.join(str(v) for v in df['Value'].values)
        assert 'detector' in values_str or 'baseline' in values_str
