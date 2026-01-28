"""
Chart Components — Bar Charts and Sparklines

Visual representations of feature contributions and historical trends.
Used for ML explainability visualization in the Industrial Report.
"""

from typing import List, Dict, Optional
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import Color, black, white

from backend.reports.constants import (
    SUCCESS,
    WARNING,
    DANGER,
    PRIMARY,
    GRAY_DARK,
    GRAY_LIGHT,
    GRAY_BORDER,
    GRAY_BG,
    FONT_SIZE_SMALL,
    FONT_SIZE_TINY,
)


def draw_horizontal_bar_chart(
    canvas: Canvas,
    x: float,
    y: float,
    contributions: List[Dict],
    width: float = 400,
    bar_height: float = 18,
    spacing: float = 6,
    max_bars: int = 5
) -> float:
    """
    Draw horizontal bar chart for feature contributions.
    
    Each bar shows:
    - Feature name (left-aligned)
    - Colored bar (length proportional to percentage)
    - Percentage value (right of bar)
    
    Bar colors by status:
    - "normal": green
    - "elevated": amber/warning
    - "critical": red
    
    Args:
        canvas: ReportLab canvas
        x, y: Top-left corner of chart area
        contributions: List of dicts with keys: feature, percent, status
        width: Total width available
        bar_height: Height of each bar
        spacing: Vertical space between bars
        max_bars: Maximum number of bars to display
        
    Returns:
        Total height consumed by chart
    """
    canvas.saveState()
    
    # Configuration
    label_width = 120  # Width reserved for feature labels
    bar_area_width = width - label_width - 60  # Space for bar + percentage
    
    # Limit to max_bars
    items = contributions[:max_bars]
    
    current_y = y
    
    for item in items:
        feature = item.get("feature", "Unknown")
        percent = item.get("percent", 0)
        status = item.get("status", "normal")
        
        # Get bar color based on status
        bar_color = _get_status_color(status)
        
        # Draw feature label
        canvas.setFillColor(GRAY_DARK)
        canvas.setFont("Helvetica", FONT_SIZE_SMALL)
        
        # Truncate label if too long
        display_label = feature[:18] + "..." if len(feature) > 18 else feature
        canvas.drawString(x, current_y - bar_height + 4, display_label)
        
        # Calculate bar width
        bar_width = (percent / 100) * bar_area_width
        bar_x = x + label_width
        bar_y = current_y - bar_height
        
        # Draw background bar (light gray)
        canvas.setFillColor(GRAY_BG)
        canvas.rect(bar_x, bar_y, bar_area_width, bar_height - 2, fill=1, stroke=0)
        
        # Draw value bar
        if bar_width > 0:
            canvas.setFillColor(bar_color)
            canvas.rect(bar_x, bar_y, bar_width, bar_height - 2, fill=1, stroke=0)
        
        # Draw border
        canvas.setStrokeColor(GRAY_BORDER)
        canvas.setLineWidth(0.5)
        canvas.rect(bar_x, bar_y, bar_area_width, bar_height - 2, fill=0, stroke=1)
        
        # Draw percentage text
        canvas.setFillColor(GRAY_DARK)
        canvas.setFont("Helvetica-Bold", FONT_SIZE_SMALL)
        pct_text = f"{percent:.1f}%"
        pct_x = bar_x + bar_area_width + 8
        canvas.drawString(pct_x, current_y - bar_height + 4, pct_text)
        
        current_y -= (bar_height + spacing)
    
    canvas.restoreState()
    
    # Return total height consumed
    return len(items) * (bar_height + spacing)


