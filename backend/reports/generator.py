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
"""

from io import BytesIO
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from backend.rules.assessor import HealthReport, RiskLevel


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


def generate_pdf_report(report: HealthReport) -> bytes:
    """
    Generate PDF "Health Certificate" from persisted HealthReport.
    
    The "Snapshot Rule": Uses stored report data, does NOT recompute.
    
    Args:
        report: Persisted HealthReport from Phase 7
        
    Returns:
        PDF file as bytes
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=24,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=colors.HexColor('#1f2937')
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#6b7280'),
        spaceAfter=24
    )
    
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor('#374151')
    )
    
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=11,
        leading=16
    )
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#9ca3af'),
        alignment=TA_CENTER
    )
    
    # Build document content
    story = []
    
    # === HEADER ===
    story.append(Paragraph("ASSET HEALTH CERTIFICATE", title_style))
    story.append(Paragraph(
        f"Industrial Asset Health Assessment Report",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#e5e7eb')))
    story.append(Spacer(1, 20))
    
    # === ASSET INFORMATION BOX ===
    story.append(Paragraph("Asset Information", section_style))
    
    asset_data = [
        ['Asset ID:', report.asset_id],
        ['Report ID:', report.report_id],
        ['Timestamp (UTC):', report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')],
    ]
    
    asset_table = Table(asset_data, colWidths=[2.5*inch, 4*inch])
    asset_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#374151')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1f2937')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(asset_table)
    story.append(Spacer(1, 20))
    
    # === HEALTH SUMMARY BOX ===
    story.append(Paragraph("Health Summary", section_style))
    
    risk_color = RISK_COLORS.get(report.risk_level, colors.gray)
    
    summary_data = [
        ['Health Score:', f"{report.health_score} / 100"],
        ['Risk Level:', report.risk_level.value],
        ['Maintenance Window:', f"{report.maintenance_window_days} days"],
    ]
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 4*inch])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#374151')),
        ('TEXTCOLOR', (1, 1), (1, 1), risk_color),  # Risk level in color
        ('FONTNAME', (1, 1), (1, 1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))
    
    # === INSIGHTS & REASONING ===
    story.append(Paragraph("Insights &amp; Reasoning", section_style))
    
    if report.explanations:
        for exp in report.explanations:
            story.append(Paragraph(f"• {exp.reason}", normal_style))
            if exp.related_features:
                features_text = ", ".join(exp.related_features)
                story.append(Paragraph(
                    f"  <font color='#6b7280'>Related: {features_text}</font>",
                    normal_style
                ))
            story.append(Spacer(1, 6))
    else:
        story.append(Paragraph(
            "✓ All systems operating within normal parameters.",
            normal_style
        ))
    
    story.append(Spacer(1, 20))
    
    # === RECENT MAINTENANCE EVENTS (Phase 5) ===
    story.append(Paragraph("Recent Maintenance Events", section_style))
    
    # Fetch maintenance logs (last 3 High/Critical events)
    all_logs = fetch_maintenance_logs_for_report(hours=168, asset_id=report.asset_id, limit=50)  # 7 days
    critical_logs = [log for log in all_logs if log['severity'] in ('CRITICAL', 'HIGH')][:3]
    
    if critical_logs:
        maintenance_data = [['Event Time', 'Type', 'Severity', 'Description']]
        for log in critical_logs:
            event_time = log['timestamp'].strftime('%Y-%m-%d %H:%M') if log['timestamp'] else 'N/A'
            event_type = log['event_type'].replace('_', ' ').title()
            description = log['description'][:50] + '...' if len(log['description']) > 50 else log['description']
            maintenance_data.append([event_time, event_type, log['severity'], description])
        
        maintenance_table = Table(maintenance_data, colWidths=[1.3*inch, 1.5*inch, 0.8*inch, 3*inch])
        
        # Build style with conditional coloring for CRITICAL
        table_style = [
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ]
        
        # Apply red text to CRITICAL severity cells
        for row_idx, log in enumerate(critical_logs, start=1):
            if log['severity'] == 'CRITICAL':
                table_style.append(('TEXTCOLOR', (2, row_idx), (2, row_idx), colors.HexColor('#ef4444')))
                table_style.append(('FONTNAME', (2, row_idx), (2, row_idx), 'Helvetica-Bold'))
            elif log['severity'] == 'HIGH':
                table_style.append(('TEXTCOLOR', (2, row_idx), (2, row_idx), colors.HexColor('#f97316')))
        
        maintenance_table.setStyle(TableStyle(table_style))
        story.append(maintenance_table)
    else:
        story.append(Paragraph(
            "<font color='#6b7280'>No high-severity maintenance events in the past 7 days.</font>",
            normal_style
        ))
    
    story.append(Spacer(1, 20))
    
    # === FOOTER WITH AUDIT METADATA ===
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e5e7eb')))
    story.append(Spacer(1, 10))
    
    footer_text = (
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | "
        f"Model Version: {report.metadata.model_version}"
    )
    story.append(Paragraph(footer_text, footer_style))
    story.append(Paragraph(
        "This report is generated from persisted system data and represents the assessment at the recorded timestamp.",
        footer_style
    ))
    
    # Build PDF
    doc.build(story)
    
    return buffer.getvalue()


def generate_excel_report(report: HealthReport) -> bytes:
    """
    Generate Excel report from persisted HealthReport.
    
    The "Snapshot Rule": Uses stored report data, does NOT recompute.
    
    Args:
        report: Persisted HealthReport from Phase 7
        
    Returns:
        Excel file as bytes
    """
    buffer = BytesIO()
    
    # Summary data
    summary_data = {
        'Field': [
            'Report ID',
            'Asset ID',
            'Timestamp (UTC)',
            'Health Score',
            'Risk Level',
            'Maintenance Window (Days)',
            'Model Version'
        ],
        'Value': [
            report.report_id,
            report.asset_id,
            report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
            report.health_score,
            report.risk_level.value,
            report.maintenance_window_days,
            report.metadata.model_version
        ]
    }
    
    # Explanations data
    explanations_data = {
        'Reason': [],
        'Related Features': [],
        'Confidence': []
    }
    
    for exp in report.explanations:
        explanations_data['Reason'].append(exp.reason)
        explanations_data['Related Features'].append(', '.join(exp.related_features))
        explanations_data['Confidence'].append(f"{exp.confidence_score:.0%}")
    
    # Create DataFrames
    summary_df = pd.DataFrame(summary_data)
    explanations_df = pd.DataFrame(explanations_data) if explanations_data['Reason'] else None
    
    # === OPERATOR LOGS WORKSHEET (Phase 5) ===
    # Fetch maintenance logs from InfluxDB (24h window)
    maintenance_logs = fetch_maintenance_logs_for_report(hours=24, asset_id=report.asset_id, limit=100)
    
    operator_logs_data = {
        'Event Time (ISO)': [],
        'Asset ID': [],
        'Event Type': [],
        'Severity': [],
        'Description': [],
        'Technician ID': []
    }
    
    for log in maintenance_logs:
        # Use event_time (the user-selected time), formatted as ISO
        event_time = log['timestamp'].isoformat() if log['timestamp'] else ''
        operator_logs_data['Event Time (ISO)'].append(event_time)
        operator_logs_data['Asset ID'].append(log['asset_id'])
        operator_logs_data['Event Type'].append(log['event_type'])
        operator_logs_data['Severity'].append(log['severity'])
        operator_logs_data['Description'].append(log['description'])
        operator_logs_data['Technician ID'].append(log.get('technician_id', 'Operator'))
    
    operator_logs_df = pd.DataFrame(operator_logs_data)
    
    # Write to Excel with multiple sheets
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        if explanations_df is not None and not explanations_df.empty:
            explanations_df.to_excel(writer, sheet_name='Insights', index=False)
        
        # Always include Operator_Logs sheet (may be empty)
        operator_logs_df.to_excel(writer, sheet_name='Operator_Logs', index=False)
        
        # Auto-adjust column widths for Operator_Logs
        worksheet = writer.sheets['Operator_Logs']
        for idx, col in enumerate(operator_logs_df.columns):
            max_len = max(
                operator_logs_df[col].astype(str).map(len).max() if len(operator_logs_df) > 0 else 0,
                len(col)
            ) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_len, 50)
    
    return buffer.getvalue()
