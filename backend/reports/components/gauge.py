"""
Health Gauge Component — Semicircular Visual Gauge

Draws a speedometer-style gauge showing health score 0-100
with color-coded segments and needle indicator.
"""

import math
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import Color, black, white

from backend.reports.constants import (
    GAUGE_SEGMENTS,
    RISK_COLORS,
    GRAY_DARK,
    GRAY_LIGHT,
    GRAY_BORDER,
    PRIMARY,
    FONT_SIZE_TITLE,
    FONT_SIZE_SMALL,
)


def draw_health_gauge(
    canvas: Canvas,
    center_x: float,
    center_y: float,
    radius: float,
    health_score: int,
    risk_level: str
) -> None:
    """
    Draw a semicircular health gauge.
    
    Visual structure:
    - Outer arc with 4 color zones (red→orange→amber→green)
    - Needle pointing to health score position
    - Large score number in center
    - Risk level label below score
    
    Args:
        canvas: ReportLab canvas to draw on
        center_x, center_y: Center point of gauge
        radius: Outer radius of gauge arc
        health_score: Value 0-100 to display
        risk_level: Current risk level for accent color
    """
    canvas.saveState()
    
    # Configuration
    arc_width = radius * 0.15  # Width of the colored arc
    inner_radius = radius - arc_width
    
    # Draw background arc (light gray) using path
    path = canvas.beginPath()
    path.arc(
        center_x - radius + arc_width/2,
        center_y - radius + arc_width/2,
        center_x + radius - arc_width/2,
        center_y + radius - arc_width/2,
        startAng=0,
        extent=180
    )
    canvas.setStrokeColor(GRAY_BORDER)
    canvas.setLineWidth(arc_width)
    canvas.drawPath(path, stroke=1, fill=0)
    
    # Draw colored segments
    for start_val, end_val, color in GAUGE_SEGMENTS:
        # Convert health values to angles (0=left at 180°, 100=right at 0°)
        start_angle = 180 - (start_val / 100 * 180)
        end_angle = 180 - (end_val / 100 * 180)
        extent = start_angle - end_angle  # Negative because we go clockwise
        
        canvas.setStrokeColor(color)
        canvas.setLineWidth(arc_width - 2)
        
        # Draw segment arc
        _draw_arc_segment(
            canvas,
            center_x,
            center_y,
            radius - arc_width/2,
            end_angle,  # Start from end because extent is positive
            extent
        )
    
    # Draw needle
    _draw_needle(canvas, center_x, center_y, inner_radius * 0.85, health_score, risk_level)
    
    # Draw center circle (white background for score)
    center_circle_radius = radius * 0.35
    canvas.setFillColor(white)
    canvas.setStrokeColor(GRAY_BORDER)
    canvas.setLineWidth(2)
    canvas.circle(center_x, center_y, center_circle_radius, fill=1, stroke=1)
    
    # Draw health score text
    canvas.setFillColor(GRAY_DARK)
    canvas.setFont("Helvetica-Bold", FONT_SIZE_TITLE)
    score_text = str(health_score)
    text_width = canvas.stringWidth(score_text, "Helvetica-Bold", FONT_SIZE_TITLE)
    canvas.drawString(center_x - text_width/2, center_y + 5, score_text)
    
    # Draw "/ 100" below score
    canvas.setFont("Helvetica", FONT_SIZE_SMALL)
    canvas.setFillColor(GRAY_LIGHT)
    sub_text = "/ 100"
    sub_width = canvas.stringWidth(sub_text, "Helvetica", FONT_SIZE_SMALL)
    canvas.drawString(center_x - sub_width/2, center_y - 12, sub_text)
    
    # Draw risk level label below gauge
    risk_color = RISK_COLORS.get(risk_level, GRAY_DARK)
    canvas.setFillColor(risk_color)
    canvas.setFont("Helvetica-Bold", FONT_SIZE_SMALL + 2)
    risk_text = f"Risk: {risk_level}"
    risk_width = canvas.stringWidth(risk_text, "Helvetica-Bold", FONT_SIZE_SMALL + 2)
    canvas.drawString(center_x - risk_width/2, center_y - radius - 20, risk_text)
    
    # Draw scale labels (0, 25, 50, 75, 100)
    _draw_scale_labels(canvas, center_x, center_y, radius + 10)
    
    canvas.restoreState()


