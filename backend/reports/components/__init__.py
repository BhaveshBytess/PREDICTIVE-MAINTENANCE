"""
Report Components — Visual Building Blocks for PDF Generation

This package provides modular visual components for the Industrial Report:
- gauge: Health score gauge visualization
- charts: Bar charts and sparklines
"""

from backend.reports.components.gauge import draw_health_gauge
from backend.reports.components.charts import draw_horizontal_bar_chart, draw_sparkline

__all__ = [
    # Gauge
    "draw_health_gauge",
    # Charts
    "draw_horizontal_bar_chart",
    "draw_sparkline",
]
