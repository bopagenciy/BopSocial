"""
Service layer for Grounded AI Executive Narrative.
Orchestrates context extraction, provider execution, deterministic validation,
persistence, and stale narrative detection.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone
from social_stats.models import ExecutiveNarrative, ExecutiveReport

from .context import build_grounded_narrative_context, compute_context_hash
from .confidence import enrich_narrative_with_derived_confidence
from .prompts import PROMPT_VERSION
from .providers import get_narrative_provider
from .schemas import (
    CONTEXT_SCHEMA_VERSION,
    GENERATION_POLICY_DEFAULT,
    GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
    MAX_PROVIDER_CALLS,
)
from .validator import NarrativeValidator

logger = logging.getLogger(__name__)


class ControlledLiveExecutionError(RuntimeError):
    """
    Raised when controlled-live narrative execution fails validation, parsing, or transport.
    Guarantees no retry, no fallback, and no database persistence.
    """
    def __init__(
        self,
        message: str,
        provider_attempt_count: int = 1,
        validation_status: str = "FAILED",
        validation_errors: Optional[List[str]] = None,
        can_retry: bool = False,
        fallback_used: bool = False,
    ):
        super().__init__(message)
        self.provider_attempt_count = provider_attempt_count
        self.validation_status = validation_status
        self.validation_errors = validation_errors or []
        self.can_retry = can_retry
        self.fallback_used = fallback_used


def execute_controlled_narrative_generation(
    report: ExecutiveReport,
    language: Optional[str] = None,
    style: str = "EXECUTIVE",
    provider_name: str = "fake",
    mock_mode: str = "VALID",
    generation_policy: str = GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
    fallback_enabled: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Executes a single controlled provider generation attempt enforcing the BS-5E.1 policy:
    1. Exactly ONE provider call maximum (MAX_PROVIDER_CALLS = 1).
    2. No automatic retries.
    3. No validation feedback retries.
    4. No automatic deterministic fallback (fallback_enabled = False).
    5. Immediate STOP on transport error, JSON parse failure, or validator rejection.
    """
    if generation_policy == GENERATION_POLICY_SINGLE_ATTEMPT_STRICT and fallback_enabled:
        raise ValueError("Controlled live policy strictly forbids fallback_enabled=True.")

    lang = language or getattr(report, "language", "es") or "es"
    context = build_grounded_narrative_context(report)
    context_hash = compute_context_hash(context)

    provider_attempt_count = 0

    if provider_attempt_count >= MAX_PROVIDER_CALLS:
        raise ControlledLiveExecutionError(
            f"MAX_PROVIDER_CALLS ({MAX_PROVIDER_CALLS}) exceeded. Provider call aborted.",
            provider_attempt_count=provider_attempt_count,
            can_retry=False,
            fallback_used=False,
        )

    provider = get_narrative_provider(provider_name, mock_mode=mock_mode)

    # Provider invocation: Attempt 1
    provider_attempt_count += 1

    try:
        result = provider.generate(
            context=context,
            language=lang,
            style=style,
            mock_mode=mock_mode,
            **kwargs
        )
    except Exception as exc:
        logger.error("Controlled provider invocation failed on attempt %d: %s", provider_attempt_count, exc)
        raise ControlledLiveExecutionError(
            f"Provider transport or execution failure: {exc}",
            provider_attempt_count=provider_attempt_count,
            validation_status="FAILED",
            validation_errors=[str(exc)],
            can_retry=False,
            fallback_used=False,
        ) from exc

    # Parse JSON check
    parsed_json = result.parsed_json
    if not parsed_json or not isinstance(parsed_json, dict):
        raise ControlledLiveExecutionError(
            "Malformed JSON or empty response from narrative provider.",
            provider_attempt_count=provider_attempt_count,
            validation_status="PARSE_FAILED",
            validation_errors=["Empty or invalid JSON payload"],
            can_retry=False,
            fallback_used=False,
        )

    # Enrich confidence
    enriched_narrative = enrich_narrative_with_derived_confidence(parsed_json, context)

    # Validate all gates
    is_valid, val_summary = NarrativeValidator.validate(enriched_narrative, context)

    return {
        "is_valid": is_valid,
        "provider_attempt_count": provider_attempt_count,
        "max_provider_calls": MAX_PROVIDER_CALLS,
        "generation_policy": generation_policy,
        "fallback_enabled": fallback_enabled,
        "fallback_used": False,
        "context": context,
        "context_hash": context_hash,
        "result": result,
        "enriched_narrative": enriched_narrative,
        "val_summary": val_summary,
        "lang": lang,
    }