def _draw_arc_segment(
    canvas: Canvas,
    center_x: float,
    center_y: float,
    radius: float,
    start_angle: float,
    extent: float
) -> None:
    """Draw an arc segment."""
    path = canvas.beginPath()
    path.arc(
        center_x - radius,
        center_y - radius,
        center_x + radius,
        center_y + radius,
        startAng=start_angle,
        extent=extent
    )
    canvas.drawPath(path, stroke=1, fill=0)


def _draw_needle(
    canvas: Canvas,
    center_x: float,
    center_y: float,
    length: float,
    health_score: int,
    risk_level: str
) -> None:
    """Draw the gauge needle pointing to the health score."""
    # Convert health score to angle
    # 0 = 180° (left), 100 = 0° (right)
    angle_deg = 180 - (health_score / 100 * 180)
    angle_rad = math.radians(angle_deg)
    
    # Calculate needle endpoint
    end_x = center_x + length * math.cos(angle_rad)
    end_y = center_y + length * math.sin(angle_rad)
    
    # Draw needle line
    needle_color = RISK_COLORS.get(risk_level, GRAY_DARK)
    canvas.setStrokeColor(needle_color)
    canvas.setLineWidth(3)
    canvas.line(center_x, center_y, end_x, end_y)
    
    # Draw needle base circle
    canvas.setFillColor(needle_color)
    canvas.circle(center_x, center_y, 6, fill=1, stroke=0)
    
    # Draw arrowhead at needle tip
    _draw_arrowhead(canvas, end_x, end_y, angle_rad, needle_color)


def _draw_arrowhead(
    canvas: Canvas,
    tip_x: float,
    tip_y: float,
    angle_rad: float,
    color: Color
) -> None:
    """Draw arrowhead at needle tip."""
    arrow_size = 8
    
    # Calculate arrowhead points
    left_angle = angle_rad + math.radians(150)
    right_angle = angle_rad - math.radians(150)
    
    left_x = tip_x + arrow_size * math.cos(left_angle)
    left_y = tip_y + arrow_size * math.sin(left_angle)
    right_x = tip_x + arrow_size * math.cos(right_angle)
    right_y = tip_y + arrow_size * math.sin(right_angle)
    
    # Draw filled triangle
    path = canvas.beginPath()
    path.moveTo(tip_x, tip_y)
    path.lineTo(left_x, left_y)
    path.lineTo(right_x, right_y)
    path.close()
    
    canvas.setFillColor(color)
    canvas.drawPath(path, fill=1, stroke=0)


def _draw_scale_labels(
    canvas: Canvas,
    center_x: float,
    center_y: float,
    radius: float
) -> None:
    """Draw scale labels around the gauge (0, 25, 50, 75, 100)."""
    canvas.setFillColor(GRAY_LIGHT)
    canvas.setFont("Helvetica", FONT_SIZE_SMALL - 1)
    
    labels = [0, 25, 50, 75, 100]
    
    for value in labels:
        # Convert value to angle
        angle_deg = 180 - (value / 100 * 180)
        angle_rad = math.radians(angle_deg)
        
        # Calculate label position (slightly outside the arc)
        label_radius = radius + 5
        label_x = center_x + label_radius * math.cos(angle_rad)
        label_y = center_y + label_radius * math.sin(angle_rad)
        
        # Adjust for text centering
        text = str(value)
        text_width = canvas.stringWidth(text, "Helvetica", FONT_SIZE_SMALL - 1)
        
        # Offset based on position
        if value == 0:
            label_x -= text_width + 2
        elif value == 100:
            label_x += 2
        else:
            label_x -= text_width / 2
        
        if value == 50:
            label_y += 8
        
        canvas.drawString(label_x, label_y - 3, text)
