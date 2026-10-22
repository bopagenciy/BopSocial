"""
Service layer orchestrating preview, persistence, PDF generation, and
lifecycle management of Executive Reports (BS-4G).
"""
import os
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from django.core.files.base import ContentFile
from django.utils import timezone

from social_stats.models import Client, ExecutiveReport
from .builder import build_executive_report_data, compute_source_hash, TEMPLATE_VERSION
from .pdf import generate_report_pdf

logger = logging.getLogger(__name__)


def preview_executive_report(
    client_id: int,
    date_from: date,
    date_to: date,
    platform: Optional[str] = None,
    language: str = "es",
    report_type: str = "EXECUTIVE",
) -> Dict[str, Any]:
    """
    Read-only preview generation.
    Strictly deterministic; zero database persistence.
    """
    return build_executive_report_data(
        client_id=client_id,
        date_from=date_from,
        date_to=date_to,
        platform=platform,
        language=language,
        report_type=report_type,
    )


def save_executive_report(
    client_id: int,
    date_from: date,
    date_to: date,
    platform: Optional[str] = None,
    language: str = "es",
    report_type: str = "EXECUTIVE",
    user: Optional[Any] = None,
    title: Optional[str] = None,
) -> ExecutiveReport:
    """
    Persists structured report data and metadata in ExecutiveReport model.
    Does NOT auto-generate PDF file until requested.
    """
    client = Client.objects.filter(id=client_id, is_active=True).first()
    if not client:
        raise ValueError(f"Active client with ID {client_id} does not exist.")

    report_data = build_executive_report_data(
        client_id=client_id,
        date_from=date_from,
        date_to=date_to,
        platform=platform,
        language=language,
        report_type=report_type,
    )

    clean_platform = (platform or "").lower()
    platform_filter = clean_platform if clean_platform not in ("", "all", "none") else None

    meta = report_data.get("metadata", {})
    report_title = title or report_data.get("cover", {}).get("title", f"Executive Report - {client.company}")

    report = ExecutiveReport.objects.create(
        client=client,
        report_type=report_type,
        period_start=date_from,
        period_end=date_to,
        platform_filter=platform_filter,
        language=language,
        status="GENERATED",
        title=report_title,
        generated_at=timezone.now(),
        generated_by=user if (user and getattr(user, "is_authenticated", False)) else None,
        source_rollup_count=meta.get("source_rollup_count", 0),
        source_signal_count=meta.get("source_signal_count", 0),
        source_hash=meta.get("source_hash", ""),
        report_data=report_data,
        template_version=TEMPLATE_VERSION,
        metadata={
            "created_via": "api",
            "platform_filter": platform_filter,
        },
    )
    return report


def generate_pdf_for_report(report: ExecutiveReport) -> Tuple[ExecutiveReport, bytes]:
    """
    Renders binary PDF from the stored report_data, calculates SHA-256 checksum,
    saves the file to media storage, and updates model fields.
    """
    pdf_bytes, checksum = generate_report_pdf(report.report_data, language=report.language)

    filename = f"executive_report_{report.client_id}_{report.id}_{report.period_start.isoformat()}_{report.period_end.isoformat()}.pdf"
    
    report.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
    report.pdf_checksum = checksum
    report.status = "GENERATED"
    report.save(update_fields=["pdf_file", "pdf_checksum", "status", "updated_at"])

    return report, pdf_bytes


def delete_executive_report(report_id: int, client: Client) -> bool:
    """
    Deletes an ExecutiveReport safely.
    Strictly isolated: does NOT touch underlying snapshots, rollups, or signals.
    """
    report = ExecutiveReport.objects.filter(id=report_id, client=client).first()
    if not report:
        return False

    if report.pdf_file:
        try:
            report.pdf_file.delete(save=False)
        except Exception as e:
            logger.warning(f"Could not delete PDF file for report {report_id}: {e}")

    report.delete()
    return True
