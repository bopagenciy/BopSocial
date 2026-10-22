"""
Service layer for Grounded AI Executive Narrative.
Orchestrates context extraction, provider execution, deterministic validation,
persistence, and stale narrative detection.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from django.utils import timezone
from social_stats.models import ExecutiveNarrative, ExecutiveReport

from .context import build_grounded_narrative_context, compute_context_hash
from .prompts import PROMPT_VERSION
from .providers import get_narrative_provider
from .schemas import CONTEXT_SCHEMA_VERSION
from .validator import NarrativeValidator

logger = logging.getLogger(__name__)


def preview_narrative(
    report: ExecutiveReport,
    language: Optional[str] = None,
    style: str = "EXECUTIVE",
    provider_name: str = "fake",
    mock_mode: str = "VALID",
    **kwargs
) -> Dict[str, Any]:
    """
    Generates a deterministic preview of the AI narrative without persisting to DB.
    Guarantees 0 database rows are created.
    """
    lang = language or getattr(report, "language", "es") or "es"
    context = build_grounded_narrative_context(report)
    context_hash = compute_context_hash(context)

    provider = get_narrative_provider(provider_name, mock_mode=mock_mode)
    result = provider.generate(
        context=context,
        language=lang,
        style=style,
        mock_mode=mock_mode,
        **kwargs
    )

    is_valid, val_summary = NarrativeValidator.validate(result.parsed_json, context)

    return {
        "report_id": report.id,
        "language": lang,
        "style": style,
        "provider": provider_name,
        "model_name": result.model_name,
        "prompt_version": PROMPT_VERSION,
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "source_hash": report.source_hash,
        "context_hash": context_hash,
        "context": context,
        "narrative": result.parsed_json,
        "raw_response": result.raw_response,
        "validation_status": val_summary["status"],
        "validation_results": val_summary["results"],
        "validation_errors": val_summary["errors"],
        "is_valid": is_valid,
        "token_usage": result.token_usage,
        "metadata": result.metadata,
    }


def generate_and_save_narrative(
    report: ExecutiveReport,
    user=None,
    language: Optional[str] = None,
    style: str = "EXECUTIVE",
    provider_name: str = "fake",
    mock_mode: str = "VALID",
    **kwargs
) -> ExecutiveReport:
    """
    Generates and persists an ExecutiveNarrative instance.
    Sets status to VALIDATED only if all validation gates pass; otherwise REJECTED or FAILED.
    """
    lang = language or getattr(report, "language", "es") or "es"
    context = build_grounded_narrative_context(report)
    context_hash = compute_context_hash(context)

    provider = get_narrative_provider(provider_name, mock_mode=mock_mode)
    result = provider.generate(
        context=context,
        language=lang,
        style=style,
        mock_mode=mock_mode,
        **kwargs
    )

    is_valid, val_summary = NarrativeValidator.validate(result.parsed_json, context)

    if not result.parsed_json:
        final_status = "FAILED"
    elif is_valid:
        final_status = "VALIDATED"
    else:
        final_status = "REJECTED"

    rendered_text = ""
    if result.parsed_json:
        sections = []
        for sec in ["executive_summary", "performance_observations"]:
            items = result.parsed_json.get(sec, [])
            if items:
                sections.append("\n".join(items))
        rendered_text = "\n\n".join(sections)

    narrative = ExecutiveNarrative.objects.create(
        client=report.client,
        executive_report=report,
        language=lang,
        status=final_status,
        provider=provider_name,
        model_name=result.model_name,
        prompt_version=PROMPT_VERSION,
        context_schema_version=CONTEXT_SCHEMA_VERSION,
        source_hash=report.source_hash,
        context_hash=context_hash,
        narrative_json=result.parsed_json,
        rendered_text=rendered_text,
        validation_status=val_summary["status"],
        validation_results=val_summary,
        created_by=user,
        generated_at=timezone.now(),
        metadata={
            "token_usage": result.token_usage,
            "style": style,
            "mock_mode": mock_mode,
        }
    )

    # Audit log entry (safe: no credentials or secrets)
    logger.info(
        "ExecutiveNarrative #%d created for Client #%d Report #%d by User %s [Status: %s, Validation: %s]",
        narrative.id,
        report.client_id,
        report.id,
        getattr(user, "username", "anonymous"),
        final_status,
        val_summary["status"],
    )

    return narrative


def get_latest_narrative_for_report(report: ExecutiveReport) -> Tuple[Optional[ExecutiveNarrative], bool]:
    """
    Returns the most recent narrative for the report along with its stale status.
    """
    narrative = ExecutiveNarrative.objects.filter(
        client=report.client,
        executive_report=report,
    ).order_by("-created_at").first()

    if not narrative:
        return None, False

    is_stale = (narrative.source_hash != report.source_hash)
    return narrative, is_stale
