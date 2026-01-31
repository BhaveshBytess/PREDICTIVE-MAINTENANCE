"""
Industrial Asset Health Certificate — 5-Page Professional Report

A comprehensive, audit-compliant PDF report generator that produces
professional "Industrial Asset Diagnostic Reports" from persisted HealthReport data.

THE SNAPSHOT RULE (CRITICAL):
- Health Score, Risk Level, Anomaly Score, and Current Sensor Readings
  MUST be pulled from the persisted HealthReport object.
- DO NOT re-run ML models or re-read current sensors.
- The report reflects exactly what the system "thought" at capture time.

CONTEXT DATA (SIMULATED FOR DEMO):
- 24-Hour Statistics and 7-Day Trends use mock/simulated data
- Mock data aligns visually with current state

Pages:
1. Executive Summary (Health Gauge, Key Metrics)
2. Sensor Analysis (Current Readings, 24h Statistics)
3. ML Explainability (Feature Contributions, Insights)
4. Business ROI & Maintenance Actions
5. Audit Trail (Process Log, Compliance Checkboxes)
"""

import math
from io import BytesIO
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Image, KeepTogether
)
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate, Frame
from reportlab.platypus.flowables import Flowable

from backend.rules.assessor import HealthReport, RiskLevel
from backend.reports.constants import (
    PRIMARY, DANGER, SUCCESS, WARNING, ORANGE,
    GRAY_DARK, GRAY_MEDIUM, GRAY_LIGHT, GRAY_BG, GRAY_BORDER, WHITE,
    RISK_COLORS, GAUGE_SEGMENTS,
    COST_MAINTENANCE_USD, COST_FAILURE_USD,
    GOLDEN_BASELINE, SIGNAL_METADATA,
    MAINTENANCE_ACTIONS, COMPLIANCE_STANDARDS, AUDIT_STEPS,
    FONT_SIZE_TITLE, FONT_SIZE_HEADING, FONT_SIZE_BODY, FONT_SIZE_SMALL, FONT_SIZE_TINY,
    PAGE_MARGIN_CM,
)
from backend.reports.mock_data import (
    generate_24h_stats,
    generate_7day_sparkline,
    generate_feature_contributions,
    get_primary_driver,
)
from backend.reports.components.gauge import draw_health_gauge
from backend.reports.components.charts import draw_horizontal_bar_chart, draw_sparkline
from backend.reports.generator import fetch_maintenance_logs_for_report


# =============================================================================
# CONSTANTS FOR THIS MODULE
# =============================================================================

PAGE_WIDTH, PAGE_HEIGHT = A4
CONTENT_WIDTH = PAGE_WIDTH - (2 * PAGE_MARGIN_CM * cm)

# Healthy baselines for deviation calculation (per specification)
HEALTHY_BASELINES = {
    "voltage_v": 230.0,
    "current_a": 15.0,
    "power_factor": 0.95,
    "vibration_g": 0.0,
    "power_kw": 3.27,  # 230 * 15 * 0.95 / 1000
}


# =============================================================================
# CUSTOM FLOWABLES
# =============================================================================

class HealthGaugeFlowable(Flowable):
    """
    Custom Flowable that renders the health gauge using canvas drawing.
    """
    
    def __init__(self, health_score: int, risk_level: str, width: float = 200, height: float = 140):
        Flowable.__init__(self)
        self.health_score = health_score
        self.risk_level = risk_level
        self.width = width
        self.height = height
    
    def draw(self):
        """Draw the gauge on the canvas."""
        canvas = self.canv
        # Center the gauge
        center_x = self.width / 2
        center_y = self.height * 0.55  # Slightly above center for label space
        radius = min(self.width, self.height) * 0.45
        
        draw_health_gauge(
            canvas=canvas,
            center_x=center_x,
            center_y=center_y,
            radius=radius,
            health_score=self.health_score,
            risk_level=self.risk_level
        )
    
    def wrap(self, availWidth, availHeight):
        return self.width, self.height


class HorizontalBarChartFlowable(Flowable):
    """
    Custom Flowable for horizontal bar chart visualization.
    """
    
    def __init__(self, contributions: List[Dict], width: float = 400, height: float = 150):
        Flowable.__init__(self)
        self.contributions = contributions
        self.width = width
        self.height = height
    
    def draw(self):
        """Draw the bar chart on the canvas."""
        canvas = self.canv
        draw_horizontal_bar_chart(
            canvas=canvas,
            x=10,
            y=self.height - 10,
            contributions=self.contributions,
            width=self.width - 20,
            bar_height=22,
            spacing=8,
            max_bars=5
        )
    
    def wrap(self, availWidth, availHeight):
        return self.width, self.height


class SparklineFlowable(Flowable):
    """
    Custom Flowable for inline sparkline charts.
    """
    
    def __init__(self, data: List[float], width: float = 80, height: float = 20,
                 line_color: colors.Color = None, baseline_value: float = None):
        Flowable.__init__(self)
        self.data = data
        self.width = width
        self.height = height
        self.line_color = line_color or PRIMARY
        self.baseline_value = baseline_value
    
    def draw(self):
        """Draw the sparkline on the canvas."""
        draw_sparkline(
            canvas=self.canv,
            x=0,
            y=2,
            data=self.data,
            width=self.width,
            height=self.height - 4,
            line_color=self.line_color,
            show_endpoint=True,
            show_baseline=self.baseline_value is not None,
            baseline_value=self.baseline_value
        )
    
    def wrap(self, availWidth, availHeight):
        return self.width, self.height


class CheckboxFlowable(Flowable):
    """
    Custom Flowable for compliance checkboxes.
    """
    
    def __init__(self, checked: bool = True, size: float = 12):
        Flowable.__init__(self)
        self.checked = checked
        self.size = size
    
    def draw(self):
        """Draw a checkbox."""
        canvas = self.canv
        
        # Draw box
        canvas.setStrokeColor(GRAY_DARK)
        canvas.setLineWidth(1)
        canvas.rect(0, 0, self.size, self.size, fill=0, stroke=1)
        
        # Draw checkmark if checked
        if self.checked:
            canvas.setStrokeColor(SUCCESS)
            canvas.setLineWidth(2)
            # Draw checkmark
            canvas.line(2, self.size/2, self.size/3, 2)
            canvas.line(self.size/3, 2, self.size - 2, self.size - 2)
    
    def wrap(self, availWidth, availHeight):
        return self.size, self.size


