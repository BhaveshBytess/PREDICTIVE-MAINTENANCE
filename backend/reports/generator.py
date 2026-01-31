"""
Reporting Layer — PDF and Excel Report Generation

Produces auditable outputs from persisted Health Reports.
The "Snapshot Rule": Reports use stored data, NOT recomputed values.

Constraints:
- Use persisted HealthReport (no recalculation)
- Include maintenance_window_days, risk_level, explanations
- Audit metadata: asset_id, timestamp (UTC), model_version
- Smart filenames: Report_{AssetID}_{YYYYMMDD_HHMM}.pdf
- PDF as formal "Health Certificate" format

Phase 5 Overhaul:
- Excel: Multi-sheet (Summary, Operator_Logs, Raw_Sensor_Data)
- Small PDF: Executive summary for Plant Managers (Health Grade A/B/C, KPIs, last 2 logs)
- Large PDF: Technical report for Engineers (Maintenance Correlation Analysis)
"""

import logging
from io import BytesIO
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, ListFlowable, ListItem, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from backend.rules.assessor import HealthReport, RiskLevel
from backend.database import db


logger = logging.getLogger(__name__)


# Risk level colors for visual formatting
RISK_COLORS = {
    RiskLevel.LOW: colors.HexColor('#10b981'),      # Green
    RiskLevel.MODERATE: colors.HexColor('#f59e0b'), # Amber
    RiskLevel.HIGH: colors.HexColor('#f97316'),     # Orange
    RiskLevel.CRITICAL: colors.HexColor('#ef4444'), # Red
}

# Severity colors for maintenance logs
SEVERITY_COLORS = {
    'CRITICAL': colors.HexColor('#ef4444'),  # Red
    'HIGH': colors.HexColor('#f97316'),      # Orange
    'MEDIUM': colors.HexColor('#f59e0b'),    # Amber
    'LOW': colors.HexColor('#10b981'),       # Green
}

# Health Grade mapping (A/B/C/D/F based on health score)
def get_health_grade(score: int) -> tuple:
    """
    Convert health score to letter grade for executive reports.
    
    Returns: (grade, color, description)
    """
    if score >= 90:
        return ('A', colors.HexColor('#10b981'), 'Excellent')
    elif score >= 75:
        return ('B', colors.HexColor('#22c55e'), 'Good')
    elif score >= 50:
        return ('C', colors.HexColor('#f59e0b'), 'Fair')
    elif score >= 25:
        return ('D', colors.HexColor('#f97316'), 'Poor')
    else:
        return ('F', colors.HexColor('#ef4444'), 'Critical')


