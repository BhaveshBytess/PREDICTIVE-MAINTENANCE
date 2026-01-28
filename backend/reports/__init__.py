"""
Reports Module — Auditable Output Generation (Phase 10)

Public API:
- generate_pdf_report: Create PDF Health Certificate (basic)
- generate_excel_report: Create Excel summary
- generate_filename: Smart filename pattern
- IndustrialReportGenerator: 5-page Industrial Asset Health Certificate
- generate_industrial_report: Convenience function for industrial reports
- generate_industrial_filename: Industrial report filename pattern
"""

from .generator import (
    generate_pdf_report,
    generate_excel_report,
    generate_filename,
)

from .industrial_report import (
    IndustrialReportGenerator,
    generate_industrial_report,
    generate_industrial_filename,
)

__all__ = [
    "generate_pdf_report",
    "generate_excel_report",
    "generate_filename",
    "IndustrialReportGenerator",
    "generate_industrial_report",
    "generate_industrial_filename",
]