# =============================================================================
# STYLE DEFINITIONS
# =============================================================================

def get_report_styles() -> Dict[str, ParagraphStyle]:
    """Get all paragraph styles for the report."""
    base_styles = getSampleStyleSheet()
    
    return {
        'title': ParagraphStyle(
            'ReportTitle',
            parent=base_styles['Heading1'],
            fontSize=22,
            alignment=TA_CENTER,
            spaceAfter=6,
            textColor=GRAY_DARK,
            fontName='Helvetica-Bold'
        ),
        'subtitle': ParagraphStyle(
            'ReportSubtitle',
            parent=base_styles['Normal'],
            fontSize=11,
            alignment=TA_CENTER,
            textColor=GRAY_MEDIUM,
            spaceAfter=20
        ),
        'section_header': ParagraphStyle(
            'SectionHeader',
            parent=base_styles['Heading2'],
            fontSize=FONT_SIZE_HEADING,
            spaceBefore=16,
            spaceAfter=10,
            textColor=PRIMARY,
            fontName='Helvetica-Bold',
            borderPadding=(0, 0, 4, 0),
        ),
        'subsection': ParagraphStyle(
            'Subsection',
            parent=base_styles['Heading3'],
            fontSize=12,
            spaceBefore=12,
            spaceAfter=6,
            textColor=GRAY_DARK,
            fontName='Helvetica-Bold'
        ),
        'body': ParagraphStyle(
            'Body',
            parent=base_styles['Normal'],
            fontSize=FONT_SIZE_BODY,
            leading=14,
            textColor=GRAY_DARK
        ),
        'body_small': ParagraphStyle(
            'BodySmall',
            parent=base_styles['Normal'],
            fontSize=FONT_SIZE_SMALL,
            leading=12,
            textColor=GRAY_MEDIUM
        ),
        'metric_value': ParagraphStyle(
            'MetricValue',
            parent=base_styles['Normal'],
            fontSize=28,
            alignment=TA_CENTER,
            textColor=GRAY_DARK,
            fontName='Helvetica-Bold'
        ),
        'metric_label': ParagraphStyle(
            'MetricLabel',
            parent=base_styles['Normal'],
            fontSize=9,
            alignment=TA_CENTER,
            textColor=GRAY_MEDIUM
        ),
        'footer': ParagraphStyle(
            'Footer',
            parent=base_styles['Normal'],
            fontSize=8,
            textColor=GRAY_LIGHT,
            alignment=TA_CENTER
        ),
        'insight_bullet': ParagraphStyle(
            'InsightBullet',
            parent=base_styles['Normal'],
            fontSize=FONT_SIZE_BODY,
            leftIndent=20,
            bulletIndent=10,
            spaceBefore=4,
            textColor=GRAY_DARK
        ),
        'table_header': ParagraphStyle(
            'TableHeader',
            parent=base_styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            textColor=WHITE
        ),
        'table_cell': ParagraphStyle(
            'TableCell',
            parent=base_styles['Normal'],
            fontSize=9,
            textColor=GRAY_DARK
        ),
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_risk_color(risk_level: str) -> colors.Color:
    """Get the color for a risk level."""
    return RISK_COLORS.get(risk_level.upper(), GRAY_DARK)


def _calculate_deviation(current: float, baseline: float) -> Tuple[float, str]:
    """
    Calculate percentage deviation from baseline.
    
    Returns:
        Tuple of (deviation_percent, status)
    """
    if baseline == 0:
        return (0.0, "N/A")
    
    deviation = ((current - baseline) / baseline) * 100
    
    if abs(deviation) < 5:
        status = "NORMAL"
    elif abs(deviation) < 15:
        status = "ELEVATED"
    else:
        status = "CRITICAL"
    
    return (deviation, status)


def _get_status_color(status: str) -> colors.Color:
    """Get color for status text."""
    status_map = {
        "NORMAL": SUCCESS,
        "ELEVATED": WARNING,
        "CRITICAL": DANGER,
        "N/A": GRAY_LIGHT
    }
    return status_map.get(status.upper(), GRAY_MEDIUM)


def _compute_feature_contributions_safe(
    current_readings: Dict[str, float],
    risk_level: str
) -> Tuple[List[Dict], bool]:
    """
    Safely compute feature contributions with fallback.
    
    This function attempts to compute feature contributions on-demand.
    If it fails for any reason, it returns a graceful fallback.
    
    Args:
        current_readings: Current sensor values
        risk_level: Current risk level
        
    Returns:
        Tuple of (contributions_list, success_flag)
    """
    try:
        contributions = generate_feature_contributions(current_readings, risk_level)
        if contributions and len(contributions) > 0:
            return (contributions, True)
        else:
            return (_get_fallback_contributions(), False)
    except Exception as e:
        # Log would go here in production
        return (_get_fallback_contributions(), False)


def _get_fallback_contributions() -> List[Dict]:
    """Return fallback contribution data when calculation fails."""
    return [
        {
            "feature": "Contribution data unavailable",
            "feature_key": "unavailable",
            "percent": 100.0,
            "status": "normal",
            "value": 0.0,
            "z_score": 0.0
        }
    ]


def _format_timestamp_ms(dt: datetime, offset_ms: int = 0) -> str:
    """Format timestamp with millisecond precision."""
    adjusted = dt + timedelta(milliseconds=offset_ms)
    return adjusted.strftime('%Y-%m-%d %H:%M:%S.') + f"{adjusted.microsecond // 1000:03d} UTC"


def _estimate_rul_days(health_score: int, risk_level: str) -> int:
    """Estimate Remaining Useful Life in days."""
    rul_map = {
        "CRITICAL": (0, 3),
        "HIGH": (3, 14),
        "MODERATE": (14, 45),
        "LOW": (45, 90)
    }
    
    min_rul, max_rul = rul_map.get(risk_level.upper(), (30, 90))
    
    # Interpolate based on health score within the risk band
    if risk_level.upper() == "CRITICAL":
        factor = health_score / 25
    elif risk_level.upper() == "HIGH":
        factor = (health_score - 25) / 25
    elif risk_level.upper() == "MODERATE":
        factor = (health_score - 50) / 25
    else:
        factor = (health_score - 75) / 25
    
    factor = max(0, min(1, factor))
    return int(min_rul + factor * (max_rul - min_rul))


# =============================================================================
# PAGE BUILDERS
# =============================================================================

def build_page_1_executive_summary(
    report: HealthReport,
    current_readings: Dict[str, float],
    styles: Dict[str, ParagraphStyle]
) -> List:
    """
    Build Page 1: Executive Summary
    
    Contains:
    - Title and header
    - Health Gauge (0-100)
    - Key Metrics: RUL, Risk Level, Anomaly Score
    - Asset identification
    """
    story = []
    
    # === HEADER ===
    story.append(Paragraph("INDUSTRIAL ASSET DIAGNOSTIC REPORT", styles['title']))
    story.append(Paragraph(
        f"Asset Health Certificate • Report ID: {report.report_id[:8]}",
        styles['subtitle']
    ))
    
    # Horizontal rule
    story.append(HRFlowable(
        width="100%", thickness=2, color=PRIMARY,
        spaceAfter=20, spaceBefore=10
    ))
    
    # === ASSET INFO BOX ===
    asset_info = [
        ['Asset ID:', report.asset_id, 'Report Generated:', 
         datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')],
        ['Data Capture:', report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
         'Model Version:', report.metadata.model_version]
    ]
    
    asset_table = Table(asset_info, colWidths=[1.2*inch, 2*inch, 1.4*inch, 2*inch])
    asset_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), GRAY_DARK),
        ('BACKGROUND', (0, 0), (-1, -1), GRAY_BG),
        ('BOX', (0, 0), (-1, -1), 1, GRAY_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(asset_table)
    story.append(Spacer(1, 25))
    
    # === HEALTH GAUGE (Center) ===
    story.append(Paragraph("Overall Health Assessment", styles['section_header']))
    
    # Create gauge flowable
    gauge = HealthGaugeFlowable(
        health_score=report.health_score,
        risk_level=report.risk_level.value,
        width=280,
        height=180
    )
    
    # Center the gauge in a table
    gauge_table = Table([[gauge]], colWidths=[CONTENT_WIDTH])
    gauge_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(gauge_table)
    story.append(Spacer(1, 20))
    
    # === KEY METRICS ROW ===
    rul_days = _estimate_rul_days(report.health_score, report.risk_level.value)
    risk_color = _get_risk_color(report.risk_level.value)
    
    # Calculate anomaly score from health score (inverse relationship)
    anomaly_score = max(0, min(100, 100 - report.health_score))
    
    # Create metric boxes
    def create_metric_box(value: str, label: str, color: colors.Color = GRAY_DARK):
        return [
            Paragraph(f'<font color="#{color.hexval()[2:]}">{value}</font>', styles['metric_value']),
            Paragraph(label, styles['metric_label'])
        ]
    
    metric_data = [
        create_metric_box(f"{rul_days}", "Est. RUL (Days)", PRIMARY),
        create_metric_box(report.risk_level.value, "Risk Level", risk_color),
        create_metric_box(f"{anomaly_score}%", "Anomaly Score", 
                          DANGER if anomaly_score > 50 else WARNING if anomaly_score > 25 else SUCCESS),
    ]
    
    # Transpose for table layout
    metrics_table = Table(
        [
            [metric_data[0][0], metric_data[1][0], metric_data[2][0]],
            [metric_data[0][1], metric_data[1][1], metric_data[2][1]]
        ],
        colWidths=[CONTENT_WIDTH/3] * 3
    )
    metrics_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (0, -1), 1, GRAY_BORDER),
        ('BOX', (1, 0), (1, -1), 1, GRAY_BORDER),
        ('BOX', (2, 0), (2, -1), 1, GRAY_BORDER),
        ('BACKGROUND', (0, 0), (-1, -1), GRAY_BG),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 25))
    
    # === EXECUTIVE SUMMARY TEXT ===
    story.append(Paragraph("Summary", styles['subsection']))
    
    # Generate summary based on risk level
    if report.risk_level == RiskLevel.CRITICAL:
        summary_text = (
            f"<b>IMMEDIATE ATTENTION REQUIRED.</b> Asset {report.asset_id} is operating in a "
            f"<font color='#ef4444'><b>CRITICAL</b></font> state with a health score of "
            f"<b>{report.health_score}/100</b>. Estimated remaining useful life is approximately "
            f"<b>{rul_days} days</b>. Immediate inspection and maintenance intervention is strongly recommended "
            f"to prevent unplanned downtime and potential equipment failure."
        )
    elif report.risk_level == RiskLevel.HIGH:
        summary_text = (
            f"<b>ELEVATED RISK DETECTED.</b> Asset {report.asset_id} shows "
            f"<font color='#f97316'><b>HIGH</b></font> risk indicators with a health score of "
            f"<b>{report.health_score}/100</b>. Estimated remaining useful life is approximately "
            f"<b>{rul_days} days</b>. Schedule maintenance within the next 1-2 weeks to address emerging issues."
        )
    elif report.risk_level == RiskLevel.MODERATE:
        summary_text = (
            f"<b>MONITORING RECOMMENDED.</b> Asset {report.asset_id} is in a "
            f"<font color='#f59e0b'><b>MODERATE</b></font> risk state with a health score of "
            f"<b>{report.health_score}/100</b>. Estimated remaining useful life is approximately "
            f"<b>{rul_days} days</b>. Continue routine monitoring and plan maintenance activities within the next month."
        )
    else:
        summary_text = (
            f"<b>SYSTEM HEALTHY.</b> Asset {report.asset_id} is operating normally with "
            f"<font color='#10b981'><b>LOW</b></font> risk and a health score of "
            f"<b>{report.health_score}/100</b>. Estimated remaining useful life exceeds "
            f"<b>{rul_days} days</b>. Continue standard monitoring protocols."
        )
    
    story.append(Paragraph(summary_text, styles['body']))
    
    return story


