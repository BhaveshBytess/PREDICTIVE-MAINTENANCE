"""
Reports Module — Auditable Output Generation (Phase 10)

Public API:
- generate_pdf_report: Create PDF Health Certificate
- generate_excel_report: Create Excel summary
- generate_filename: Smart filename pattern
"""

from .generator import (
    generate_pdf_report,
    generate_excel_report,
    generate_filename,
)

__all__ = [
    "generate_pdf_report",
    "generate_excel_report",
    "generate_filename",
]