def fetch_maintenance_logs_for_report(
    hours: int = 24,
    asset_id: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Fetch maintenance logs from InfluxDB for report generation.
    
    Uses the log's event_time (the time selected in UI), NOT created_at.
    This represents the actual machine event time.
    
    Args:
        hours: Look back period
        asset_id: Optional filter by asset
        limit: Maximum records
        
    Returns:
        List of log dicts with: timestamp, asset_id, event_type, severity, description
    """
    asset_filter = f'|> filter(fn: (r) => r["asset_id"] == "{asset_id}")' if asset_id else ""
    
    flux_query = f'''
        from(bucket: "sensor_data")
        |> range(start: -{hours}h)
        |> filter(fn: (r) => r["_measurement"] == "maintenance_logs")
        |> filter(fn: (r) => r["_field"] == "description")
        {asset_filter}
        |> sort(columns: ["_time"], desc: true)
        |> limit(n: {limit})
    '''
    
    try:
        results = db.query_data(flux_query)
        
        logs = []
        for record in results:
            logs.append({
                'timestamp': record.get('time'),
                'asset_id': record.get('asset_id', 'Unknown'),
                'event_type': record.get('event_type', 'UNKNOWN'),
                'severity': record.get('severity', 'MEDIUM'),
                'description': record.get('value', ''),
                'technician_id': record.get('technician_id', 'Operator')  # Default value
            })
        
        logger.info(f"📋 Fetched {len(logs)} maintenance logs for report")
        return logs
        
    except Exception as e:
        logger.warning(f"Failed to fetch maintenance logs for report: {e}")
        return []


def generate_filename(asset_id: str, timestamp: datetime, extension: str) -> str:
    """
    Generate smart filename following pattern: Report_{AssetID}_{YYYYMMDD_HHMM}.ext
    """
    ts_str = timestamp.strftime('%Y%m%d_%H%M')
    safe_asset_id = asset_id.replace(' ', '_').replace('/', '-')
    return f"Report_{safe_asset_id}_{ts_str}.{extension}"


def generate_pdf_report(
    report: HealthReport,
    sensor_history: Optional[List[Dict[str, Any]]] = None
) -> bytes:
    """
    Generate Executive Summary PDF for Plant Managers.
    
    A high-impact 1-pager with:
    - Header: Machine ID + Overall Health Grade (A/B/C)
    - KPI Box: Max Vibration, Total Run Time, Critical Alerts count
    - Maintenance Snapshot: Last 2 Operator Logs
    
    Args:
        report: Persisted HealthReport
        sensor_history: Optional list of sensor readings for metrics
        
    Returns:
        PDF file as bytes
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=28,
        alignment=TA_CENTER,
        spaceAfter=6,
        textColor=colors.HexColor('#1f2937')
    )
    
    grade_style = ParagraphStyle(
        'Grade',
        parent=styles['Normal'],
        fontSize=72,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#10b981'),
        fontName='Helvetica-Bold'
    )
    
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor('#374151')
    )
    
    kpi_label_style = ParagraphStyle(
        'KPILabel',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#6b7280'),
        alignment=TA_CENTER
    )
    
    kpi_value_style = ParagraphStyle(
        'KPIValue',
        parent=styles['Normal'],
        fontSize=24,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1f2937'),
        alignment=TA_CENTER
    )
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#9ca3af'),
        alignment=TA_CENTER
    )
    
    # === Calculate KPIs from sensor history ===
    max_vibration = 0.0
    total_runtime_hours = 0.0
    critical_alerts = 0
    
    if sensor_history and len(sensor_history) > 0:
        # Max vibration
        vibrations = [r.get('vibration_g', 0) for r in sensor_history if r.get('vibration_g')]
        max_vibration = max(vibrations) if vibrations else 0.0
        
        # Estimate runtime (assuming 1 reading per second or calculate from timestamps)
        total_runtime_hours = len(sensor_history) / 3600  # Rough estimate
        
        # Count anomalies/alerts
        critical_alerts = sum(1 for r in sensor_history if r.get('is_anomaly', False))
    
    # Fetch maintenance logs
    all_logs = fetch_maintenance_logs_for_report(hours=168, asset_id=report.asset_id, limit=50)
    critical_count = len([log for log in all_logs if log['severity'] == 'CRITICAL'])
    
    # Build document
    story = []
    
    # === HEADER WITH HEALTH GRADE ===
    grade, grade_color, grade_desc = get_health_grade(report.health_score)
    
    story.append(Paragraph("EXECUTIVE HEALTH SUMMARY", title_style))
    story.append(Spacer(1, 10))
    
    # Asset ID and timestamp row
    header_data = [[
        f"Machine: {report.asset_id}",
        f"Report Date: {report.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"
    ]]
    header_table = Table(header_data, colWidths=[3.5*inch, 3.5*inch])
    header_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#6b7280')),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(header_table)
    
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#e5e7eb')))
    story.append(Spacer(1, 20))
    
    # === LARGE HEALTH GRADE BOX ===
    grade_box_data = [[
        Paragraph(f"<font color='{grade_color.hexval()}'>{grade}</font>", 
                  ParagraphStyle('GradeLetter', fontSize=80, alignment=TA_CENTER, fontName='Helvetica-Bold')),
    ], [
        Paragraph(f"{grade_desc} Condition", 
                  ParagraphStyle('GradeDesc', fontSize=14, alignment=TA_CENTER, textColor=colors.HexColor('#6b7280')))
    ], [
        Paragraph(f"Health Score: {report.health_score}/100", 
                  ParagraphStyle('Score', fontSize=12, alignment=TA_CENTER, textColor=colors.HexColor('#374151')))
    ]]
    
    grade_table = Table(grade_box_data, colWidths=[4*inch])
    grade_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
        ('BOX', (0, 0), (-1, -1), 2, grade_color),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    ]))
    
    # Center the grade box
    grade_container = Table([[grade_table]], colWidths=[7*inch])
    grade_container.setStyle(TableStyle([('ALIGN', (0, 0), (0, 0), 'CENTER')]))
    story.append(grade_container)
    story.append(Spacer(1, 25))
    
    # === KEY PERFORMANCE INDICATORS ===
    story.append(Paragraph("Key Performance Indicators", section_style))
    story.append(Spacer(1, 10))
    
    kpi_data = [[
        Paragraph(f"{max_vibration:.3f} g", kpi_value_style),
        Paragraph(f"{report.maintenance_window_days}", kpi_value_style),
        Paragraph(f"{critical_alerts + critical_count}", kpi_value_style),
        Paragraph(f"{report.risk_level.value}", 
                  ParagraphStyle('Risk', fontSize=20, fontName='Helvetica-Bold', 
                                alignment=TA_CENTER, textColor=RISK_COLORS.get(report.risk_level, colors.gray)))
    ], [
        Paragraph("Max Vibration", kpi_label_style),
        Paragraph("Days to Maintenance", kpi_label_style),
        Paragraph("Critical Alerts", kpi_label_style),
        Paragraph("Risk Level", kpi_label_style)
    ]]
    
    kpi_table = Table(kpi_data, colWidths=[1.7*inch, 1.7*inch, 1.7*inch, 1.7*inch])
    kpi_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
        ('INNERGRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 25))
    
    # === MAINTENANCE SNAPSHOT (Last 2 logs) ===
    story.append(Paragraph("Recent Maintenance Activity", section_style))
    
    last_2_logs = all_logs[:2]  # Already sorted by time desc
    
    if last_2_logs:
        maint_data = [['Event Time', 'Type', 'Severity', 'Technician Note']]
        for log in last_2_logs:
            event_time = log['timestamp'].strftime('%Y-%m-%d %H:%M') if log['timestamp'] else 'N/A'
            event_type = log['event_type'].replace('_', ' ').title()[:20]
            note = log['description'][:40] + '...' if len(log['description']) > 40 else log['description']
            maint_data.append([event_time, event_type, log['severity'], note])
        
        maint_table = Table(maint_data, colWidths=[1.4*inch, 1.6*inch, 0.9*inch, 3*inch])
        
        table_style = [
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]
        
        # Color severity cells
        for row_idx, log in enumerate(last_2_logs, start=1):
            sev_color = SEVERITY_COLORS.get(log['severity'], colors.gray)
            table_style.append(('TEXTCOLOR', (2, row_idx), (2, row_idx), sev_color))
            table_style.append(('FONTNAME', (2, row_idx), (2, row_idx), 'Helvetica-Bold'))
        
        maint_table.setStyle(TableStyle(table_style))
        story.append(maint_table)
    else:
        story.append(Paragraph(
            "<font color='#6b7280'><i>No maintenance events recorded in the past 7 days.</i></font>",
            styles['Normal']
        ))
    
    story.append(Spacer(1, 30))
    
    # === FOOTER ===
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e5e7eb')))
    story.append(Spacer(1, 8))
    
    footer_text = (
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | "
        f"Model: {report.metadata.model_version} | "
        f"Report ID: {report.report_id[:8]}"
    )
    story.append(Paragraph(footer_text, footer_style))
    story.append(Paragraph(
        "Executive Summary Report — For Plant Management Review",
        footer_style
    ))
    
    # Build PDF
    doc.build(story)
    
    return buffer.getvalue()


def generate_excel_report(
    report: HealthReport,
    sensor_history: Optional[List[Dict[str, Any]]] = None
) -> bytes:
    """
    Generate Multi-Sheet Excel Report for Analysts.
    
    Sheets:
    1. Summary: High-level metrics (Total Duration, Max Vibration, Total Anomalies)
    2. Operator_Logs: Human ground truth data
    3. Raw_Sensor_Data: Complete timeline of sensor readings
    
    Args:
        report: Persisted HealthReport
        sensor_history: List of sensor readings for raw data export
        
    Returns:
        Excel file as bytes
    """
    buffer = BytesIO()
    
    # === Calculate metrics from sensor history ===
    total_readings = len(sensor_history) if sensor_history else 0
    total_duration_hours = total_readings / 3600 if total_readings > 0 else 0  # Assuming 1 reading/sec
    max_vibration = 0.0
    max_current = 0.0
    total_anomalies = 0
    
    if sensor_history and len(sensor_history) > 0:
        vibrations = [r.get('vibration_g', 0) for r in sensor_history if r.get('vibration_g') is not None]
        max_vibration = max(vibrations) if vibrations else 0.0
        
        currents = [r.get('current_a', 0) for r in sensor_history if r.get('current_a') is not None]
        max_current = max(currents) if currents else 0.0
        
        total_anomalies = sum(1 for r in sensor_history if r.get('is_anomaly', False))
    
    # === SHEET 1: SUMMARY ===
    summary_data = {
        'Metric': [
            'Report ID',
            'Asset ID',
            'Report Generated (UTC)',
            'Health Score',
            'Health Grade',
            'Risk Level',
            'Maintenance Window (Days)',
            'Model Version',
            '---',
            'Total Data Points',
            'Session Duration (Hours)',
            'Max Vibration (g)',
            'Max Current (A)',
            'Total Anomalies Detected',
        ],
        'Value': [
            report.report_id,
            report.asset_id,
            report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
            f"{report.health_score}/100",
            get_health_grade(report.health_score)[0],  # Just the grade letter
            report.risk_level.value,
            report.maintenance_window_days,
            report.metadata.model_version,
            '---',
            total_readings,
            f"{total_duration_hours:.2f}",
            f"{max_vibration:.4f}",
            f"{max_current:.2f}",
            total_anomalies,
        ]
    }
    summary_df = pd.DataFrame(summary_data)
    
    # === SHEET 2: OPERATOR LOGS (Ground Truth) ===
    maintenance_logs = fetch_maintenance_logs_for_report(hours=168, asset_id=report.asset_id, limit=100)
    
    operator_logs_data = {
        'Event Time': [],
        'Type': [],
        'Severity': [],
        'Technician Note': []
    }
    
    for log in maintenance_logs:
        event_time = log['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if log['timestamp'] else ''
        operator_logs_data['Event Time'].append(event_time)
        operator_logs_data['Type'].append(log['event_type'].replace('_', ' ').title())
        operator_logs_data['Severity'].append(log['severity'])
        operator_logs_data['Technician Note'].append(log['description'])
    
    operator_logs_df = pd.DataFrame(operator_logs_data)
    
    # === SHEET 3: RAW SENSOR DATA ===
    raw_sensor_data = {
        'Timestamp': [],
        'Vibration (g)': [],
        'Current (A)': [],
        'Voltage (V)': [],
        'Power Factor': [],
        'Anomaly_Score': [],
        'Status': []
    }
    
    if sensor_history:
        for reading in sensor_history:
            ts = reading.get('timestamp')
            if isinstance(ts, datetime):
                raw_sensor_data['Timestamp'].append(ts.strftime('%Y-%m-%d %H:%M:%S'))
            elif isinstance(ts, str):
                raw_sensor_data['Timestamp'].append(ts)
            else:
                raw_sensor_data['Timestamp'].append(str(ts) if ts else '')
            
            raw_sensor_data['Vibration (g)'].append(reading.get('vibration_g', ''))
            raw_sensor_data['Current (A)'].append(reading.get('current_a', ''))
            raw_sensor_data['Voltage (V)'].append(reading.get('voltage_v', ''))
            raw_sensor_data['Power Factor'].append(reading.get('power_factor', ''))
            raw_sensor_data['Anomaly_Score'].append(reading.get('anomaly_score', ''))
            
            is_anomaly = reading.get('is_anomaly', False)
            raw_sensor_data['Status'].append('ANOMALY' if is_anomaly else 'NORMAL')
    
    raw_sensor_df = pd.DataFrame(raw_sensor_data)
    
    # === Write all sheets ===
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        # Sheet 1: Summary
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        ws_summary = writer.sheets['Summary']
        ws_summary.column_dimensions['A'].width = 30
        ws_summary.column_dimensions['B'].width = 40
        
        # Sheet 2: Operator_Logs
        operator_logs_df.to_excel(writer, sheet_name='Operator_Logs', index=False)
        ws_logs = writer.sheets['Operator_Logs']
        ws_logs.column_dimensions['A'].width = 20
        ws_logs.column_dimensions['B'].width = 25
        ws_logs.column_dimensions['C'].width = 12
        ws_logs.column_dimensions['D'].width = 50
        
        # Sheet 3: Raw_Sensor_Data
        raw_sensor_df.to_excel(writer, sheet_name='Raw_Sensor_Data', index=False)
        ws_raw = writer.sheets['Raw_Sensor_Data']
        ws_raw.column_dimensions['A'].width = 20
        for col in ['B', 'C', 'D', 'E', 'F', 'G']:
            ws_raw.column_dimensions[col].width = 15
    
    return buffer.getvalue()