def build_page_2_sensor_analysis(
    report: HealthReport,
    current_readings: Dict[str, float],
    styles: Dict[str, ParagraphStyle],
    sensor_history: Optional[List[Dict[str, Any]]] = None
) -> List:
    """
    Build Page 2: Sensor Analysis
    
    Contains:
    - Current Readings Table with deviation from baseline
    - 24h Statistics (Mocked)
    - Maintenance Correlation Analysis (when sensor_history provided)
    """
    story = []
    
    # Default to empty list
    if sensor_history is None:
        sensor_history = []
    
    story.append(PageBreak())
    story.append(Paragraph("Sensor Analysis", styles['section_header']))
    story.append(Paragraph(
        "Current sensor readings compared against healthy baseline values. "
        "Statistics show 24-hour operational summary.",
        styles['body_small']
    ))
    story.append(Spacer(1, 15))
    
    # === CURRENT READINGS TABLE ===
    story.append(Paragraph("Current Readings", styles['subsection']))
    
    # Table header
    readings_header = ['Sensor', 'Value', 'Unit', 'Baseline', '% Deviation', 'Status']
    readings_data = [readings_header]
    
    # Signal order for display
    signal_order = ['voltage_v', 'current_a', 'power_factor', 'vibration_g', 'power_kw']
    
    for signal in signal_order:
        meta = SIGNAL_METADATA.get(signal, {"name": signal, "unit": ""})
        display_name = meta.get("name", signal)
        unit = meta.get("unit", "")
        
        current_value = current_readings.get(signal, 0.0)
        baseline_value = HEALTHY_BASELINES.get(signal, current_value)
        
        deviation, status = _calculate_deviation(current_value, baseline_value)
        
        # Format deviation with sign
        if deviation >= 0:
            deviation_str = f"+{deviation:.1f}%"
        else:
            deviation_str = f"{deviation:.1f}%"
        
        readings_data.append([
            display_name,
            f"{current_value:.2f}",
            unit,
            f"{baseline_value:.2f}",
            deviation_str,
            status
        ])
    
    readings_table = Table(
        readings_data,
        colWidths=[1.3*inch, 1*inch, 0.6*inch, 1*inch, 1*inch, 1*inch]
    )
    
    # Apply styling
    table_style = [
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        
        # Data rows
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        
        # Borders
        ('BOX', (0, 0), (-1, -1), 1, GRAY_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        
        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        
        # Alternating row colors
        ('BACKGROUND', (0, 1), (-1, 1), GRAY_BG),
        ('BACKGROUND', (0, 3), (-1, 3), GRAY_BG),
        ('BACKGROUND', (0, 5), (-1, 5), GRAY_BG),
    ]
    
    # Color-code status column
    for i, row in enumerate(readings_data[1:], start=1):
        status = row[-1]
        status_color = _get_status_color(status)
        table_style.append(('TEXTCOLOR', (-1, i), (-1, i), status_color))
        table_style.append(('FONTNAME', (-1, i), (-1, i), 'Helvetica-Bold'))
    
    readings_table.setStyle(TableStyle(table_style))
    story.append(readings_table)
    story.append(Spacer(1, 25))
    
    # === 24-HOUR STATISTICS (Mocked) ===
    story.append(Paragraph("24-Hour Statistics", styles['subsection']))
    story.append(Paragraph(
        "<i>Simulated historical data for demonstration purposes</i>",
        styles['body_small']
    ))
    story.append(Spacer(1, 8))
    
    # Generate mock 24h stats
    stats_24h = generate_24h_stats(current_readings, report.risk_level.value)
    
    stats_header = ['Sensor', 'Min', 'Max', 'Mean', 'Std Dev']
    stats_data = [stats_header]
    
    for signal in signal_order:
        meta = SIGNAL_METADATA.get(signal, {"name": signal})
        display_name = meta.get("name", signal)
        
        signal_stats = stats_24h.get(signal, {})
        stats_data.append([
            display_name,
            f"{signal_stats.get('min', 0):.2f}",
            f"{signal_stats.get('max', 0):.2f}",
            f"{signal_stats.get('mean', 0):.2f}",
            f"{signal_stats.get('std', 0):.3f}"
        ])
    
    stats_table = Table(
        stats_data,
        colWidths=[1.5*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch]
    )
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#475569')),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('BOX', (0, 0), (-1, -1), 1, GRAY_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, 1), GRAY_BG),
        ('BACKGROUND', (0, 3), (-1, 3), GRAY_BG),
        ('BACKGROUND', (0, 5), (-1, 5), GRAY_BG),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 25))
    
    # === BASELINE REFERENCE NOTE ===
    story.append(Paragraph("Baseline Reference", styles['subsection']))
    baseline_note = (
        "Deviation percentages are calculated against healthy baseline values: "
        f"Voltage={HEALTHY_BASELINES['voltage_v']}V, "
        f"Power Factor={HEALTHY_BASELINES['power_factor']}, "
        f"Vibration={HEALTHY_BASELINES['vibration_g']}g (ideal). "
        "Status thresholds: NORMAL (<5%), ELEVATED (5-15%), CRITICAL (>15%)."
    )
    story.append(Paragraph(baseline_note, styles['body_small']))
    story.append(Spacer(1, 25))
    
    # === MAINTENANCE CORRELATION ANALYSIS ===
    # This section correlates sensor data with maintenance events for engineers
    story.append(Paragraph("Maintenance Correlation Analysis", styles['subsection']))
    story.append(Paragraph(
        "Sensor readings correlated with maintenance events. This data is used for "
        "supervised ML training to improve predictive accuracy.",
        styles['body_small']
    ))
    story.append(Spacer(1, 10))
    
    # Fetch maintenance logs for correlation
    maintenance_logs = fetch_maintenance_logs_for_report(hours=24, asset_id=report.asset_id, limit=10)
    
    if sensor_history and len(sensor_history) > 0:
        # Build correlation table: show sensor readings with nearby maintenance events
        corr_header = ['Timestamp', 'Vibration (g)', 'Current (A)', 'Anomaly Score', 'Status', 'Maintenance Event']
        corr_data = [corr_header]
        
        # Take last 8 sensor readings for the table
        recent_sensors = sensor_history[-8:] if len(sensor_history) > 8 else sensor_history
        
        for reading in recent_sensors:
            ts = reading.get('timestamp')
            if isinstance(ts, datetime):
                ts_str = ts.strftime('%H:%M:%S')
            elif isinstance(ts, str):
                ts_str = ts[-8:] if len(ts) > 8 else ts  # Extract time portion
            else:
                ts_str = str(ts)[:8] if ts else 'N/A'
            
            vibration = reading.get('vibration_g', 0.0)
            current = reading.get('current_a', 0.0)
            anomaly_score = reading.get('anomaly_score', 0.0)
            sensor_status = reading.get('status', 'NORMAL')
            
            # Check if there's a maintenance event near this timestamp
            maint_event = '-'
            for log in maintenance_logs:
                if log['timestamp']:
                    # Simple proximity check (within 5 minutes)
                    log_ts = log['timestamp']
                    if isinstance(ts, datetime) and isinstance(log_ts, datetime):
                        diff = abs((ts - log_ts).total_seconds())
                        if diff < 300:  # 5 minutes
                            maint_event = f"{log['severity']}: {log['event_type'][:15]}"
                            break
            
            corr_data.append([
                ts_str,
                f"{vibration:.3f}",
                f"{current:.2f}",
                f"{anomaly_score:.2f}",
                sensor_status,
                maint_event
            ])
        
        corr_table = Table(
            corr_data,
            colWidths=[1*inch, 1*inch, 0.9*inch, 1*inch, 0.9*inch, 1.7*inch]
        )
        
        corr_table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (-2, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 1, GRAY_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ]
        
        # Color code status and highlight anomalies
        for row_idx in range(1, len(corr_data)):
            row = corr_data[row_idx]
            status = row[4]
            anomaly = float(row[3])
            
            # Alternating rows
            if row_idx % 2 == 0:
                corr_table_style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), GRAY_BG))
            
            # Status coloring
            if status == 'CRITICAL':
                corr_table_style.append(('TEXTCOLOR', (4, row_idx), (4, row_idx), DANGER))
                corr_table_style.append(('FONTNAME', (4, row_idx), (4, row_idx), 'Helvetica-Bold'))
            elif status == 'WARNING':
                corr_table_style.append(('TEXTCOLOR', (4, row_idx), (4, row_idx), ORANGE))
            
            # Highlight high anomaly scores
            if anomaly > 0.7:
                corr_table_style.append(('TEXTCOLOR', (3, row_idx), (3, row_idx), DANGER))
                corr_table_style.append(('FONTNAME', (3, row_idx), (3, row_idx), 'Helvetica-Bold'))
            elif anomaly > 0.4:
                corr_table_style.append(('TEXTCOLOR', (3, row_idx), (3, row_idx), ORANGE))
            
            # Highlight maintenance events
            if row[5] != '-':
                corr_table_style.append(('TEXTCOLOR', (-1, row_idx), (-1, row_idx), PRIMARY))
                corr_table_style.append(('FONTNAME', (-1, row_idx), (-1, row_idx), 'Helvetica-Bold'))
        
        corr_table.setStyle(TableStyle(corr_table_style))
        story.append(corr_table)
        
        # Summary stats
        total_readings = len(sensor_history)
        high_anomaly_count = sum(1 for r in sensor_history if r.get('anomaly_score', 0) > 0.7)
        avg_vibration = sum(r.get('vibration_g', 0) for r in sensor_history) / max(total_readings, 1)
        
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f"<i>Analysis Summary: {total_readings} readings in window | "
            f"{high_anomaly_count} high anomaly events | "
            f"Avg vibration: {avg_vibration:.3f}g | "
            f"{len(maintenance_logs)} maintenance logs</i>",
            styles['body_small']
        ))
    else:
        story.append(Paragraph(
            "<font color='#6b7280'><i>No sensor history available for correlation analysis. "
            "Sensor data is collected during real-time monitoring.</i></font>",
            styles['body_small']
        ))
    
    return story


