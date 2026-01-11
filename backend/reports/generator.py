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
    
    story.append(Spacer(1, 30))
    
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
    
    # Write to Excel with multiple sheets
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        if explanations_df is not None and not explanations_df.empty:
            explanations_df.to_excel(writer, sheet_name='Insights', index=False)
    
    return buffer.getvalue()
