"""
Bop Social Executive Reporting & PDF Export Engine (BS-4G).
"""
from .builder import build_executive_report_data, compute_source_hash, TEMPLATE_VERSION
from .pdf import generate_report_pdf, render_report_html
from .service import (
    preview_executive_report,
    save_executive_report,
    generate_pdf_for_report,
    delete_executive_report,
)
from .templates import BRANDING, get_report_strings

__all__ = [
    "build_executive_report_data",
    "compute_source_hash",
    "generate_report_pdf",
    "render_report_html",
    "preview_executive_report",
    "save_executive_report",
    "generate_pdf_for_report",
    "delete_executive_report",
    "BRANDING",
    "get_report_strings",
    "TEMPLATE_VERSION",
]