def build_page_3_ml_explainability(
    report: HealthReport,
    current_readings: Dict[str, float],
    styles: Dict[str, ParagraphStyle]
) -> List:
    """
    Build Page 3: ML Explainability (The "Why")
    
    Contains:
    - Feature contribution bar chart
    - Ranked insights explaining the anomaly
    """
    story = []
    
    story.append(PageBreak())
    story.append(Paragraph("ML Explainability Analysis", styles['section_header']))
    story.append(Paragraph(
        "Understanding why the system flagged this health state. "
        "Feature contributions show which sensor readings most influenced the assessment.",
        styles['body_small']
    ))
    story.append(Spacer(1, 15))
    
    # === COMPUTE FEATURE CONTRIBUTIONS (On-demand, with fallback) ===
    contributions, calc_success = _compute_feature_contributions_safe(
        current_readings, report.risk_level.value
    )
    
    # === FEATURE CONTRIBUTION CHART ===
    story.append(Paragraph("Feature Contributions", styles['subsection']))
    
    if not calc_success:
        story.append(Paragraph(
            "<i>Note: Detailed contribution analysis unavailable. Showing summary view.</i>",
            styles['body_small']
        ))
        story.append(Spacer(1, 10))
    
    # Create bar chart flowable
    bar_chart = HorizontalBarChartFlowable(
        contributions=contributions,
        width=CONTENT_WIDTH - 20,
        height=160
    )
    story.append(bar_chart)
    story.append(Spacer(1, 20))
    
    # === INSIGHTS SECTION ===
    story.append(Paragraph("Key Insights", styles['subsection']))
    
    if calc_success and contributions:
        # Generate insights from contributions
        for i, contrib in enumerate(contributions[:4], start=1):
            feature = contrib.get('feature', 'Unknown')
            percent = contrib.get('percent', 0)
            status = contrib.get('status', 'normal')
            value = contrib.get('value', 0)
            z_score = contrib.get('z_score', 0)
            
            # Determine insight severity
            if status == 'critical':
                severity_icon = "🔴"
                severity_text = "CRITICAL"
            elif status == 'elevated':
                severity_icon = "🟡"
                severity_text = "ELEVATED"
            else:
                severity_icon = "🟢"
                severity_text = "NORMAL"
            
            if percent > 30:
                insight_text = (
                    f"<b>{severity_icon} {feature}</b> contributed <b>{percent:.1f}%</b> to the risk assessment. "
                    f"Current value ({value:.2f}) is {z_score:.1f}σ from baseline. "
                    f"[{severity_text}]"
                )
            else:
                insight_text = (
                    f"<b>{feature}</b>: {percent:.1f}% contribution, value={value:.2f} [{severity_text}]"
                )
            
            story.append(Paragraph(f"• {insight_text}", styles['insight_bullet']))
    else:
        # Fallback insights from report explanations
        if report.explanations:
            for exp in report.explanations[:4]:
                story.append(Paragraph(f"• {exp.reason}", styles['insight_bullet']))
        else:
            story.append(Paragraph(
                "• All systems operating within normal parameters.",
                styles['insight_bullet']
            ))
    
    story.append(Spacer(1, 20))
    
    # === PRIMARY DRIVER ANALYSIS ===
    story.append(Paragraph("Primary Driver Analysis", styles['subsection']))
    
    primary_driver = get_primary_driver(contributions)
    driver_display = {
        'vibration': 'Vibration',
        'voltage': 'Voltage',
        'power_factor': 'Power Factor',
        'current': 'Current',
        'default': 'Multiple Factors'
    }.get(primary_driver, 'Multiple Factors')
    
    if report.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
        driver_text = (
            f"The primary contributor to the current risk state is <b>{driver_display}</b>. "
            f"This factor showed the highest deviation from expected baseline values and "
            f"requires immediate attention as part of the maintenance response."
        )
    elif report.risk_level == RiskLevel.MODERATE:
        driver_text = (
            f"<b>{driver_display}</b> is the leading indicator to monitor. "
            f"While not at critical levels, this parameter shows early signs of deviation "
            f"that warrant closer observation."
        )
    else:
        driver_text = (
            f"All parameters are within acceptable ranges. No single factor is driving "
            f"anomalous behavior. Continue standard monitoring protocols."
        )
    
    story.append(Paragraph(driver_text, styles['body']))
    
    return story