def preview_narrative(
    report: ExecutiveReport,
    language: Optional[str] = None,
    style: str = "EXECUTIVE",
    provider_name: str = "fake",
    mock_mode: str = "VALID",
    generation_policy: str = GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
    fallback_enabled: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Generates a deterministic preview of the AI narrative without persisting to DB.
    Guarantees 0 database rows are created.
    Enforces controlled-live policy accounting.
    """
    exec_data = execute_controlled_narrative_generation(
        report=report,
        language=language,
        style=style,
        provider_name=provider_name,
        mock_mode=mock_mode,
        generation_policy=generation_policy,
        fallback_enabled=fallback_enabled,
        **kwargs
    )

    result = exec_data["result"]
    val_summary = exec_data["val_summary"]

    return {
        "report_id": report.id,
        "language": exec_data["lang"],
        "style": style,
        "provider": provider_name,
        "model_name": result.model_name,
        "prompt_version": PROMPT_VERSION,
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "source_hash": report.source_hash,
        "context_hash": exec_data["context_hash"],
        "context": exec_data["context"],
        "narrative": exec_data["enriched_narrative"],
        "raw_response": result.raw_response,
        "validation_status": val_summary["status"],
        "validation_results": val_summary["results"],
        "validation_errors": val_summary["errors"],
        "is_valid": exec_data["is_valid"],
        "token_usage": result.token_usage,
        "provider_attempt_count": exec_data["provider_attempt_count"],
        "max_provider_calls": exec_data["max_provider_calls"],
        "generation_policy": exec_data["generation_policy"],
        "fallback_enabled": exec_data["fallback_enabled"],
        "fallback_used": exec_data["fallback_used"],
        "metadata": result.metadata,
    }


def generate_and_save_narrative(
    report: ExecutiveReport,
    user=None,
    language: Optional[str] = None,
    style: str = "EXECUTIVE",
    provider_name: str = "fake",
    mock_mode: str = "VALID",
    force_regenerate: bool = False,
    generation_policy: str = GENERATION_POLICY_DEFAULT,
    fallback_enabled: bool = False,
    persist_on_validation_failure: Optional[bool] = None,
    **kwargs
) -> ExecutiveNarrative:
    """
    Generates and persists an ExecutiveNarrative instance.
    Sets status to VALIDATED only if all validation gates pass.
    Under GENERATION_POLICY_SINGLE_ATTEMPT_STRICT:
      - Enforces MAX_PROVIDER_CALLS = 1.
      - Disables automatic retries.
      - Disables automatic fallback.
      - Rejects persistence if validation or transport fails.
    Deduplication Policy:
      If force_regenerate is False and an identical VALIDATED narrative already exists for this report
      (matching executive_report, source_hash, context_hash, prompt_version, and provider),
      the existing narrative is returned without creating duplicate database rows.
    """
    lang = language or getattr(report, "language", "es") or "es"
    context = build_grounded_narrative_context(report)
    context_hash = compute_context_hash(context)

    if not force_regenerate:
        existing = ExecutiveNarrative.objects.filter(
            executive_report=report,
            status="VALIDATED",
            source_hash=report.source_hash,
            context_hash=context_hash,
            prompt_version=PROMPT_VERSION,
            provider=provider_name,
        ).order_by("-created_at").first()
        if existing:
            logger.info(
                "Returning existing VALIDATED ExecutiveNarrative #%d for Report #%d (deduplication active)",
                existing.id,
                report.id,
            )
            return existing

    exec_data = execute_controlled_narrative_generation(
        report=report,
        language=language,
        style=style,
        provider_name=provider_name,
        mock_mode=mock_mode,
        generation_policy=generation_policy,
        fallback_enabled=fallback_enabled,
        **kwargs
    )

    is_valid = exec_data["is_valid"]
    val_summary = exec_data["val_summary"]
    enriched_narrative = exec_data["enriched_narrative"]
    result = exec_data["result"]
    provider_attempt_count = exec_data["provider_attempt_count"]

    if not is_valid:
        should_persist = (persist_on_validation_failure is True) or (
            generation_policy != GENERATION_POLICY_SINGLE_ATTEMPT_STRICT and persist_on_validation_failure is not False
        )
        if not should_persist:
            raise ControlledLiveExecutionError(
                f"Controlled-live generation failed validation: {val_summary.get('errors')}",
                provider_attempt_count=provider_attempt_count,
                validation_status=val_summary["status"],
                validation_errors=val_summary.get("errors", []),
                can_retry=False,
                fallback_used=False,
            )
        else:
            final_status = "REJECTED"
    else:
        final_status = "VALIDATED"

    rendered_text = ""
    if enriched_narrative:
        sections = []
        for sec in ["executive_summary", "performance_observations"]:
            items = enriched_narrative.get(sec, [])
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
        narrative_json=enriched_narrative,
        rendered_text=rendered_text,
        validation_status=val_summary["status"],
        validation_results=val_summary,
        created_by=user,
        generated_at=timezone.now(),
        metadata={
            "token_usage": result.token_usage,
            "style": style,
            "mock_mode": mock_mode,
            "provider_attempt_count": provider_attempt_count,
            "max_provider_calls": MAX_PROVIDER_CALLS,
            "generation_policy": generation_policy,
            "fallback_enabled": fallback_enabled,
            "fallback_used": False,
        }
    )

    # Audit log entry (safe: no credentials or secrets)
    logger.info(
        "ExecutiveNarrative #%d created for Client #%d Report #%d by User %s [Status: %s, Validation: %s, Attempts: %d]",
        narrative.id,
        report.client_id,
        report.id,
        getattr(user, "username", "anonymous"),
        final_status,
        val_summary["status"],
        provider_attempt_count,
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