def draw_sparkline(
    canvas: Canvas,
    x: float,
    y: float,
    data: List[float],
    width: float = 100,
    height: float = 25,
    line_color: Optional[Color] = None,
    show_endpoint: bool = True,
    show_baseline: bool = False,
    baseline_value: Optional[float] = None
) -> None:
    """
    Draw a mini trend line (sparkline).
    
    Used for showing 7-day historical trends in a compact format.
    
    Args:
        canvas: ReportLab canvas
        x, y: Bottom-left corner of sparkline area
        data: List of values to plot (oldest first)
        width, height: Dimensions of sparkline
        line_color: Line color (defaults to PRIMARY)
        show_endpoint: Whether to draw dot at last point
        show_baseline: Whether to draw baseline reference line
        baseline_value: Value for baseline line
    """
    if not data or len(data) < 2:
        return
    
    canvas.saveState()
    
    # Use default color if not specified
    if line_color is None:
        line_color = PRIMARY
    
    # Calculate data range
    data_min = min(data)
    data_max = max(data)
    data_range = data_max - data_min
    
    # Prevent division by zero
    if data_range < 0.0001:
        data_range = 1.0
        data_min = data[0] - 0.5
    
    # Calculate x step
    x_step = width / (len(data) - 1)
    
    # Draw baseline if requested
    if show_baseline and baseline_value is not None:
        baseline_y = y + ((baseline_value - data_min) / data_range) * height
        baseline_y = max(y, min(y + height, baseline_y))
        
        canvas.setStrokeColor(GRAY_LIGHT)
        canvas.setLineWidth(0.5)
        canvas.setDash([2, 2])
        canvas.line(x, baseline_y, x + width, baseline_y)
        canvas.setDash([])
    
    # Build path for sparkline
    path = canvas.beginPath()
    
    for i, value in enumerate(data):
        # Normalize value to y position
        normalized = (value - data_min) / data_range
        point_x = x + (i * x_step)
        point_y = y + (normalized * height)
        
        if i == 0:
            path.moveTo(point_x, point_y)
        else:
            path.lineTo(point_x, point_y)
    
    # Draw the line
    canvas.setStrokeColor(line_color)
    canvas.setLineWidth(1.5)
    canvas.drawPath(path, fill=0, stroke=1)
    
    # Draw endpoint marker
    if show_endpoint and data:
        last_value = data[-1]
        last_normalized = (last_value - data_min) / data_range
        last_x = x + width
        last_y = y + (last_normalized * height)
        
        canvas.setFillColor(line_color)
        canvas.circle(last_x, last_y, 3, fill=1, stroke=0)
    
    canvas.restoreState()


def draw_mini_bar(
    canvas: Canvas,
    x: float,
    y: float,
    value: float,
    max_value: float,
    width: float = 60,
    height: float = 12,
    color: Optional[Color] = None
) -> None:
    """
    Draw a mini horizontal bar (for inline use in tables).
    
    Args:
        canvas: ReportLab canvas
        x, y: Bottom-left corner
        value: Current value
        max_value: Maximum value (for scaling)
        width, height: Dimensions
        color: Bar color (defaults to PRIMARY)
    """
    canvas.saveState()
    
    if color is None:
        color = PRIMARY
    
    # Calculate bar fill width
    fill_ratio = min(1.0, value / max_value) if max_value > 0 else 0
    fill_width = fill_ratio * width
    
    # Draw background
    canvas.setFillColor(GRAY_BG)
    canvas.rect(x, y, width, height, fill=1, stroke=0)
    
    # Draw fill
    if fill_width > 0:
        canvas.setFillColor(color)
        canvas.rect(x, y, fill_width, height, fill=1, stroke=0)
    
    # Draw border
    canvas.setStrokeColor(GRAY_BORDER)
    canvas.setLineWidth(0.5)
    canvas.rect(x, y, width, height, fill=0, stroke=1)
    
    canvas.restoreState()


def draw_trend_indicator(
    canvas: Canvas,
    x: float,
    y: float,
    trend: str,
    size: float = 10
) -> None:
    """
    Draw a trend direction indicator (arrow up/down/flat).
    
    Args:
        canvas: ReportLab canvas
        x, y: Center position
        trend: "up", "down", or "flat"
        size: Size of indicator
    """
    canvas.saveState()
    
    if trend == "up":
        # Red up arrow (worsening)
        canvas.setFillColor(DANGER)
        _draw_up_arrow(canvas, x, y, size)
    elif trend == "down":
        # Green down arrow (improving)
        canvas.setFillColor(SUCCESS)
        _draw_down_arrow(canvas, x, y, size)
    else:
        # Gray horizontal line (stable)
        canvas.setStrokeColor(GRAY_LIGHT)
        canvas.setLineWidth(2)
        canvas.line(x - size/2, y, x + size/2, y)
    
    canvas.restoreState()


def _draw_up_arrow(canvas: Canvas, x: float, y: float, size: float) -> None:
    """Draw upward pointing triangle."""
    path = canvas.beginPath()
    path.moveTo(x, y + size/2)  # Top point
    path.lineTo(x - size/2, y - size/2)  # Bottom left
    path.lineTo(x + size/2, y - size/2)  # Bottom right
    path.close()
    canvas.drawPath(path, fill=1, stroke=0)


def _draw_down_arrow(canvas: Canvas, x: float, y: float, size: float) -> None:
    """Draw downward pointing triangle."""
    path = canvas.beginPath()
    path.moveTo(x, y - size/2)  # Bottom point
    path.lineTo(x - size/2, y + size/2)  # Top left
    path.lineTo(x + size/2, y + size/2)  # Top right
    path.close()
    canvas.drawPath(path, fill=1, stroke=0)


def _get_status_color(status: str) -> Color:
    """Get color for contribution status."""
    status_colors = {
        "normal": SUCCESS,
        "elevated": WARNING,
        "critical": DANGER,
    }
    return status_colors.get(status.lower(), GRAY_LIGHT)
