"""
Pure Eligibility Engine for BS-6A Production Intelligence Automation.
Evaluates deterministic gates, freshness, idempotency, existing artifacts,
and provider-call budgets without making any external provider calls.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from django.utils import timezone

from social_stats.models import (
    BusinessSignal,
    Client,
    ExecutiveNarrative,
    ExecutiveReport,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
)
from .constants import (
    AutomationStage,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MINIMUM_PERIOD_COVERAGE_PERCENT,
    DEFAULT_PROVIDER_CALL_BUDGET,
    FreshnessCode,
    PIPELINE_VERSION,
)
from .coverage import evaluate_target_period_coverage, CoverageResult
from .freshness import evaluate_tenant_freshness, FreshnessResult
from .identity import compute_block_state_hash, compute_execution_identity
from .period import calculate_reporting_period


@dataclass
class EligibilityResult:
    eligible: bool
    client_id: int
    period_start: date
    period_end: date
    execution_identity: str
    pipeline_version: str
    data_eligible: bool = True
    execution_authorized: bool = False
    block_state_hash: str = ""
    blocking_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    freshness: Dict[str, Any] = field(default_factory=dict)
    target_period_coverage: Dict[str, Any] = field(default_factory=dict)
    existing_artifacts: Dict[str, Any] = field(default_factory=dict)
    planned_stages: List[str] = field(default_factory=list)
    skipped_stages: List[str] = field(default_factory=list)
    reuse_decisions: Dict[str, Any] = field(default_factory=dict)
    provider_call_budget: int = DEFAULT_PROVIDER_CALL_BUDGET
    requires_operator_approval: bool = True
    config_enabled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eligible": self.eligible,
            "data_eligible": self.data_eligible,
            "execution_authorized": self.execution_authorized,
            "block_state_hash": self.block_state_hash,
            "client_id": self.client_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "execution_identity": self.execution_identity,
            "pipeline_version": self.pipeline_version,
            "blocking_reasons": self.blocking_reasons,
            "warnings": self.warnings,
            "freshness": self.freshness,
            "target_period_coverage": self.target_period_coverage,
            "existing_artifacts": self.existing_artifacts,
            "planned_stages": self.planned_stages,
            "skipped_stages": self.skipped_stages,
            "reuse_decisions": self.reuse_decisions,
            "provider_call_budget": self.provider_call_budget,
            "requires_operator_approval": self.requires_operator_approval,
            "config_enabled": self.config_enabled,
        }


def evaluate_intelligence_automation_eligibility(
    client_id: int,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    pipeline_version: str = PIPELINE_VERSION,
    trigger_type: str = "MANUAL",
    force_stages: Optional[List[str]] = None,
    now: Optional[datetime] = None,
    dry_run: bool = False,
) -> EligibilityResult:
    """
    Evaluates tenant eligibility for automated intelligence generation under strict BS-6A rules.
    Pure function with zero external network or LLM calls.
    """
    current_time = now or timezone.now()
    blocking_reasons: List[str] = []
    warnings: List[str] = []
    planned_stages: List[str] = []
    skipped_stages: List[str] = []
    reuse_decisions: Dict[str, Any] = {}

    # 1. Tenant Existence & Active Check
    client = Client.objects.filter(id=client_id).first()
    if not client:
        return EligibilityResult(
            eligible=False,
            data_eligible=False,
            execution_authorized=False,
            client_id=client_id,
            period_start=period_start or current_time.date(),
            period_end=period_end or current_time.date(),
            execution_identity="",
            pipeline_version=pipeline_version,
            blocking_reasons=["CLIENT_NOT_FOUND"],
            warnings=[],
            freshness={},
            existing_artifacts={},
            planned_stages=[],
            skipped_stages=[],
            reuse_decisions={},
            provider_call_budget=0,
            requires_operator_approval=True,
            config_enabled=False,
        )

    if not client.is_active:
        blocking_reasons.append("CLIENT_INACTIVE")

    # 2. Automation Config Check
    config = IntelligenceAutomationConfig.objects.filter(client_id=client_id).first()
    config_enabled = bool(config and config.enabled)
    lookback_days = config.lookback_days if config else DEFAULT_LOOKBACK_DAYS
    tz_name = config.timezone if (config and config.timezone) else (getattr(client, "timezone", None) or "America/New_York")
    freq = config.reporting_frequency if config else "MONTHLY"
    provider_budget = config.provider_call_budget if config else DEFAULT_PROVIDER_CALL_BUDGET
    req_approval = config.require_operator_approval if config else getattr(client, "requires_approval", True)
    gen_narrative = config.generate_narrative if config else False
    gen_report = config.generate_report if config else True
    max_staleness = config.max_data_staleness_hours if config else 24

    if not config:
        warnings.append("CONFIG_NOT_FOUND_DEFAULTING_TO_SAFE_DEFAULTS")
        if trigger_type == "SCHEDULED":
            blocking_reasons.append("AUTOMATION_CONFIG_MISSING")
    elif not config.enabled:
        if trigger_type == "SCHEDULED":
            blocking_reasons.append("AUTOMATION_CONFIG_DISABLED")
        else:
            warnings.append("AUTOMATION_CONFIG_CURRENTLY_DISABLED")

    # 3. Period Determination & Validation
    if not period_start or not period_end:
        p_start, p_end = calculate_reporting_period(
            tz_name=tz_name,
            frequency=freq,
            reference_datetime=current_time,
            lookback_days=lookback_days,
            period_type="CALENDAR_MONTH",
        )
    else:
        p_start, p_end = period_start, period_end

    if p_start >= p_end:
        blocking_reasons.append("INVALID_PERIOD_START_GTE_END")

    today_date = current_time.date()
    if p_end > today_date:
        blocking_reasons.append("PERIOD_END_IN_FUTURE")

    # Deterministic Execution Identity
    exec_identity = compute_execution_identity(
        client_id=client_id,
        period_start=p_start,
        period_end=p_end,
        pipeline_version=pipeline_version,
    )

    # 4. Duplicate Active Run Lock Check
    active_run = IntelligenceAutomationRun.objects.filter(
        client_id=client_id,
        period_start=p_start,
        period_end=p_end,
        pipeline_version=pipeline_version,
        status__in=[
            "PENDING",
            "ELIGIBILITY_CHECK",
            "RUNNING",
            "AWAITING_APPROVAL",
            "PROVIDER_EXECUTION_READY",
            "PROVIDER_EXECUTING",
        ],
    ).first()

    if active_run:
        blocking_reasons.append(f"DUPLICATE_ACTIVE_RUN_EXISTS: run #{active_run.id}")

    # 5. Connected Providers Check
    creds = list(PlatformCredential.objects.filter(client_id=client_id, is_active=True).values("id", "platform", "is_active", "expires_at"))
    if not creds:
        blocking_reasons.append("PROVIDER_DISCONNECTED: no active platform credentials")
    else:
        all_expired = all(
            bool(c.get("expires_at") and current_time >= (c["expires_at"] - timedelta(minutes=10)))
            for c in creds
        )
        if all_expired:
            blocking_reasons.append("PROVIDER_CREDENTIAL_EXPIRED: all platform credentials expired")

    # 6. Freshness Evaluation
    freshness_res: FreshnessResult = evaluate_tenant_freshness(
        client_id=client_id,
        period_start=p_start,
        period_end=p_end,
        max_staleness_hours=max_staleness,
        now=current_time,
    )
    freshness_dict = freshness_res.to_dict()

    if freshness_res.code == FreshnessCode.MISSING:
        blocking_reasons.append("ANALYTICS_DATA_MISSING")
    elif freshness_res.code == FreshnessCode.STALE and trigger_type == "SCHEDULED":
        blocking_reasons.append(f"ANALYTICS_DATA_STALE: age {freshness_res.data_age_hours:.1f}h > {max_staleness}h threshold")
    elif freshness_res.code == FreshnessCode.UNKNOWN:
        blocking_reasons.append("ANALYTICS_FRESHNESS_UNKNOWN")

    # 7. Coverage of Canonical Analytics (Snapshots & Rollups)
    snapshot_count = SocialMetricSnapshot.objects.filter(
        client_id=client_id,
        bucket_timestamp__date__gte=p_start,
        bucket_timestamp__date__lte=p_end,
    ).count()

    rollup_count = SocialMetricRollup.objects.filter(
        client_id=client_id,
        period_start__gte=p_start,
        period_start__lte=p_end,
    ).count()

    # 7b. Target-Period Completeness Gate (BS-6D.0C)
    cov_threshold = getattr(config, "minimum_period_coverage_percent", DEFAULT_MINIMUM_PERIOD_COVERAGE_PERCENT) if config else DEFAULT_MINIMUM_PERIOD_COVERAGE_PERCENT
    coverage_res: CoverageResult = evaluate_target_period_coverage(
        client_id=client_id,
        period_start=p_start,
        period_end=p_end,
        threshold_percent=cov_threshold,
    )
    coverage_dict = coverage_res.to_dict()

    if not coverage_res.is_sufficient:
        blocking_reasons.extend(coverage_res.blocking_reasons)
    warnings.extend(coverage_res.warnings)

    # 8. Existing Intelligence Artifacts Inspection
    signals = list(BusinessSignal.objects.filter(
        client_id=client_id,
        period_start=p_start,
        period_end=p_end,
    ))
    signal_count = len(signals)

    # Matching ExecutiveReport
    reports = list(ExecutiveReport.objects.filter(
        client_id=client_id,
        period_start=p_start,
        period_end=p_end,
        status="GENERATED",
    ).order_by("-id"))
    matching_report = reports[0] if reports else None

    # Matching Validated ExecutiveNarrative
    matching_narrative = None
    if matching_report:
        matching_narrative = ExecutiveNarrative.objects.filter(
            executive_report=matching_report,
            status="VALIDATED",
        ).order_by("-id").first()

    existing_artifacts = {
        "snapshots_count": snapshot_count,
        "rollups_count": rollup_count,
        "signals_count": signal_count,
        "matching_report_id": matching_report.id if matching_report else None,
        "matching_narrative_id": matching_narrative.id if matching_narrative else None,
        "report_source_hash": matching_report.source_hash if matching_report else None,
        "narrative_status": matching_narrative.status if matching_narrative else None,
    }

    # 9. Tenant Approval Boundary
    if req_approval and gen_narrative and not dry_run:
        blocking_reasons.append("OPERATOR_APPROVAL_REQUIRED: automated recurring narrative generation requires operator approval")

    # 10. Provider Call Budget Check
    if gen_narrative and not matching_narrative and provider_budget < 1:
        blocking_reasons.append("PROVIDER_CALL_BUDGET_EXHAUSTED: budget is 0")

    # 11. Planned Stages & Artifact Reuse Decisions
    # Stage: SNAPSHOT_CHECK
    if snapshot_count == 0:
        planned_stages.append(AutomationStage.SNAPSHOT_CHECK.value)
        warnings.append("NO_SNAPSHOTS_IN_PERIOD")
    else:
        skipped_stages.append(AutomationStage.SNAPSHOT_CHECK.value)
        reuse_decisions["snapshots"] = f"REUSE {snapshot_count} existing snapshots"

    # Stage: ROLLUP_CHECK
    if rollup_count == 0:
        planned_stages.append(AutomationStage.ROLLUP_CHECK.value)
        warnings.append("NO_ROLLUPS_IN_PERIOD")
    else:
        skipped_stages.append(AutomationStage.ROLLUP_CHECK.value)
        reuse_decisions["rollups"] = f"REUSE {rollup_count} existing rollups"

    # Stage: SIGNAL_CHECK
    if signal_count == 0:
        planned_stages.append(AutomationStage.SIGNAL_CHECK.value)
    else:
        skipped_stages.append(AutomationStage.SIGNAL_CHECK.value)
        reuse_decisions["signals"] = f"REUSE {signal_count} existing signals"

    # Stage: REPORT_CHECK
    if matching_report:
        skipped_stages.append(AutomationStage.REPORT_CHECK.value)
        reuse_decisions["report"] = f"REUSE ExecutiveReport #{matching_report.id} (idempotent matching hash)"
    else:
        if gen_report:
            planned_stages.append(AutomationStage.REPORT_CHECK.value)

    # Stage: NARRATIVE_CHECK
    if matching_narrative:
        skipped_stages.append(AutomationStage.NARRATIVE_CHECK.value)
        reuse_decisions["narrative"] = f"REUSE ExecutiveNarrative #{matching_narrative.id} (VALIDATED status, prompt={matching_narrative.prompt_version})"
    else:
        if gen_narrative:
            planned_stages.append(AutomationStage.NARRATIVE_CHECK.value)
        else:
            skipped_stages.append(AutomationStage.NARRATIVE_CHECK.value)
            reuse_decisions["narrative"] = "SKIPPED (generate_narrative=False in config)"

    is_eligible = len(blocking_reasons) == 0
    # Data eligibility: are snapshots/rollups/creds sufficient to synthesize data?
    data_blocking = [b for b in blocking_reasons if b in [
        "CLIENT_NOT_FOUND", "CLIENT_INACTIVE", "INVALID_PERIOD_START_GTE_END",
        "PERIOD_END_IN_FUTURE", "PROVIDER_DISCONNECTED: no active platform credentials",
        "PROVIDER_CREDENTIAL_EXPIRED: all platform credentials expired",
        "ANALYTICS_DATA_MISSING", "ANALYTICS_FRESHNESS_UNKNOWN",
    ] or b.startswith("ANALYTICS_DATA_STALE") or b.startswith("TARGET_PERIOD_COVERAGE_INSUFFICIENT")]
    is_data_eligible = len(data_blocking) == 0

    # Execution authorization: has operator/schedule authorized active generation?
    # SCHEDULED requires config_enabled AND NOT require_operator_approval (or approved)
    # MANUAL requires active client and no hard blockers
    is_execution_authorized = is_eligible and (
        (trigger_type == "SCHEDULED" and config_enabled and not req_approval)
        or (trigger_type in ["MANUAL", "ADMIN"])
    )

    # Material block state fingerprint:
    block_hash = compute_block_state_hash(
        blocking_reasons=blocking_reasons,
        freshness_code=freshness_res.code.value if hasattr(freshness_res, "code") else "",
        requires_approval=req_approval,
        config_enabled=config_enabled,
        coverage_code=coverage_res.overall_code.value if hasattr(coverage_res, "overall_code") else "",
        coverage_summary=f"{coverage_res.overall_percent:.1f}%",
    ) if not is_eligible else ""

    return EligibilityResult(
        eligible=is_eligible,
        data_eligible=is_data_eligible,
        execution_authorized=is_execution_authorized,
        block_state_hash=block_hash,
        client_id=client_id,
        period_start=p_start,
        period_end=p_end,
        execution_identity=exec_identity,
        pipeline_version=pipeline_version,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        freshness=freshness_dict,
        target_period_coverage=coverage_dict,
        existing_artifacts=existing_artifacts,
        planned_stages=planned_stages,
        skipped_stages=skipped_stages,
        reuse_decisions=reuse_decisions,
        provider_call_budget=provider_budget,
        requires_operator_approval=req_approval,
        config_enabled=config_enabled,
    )