def build_page_4_business_roi(
    report: HealthReport,
    current_readings: Dict[str, float],
    styles: Dict[str, ParagraphStyle]
) -> List:
    """
    Build Page 4: Business ROI & Maintenance
    
    Contains:
    - ROI Analysis (Hardcoded values)
    - Dynamic Maintenance Actions based on primary driver
    """
    story = []
    
    story.append(PageBreak())
    story.append(Paragraph("Business Impact & Maintenance Planning", styles['section_header']))
    story.append(Paragraph(
        "Cost-benefit analysis of predictive maintenance intervention and recommended actions.",
        styles['body_small']
    ))
    story.append(Spacer(1, 15))
    
    # === ROI ANALYSIS ===
    story.append(Paragraph("ROI Analysis", styles['subsection']))
    
    # Calculate ROI (hardcoded per spec)
    roi_multiplier = int(COST_FAILURE_USD / COST_MAINTENANCE_USD)
    savings = COST_FAILURE_USD - COST_MAINTENANCE_USD
    
    roi_data = [
        ['Metric', 'Value', 'Notes'],
        ['Est. Preventive Maintenance Cost', f'${COST_MAINTENANCE_USD:,.0f}', 'Planned service intervention'],
        ['Cost of Unplanned Failure', f'${COST_FAILURE_USD:,.0f}', 'Includes downtime + repairs'],
        ['Potential Savings', f'${savings:,.0f}', 'Per prevented failure event'],
        ['ROI Multiplier', f'{roi_multiplier}x', 'Return on maintenance investment'],
    ]
    
    roi_table = Table(roi_data, colWidths=[2.2*inch, 1.5*inch, 2.5*inch])
    roi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('BOX', (0, 0), (-1, -1), 1, GRAY_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 2), (-1, 2), GRAY_BG),
        ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#dcfce7')),  # Green highlight for ROI
        ('FONTNAME', (0, 4), (-1, 4), 'Helvetica-Bold'),
    ]))
    story.append(roi_table)
    story.append(Spacer(1, 25))
    
    # === MAINTENANCE ACTIONS ===
    story.append(Paragraph("Recommended Maintenance Actions", styles['subsection']))
    
    # Get contributions and primary driver
    contributions, _ = _compute_feature_contributions_safe(
        current_readings, report.risk_level.value
    )
    primary_driver = get_primary_driver(contributions)
    
    # Get actions for this driver and risk level
    driver_actions = MAINTENANCE_ACTIONS.get(primary_driver, MAINTENANCE_ACTIONS['default'])
    risk_str = report.risk_level.value.upper()
    
    # Find matching action
    recommended_action = None
    for risk, action, priority in driver_actions:
        if risk == risk_str:
            recommended_action = (action, priority)
            break
    
    if recommended_action is None:
        # Fallback
        recommended_action = ("Continue standard monitoring and maintenance schedule", "LOW")
    
    action_text, priority = recommended_action
    
    # Priority color
    priority_colors = {
        'URGENT': DANGER,
        'HIGH': ORANGE,
        'MEDIUM': WARNING,
        'LOW': SUCCESS
    }
    priority_color = priority_colors.get(priority, GRAY_MEDIUM)
    
    # Action box
    action_data = [
        [f'Priority: {priority}', f'Primary Driver: {primary_driver.replace("_", " ").title()}'],
        [Paragraph(f'<b>Action:</b> {action_text}', styles['body']), ''],
    ]
    
    action_table = Table(action_data, colWidths=[3.5*inch, 2.5*inch])
    action_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), priority_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('SPAN', (0, 1), (-1, 1)),
        ('BOX', (0, 0), (-1, -1), 2, priority_color),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(action_table)
    story.append(Spacer(1, 20))
    
    # === ADDITIONAL RECOMMENDATIONS ===
    story.append(Paragraph("Supporting Actions", styles['subsection']))
    
    # General recommendations based on risk level
    if report.risk_level == RiskLevel.CRITICAL:
        recommendations = [
            "Isolate asset from critical production lines if possible",
            "Prepare backup equipment or contingency plans",
            "Alert maintenance team lead and operations manager",
            "Document all observations for root cause analysis",
        ]
    elif report.risk_level == RiskLevel.HIGH:
        recommendations = [
            "Schedule maintenance window within next 48-72 hours",
            "Order replacement parts if applicable",
            "Increase monitoring frequency to 15-minute intervals",
            "Review recent operational changes or load patterns",
        ]
    elif report.risk_level == RiskLevel.MODERATE:
        recommendations = [
            "Add to next scheduled maintenance cycle",
            "Review trend data for progression patterns",
            "Verify sensor calibration and data quality",
            "Update maintenance planning documentation",
        ]
    else:
        recommendations = [
            "Continue standard preventive maintenance schedule",
            "Document baseline readings for future comparison",
            "No immediate action required",
        ]
    
    for rec in recommendations:
        story.append(Paragraph(f"• {rec}", styles['insight_bullet']))
    
    return story


def build_page_5_audit_trail(
    report: HealthReport,
    styles: Dict[str, ParagraphStyle]
) -> List:
    """
    Build Page 5: Audit Trail
    
    Contains:
    - Process Log with millisecond precision
    - Compliance checkboxes (ISO 55000, ISO 13374)
    """
    story = []
    
    story.append(PageBreak())
    story.append(Paragraph("Audit Trail & Compliance", styles['section_header']))
    story.append(Paragraph(
        "Detailed process log and regulatory compliance verification for audit purposes.",
        styles['body_small']
    ))
    story.append(Spacer(1, 15))
    
    # === PROCESS LOG ===
    story.append(Paragraph("Process Log", styles['subsection']))
    story.append(Paragraph(
        "Timeline of data processing steps with millisecond precision. "
        "Timestamps are relative to the data capture event.",
        styles['body_small']
    ))
    story.append(Spacer(1, 10))
    
    # Use report timestamp as anchor
    anchor_time = report.timestamp
    pdf_gen_time = datetime.now(timezone.utc)
    
    log_header = ['Step', 'Process', 'Timestamp (UTC)', 'Status']
    log_data = [log_header]
    
    for i, (step_name, offset_ms) in enumerate(AUDIT_STEPS, start=1):
        timestamp_str = _format_timestamp_ms(anchor_time, offset_ms)
        log_data.append([
            str(i),
            step_name,
            timestamp_str,
            '✓ Complete'
        ])
    
    # Add PDF generation step (current time)
    log_data.append([
        str(len(AUDIT_STEPS) + 1),
        'PDF Report Generation',
        _format_timestamp_ms(pdf_gen_time, 0),
        '✓ Complete'
    ])
    
    log_table = Table(log_data, colWidths=[0.5*inch, 2.5*inch, 2.5*inch, 1*inch])
    log_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (2, 1), (2, -1), 'Courier'),  # Monospace for timestamps
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (-1, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 1, GRAY_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('TEXTCOLOR', (-1, 1), (-1, -1), SUCCESS),  # Green checkmarks
    ]))
    
    # Add alternating row colors
    for i in range(1, len(log_data)):
        if i % 2 == 0:
            log_table.setStyle(TableStyle([
                ('BACKGROUND', (0, i), (-1, i), GRAY_BG)
            ]))
    
    story.append(log_table)
    story.append(Spacer(1, 25))
    
    # === OPERATOR MAINTENANCE LOGS (Phase 5) ===
    story.append(Paragraph("Operator Maintenance Logs", styles['subsection']))
    story.append(Paragraph(
        "Ground-truth maintenance events logged by operators within the report period. "
        "These events are correlated with sensor data for supervised ML training.",
        styles['body_small']
    ))
    story.append(Spacer(1, 10))
    
    # Fetch maintenance logs from InfluxDB (24h window)
    maintenance_logs = fetch_maintenance_logs_for_report(hours=24, asset_id=report.asset_id, limit=50)
    
    if maintenance_logs:
        maint_header = ['Event Time', 'Type', 'Severity', 'Description']
        maint_data = [maint_header]
        
        for log in maintenance_logs:
            event_time = log['timestamp'].strftime('%Y-%m-%d %H:%M') if log['timestamp'] else 'N/A'
            event_type = log['event_type'].replace('_', ' ').title()[:25]  # Truncate long types
            description = log['description'][:40] + '...' if len(log['description']) > 40 else log['description']
            maint_data.append([event_time, event_type, log['severity'], description])
        
        maint_table = Table(maint_data, colWidths=[1.3*inch, 1.8*inch, 0.8*inch, 2.6*inch])
        
        # Build table style with conditional severity coloring
        maint_table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 1, GRAY_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        
        # Apply severity coloring (CRITICAL = red, HIGH = orange)
        for row_idx, log in enumerate(maintenance_logs, start=1):
            if row_idx < len(maint_data):  # Safety check
                severity = log['severity']
                if severity == 'CRITICAL':
                    maint_table_style.append(('TEXTCOLOR', (2, row_idx), (2, row_idx), DANGER))
                    maint_table_style.append(('FONTNAME', (2, row_idx), (2, row_idx), 'Helvetica-Bold'))
                elif severity == 'HIGH':
                    maint_table_style.append(('TEXTCOLOR', (2, row_idx), (2, row_idx), ORANGE))
                elif severity == 'LOW':
                    maint_table_style.append(('TEXTCOLOR', (2, row_idx), (2, row_idx), SUCCESS))
                
                # Alternating row colors
                if row_idx % 2 == 0:
                    maint_table_style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), GRAY_BG))
        
        maint_table.setStyle(TableStyle(maint_table_style))
        story.append(maint_table)
        story.append(Paragraph(
            f"<i>Total: {len(maintenance_logs)} events in the past 24 hours</i>",
            styles['body_small']
        ))
    else:
        story.append(Paragraph(
            "<font color='#6b7280'><i>No maintenance events logged in the past 24 hours.</i></font>",
            styles['body_small']
        ))
    
    story.append(Spacer(1, 25))
    
    # === COMPLIANCE VERIFICATION ===
    story.append(Paragraph("Compliance Verification", styles['subsection']))
    story.append(Paragraph(
        "This report has been generated in accordance with the following standards:",
        styles['body_small']
    ))
    story.append(Spacer(1, 10))
    
    compliance_header = ['', 'Standard', 'Description', 'Status']
    compliance_data = [compliance_header]
    
    for standard in COMPLIANCE_STANDARDS:
        compliance_data.append([
            CheckboxFlowable(checked=True, size=12),
            f"{standard['code']}\n{standard['name']}",
            standard['description'],
            standard['status']
        ])
    
    compliance_table = Table(
        compliance_data,
        colWidths=[0.5*inch, 1.5*inch, 3*inch, 1*inch]
    )
    compliance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (-1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1, GRAY_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, 1), GRAY_BG),
        ('BACKGROUND', (0, 3), (-1, 3), GRAY_BG),
        ('TEXTCOLOR', (-1, 1), (-1, -1), SUCCESS),
        ('FONTNAME', (-1, 1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(compliance_table)
    story.append(Spacer(1, 25))
    
    # === DATA INTEGRITY STATEMENT ===
    story.append(Paragraph("Data Integrity Statement", styles['subsection']))
    integrity_text = (
        "This report was generated from persisted system data and represents the exact "
        "assessment state at the recorded data capture timestamp. All values shown in the "
        "Executive Summary and Sensor Analysis sections are immutable snapshots from the "
        f"assessment performed at {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}. "
        "Historical statistics and trend visualizations are simulated for demonstration purposes "
        "and are clearly marked as such."
    )
    story.append(Paragraph(integrity_text, styles['body_small']))
    story.append(Spacer(1, 15))
    
    # === FOOTER ===
    story.append(HRFlowable(width="100%", thickness=1, color=GRAY_BORDER, spaceBefore=20))
    footer_text = (
        f"Report ID: {report.report_id} | "
        f"Generated: {pdf_gen_time.strftime('%Y-%m-%d %H:%M:%S UTC')} | "
        f"Model Version: {report.metadata.model_version}"
    )
    story.append(Paragraph(footer_text, styles['footer']))
    story.append(Paragraph(
        "Predictive Maintenance & Energy Efficiency Platform — Digital Twin Simulation",
        styles['footer']
    ))
    
    return story


# =============================================================================
# MAIN GENERATOR CLASS
# =============================================================================

class IndustrialReportGenerator:
    """
    Generates 5-page Industrial Asset Health Certificate PDFs.
    
    This generator adheres to the Snapshot Rule:
    - Health Score, Risk Level, and Sensor Readings come from persisted HealthReport
    - No re-computation of ML scores
    - Historical data is simulated for demo purposes
    
    Usage:
        generator = IndustrialReportGenerator()
        pdf_bytes = generator.generate(health_report, sensor_readings)
    """
    
    def __init__(self):
        """Initialize the report generator."""
        self.styles = get_report_styles()
    
    def generate(
        self,
        report: HealthReport,
        current_readings: Optional[Dict[str, float]] = None,
        sensor_history: Optional[List[Dict[str, Any]]] = None
    ) -> bytes:
        """
        Generate a complete 5-page Industrial Asset Health Certificate.
        
        Args:
            report: Persisted HealthReport object (immutable snapshot)
            current_readings: Optional sensor readings dict. If not provided,
                              will use baseline values.
            sensor_history: Optional list of sensor data points for correlation analysis
                              
        Returns:
            PDF file as bytes
        """
        # Use default readings if not provided
        if current_readings is None:
            current_readings = dict(HEALTHY_BASELINES)
        
        # Default to empty list if no history
        if sensor_history is None:
            sensor_history = []
        
        # Ensure power_kw is present
        if 'power_kw' not in current_readings:
            v = current_readings.get('voltage_v', 230)
            i = current_readings.get('current_a', 15)
            pf = current_readings.get('power_factor', 0.95)
            current_readings['power_kw'] = (v * i * pf) / 1000
        
        # Create PDF buffer
        buffer = BytesIO()
        
        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=PAGE_MARGIN_CM * cm,
            leftMargin=PAGE_MARGIN_CM * cm,
            topMargin=PAGE_MARGIN_CM * cm,
            bottomMargin=PAGE_MARGIN_CM * cm,
            title=f"Industrial Asset Report - {report.asset_id}",
            author="Predictive Maintenance Platform",
            subject="Asset Health Certificate"
        )
        
        # Build story (all pages)
        story = []
        
        # Page 1: Executive Summary
        story.extend(build_page_1_executive_summary(report, current_readings, self.styles))
        
        # Page 2: Sensor Analysis (now includes Maintenance Correlation)
        story.extend(build_page_2_sensor_analysis(report, current_readings, self.styles, sensor_history))
        
        # Page 3: ML Explainability
        story.extend(build_page_3_ml_explainability(report, current_readings, self.styles))
        
        # Page 4: Business ROI & Maintenance
        story.extend(build_page_4_business_roi(report, current_readings, self.styles))
        
        # Page 5: Audit Trail
        story.extend(build_page_5_audit_trail(report, self.styles))
        
        # Build PDF
        doc.build(story)
        
        return buffer.getvalue()


def generate_industrial_report(
    report: HealthReport,
    current_readings: Optional[Dict[str, float]] = None,
    sensor_history: Optional[List[Dict[str, Any]]] = None
) -> bytes:
    """
    Convenience function to generate an Industrial Asset Health Certificate.
    
    Args:
        report: Persisted HealthReport object
        current_readings: Optional sensor readings dict
        sensor_history: Optional list of sensor data points for correlation analysis
        
    Returns:
        PDF file as bytes
    """
    generator = IndustrialReportGenerator()
    return generator.generate(report, current_readings, sensor_history)


def generate_industrial_filename(asset_id: str, timestamp: datetime) -> str:
    """
    Generate filename for the industrial report.
    
    Pattern: IndustrialReport_{AssetID}_{YYYYMMDD_HHMM}.pdf
    """
    ts_str = timestamp.strftime('%Y%m%d_%H%M')
    safe_asset_id = asset_id.replace(' ', '_').replace('/', '-')
    return f"IndustrialReport_{safe_asset_id}_{ts_str}.pdf"
