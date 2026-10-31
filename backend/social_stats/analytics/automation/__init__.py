"""
BS-6A Production Intelligence Automation & Scheduling Foundation.
"""
from .approval import (
    ApprovalError,
    ApprovalIdentityMismatchError,
    ApprovalStateError,
    AuthorizationError,
    DoubleApprovalError,
    StaleApprovalError,
    approve_intelligence_run,
    reject_intelligence_run,
    resume_approved_intelligence_run,
    reserve_provider_execution,
)
from .constants import (
    ApprovalStatus,
    AutomationStage,
    AutomationStatus,
    AutomationTriggerType,
    CoverageCode,
    DEFAULT_MAX_RETRY_COUNT,
    DEFAULT_MINIMUM_PERIOD_COVERAGE_PERCENT,
    DEFAULT_PROVIDER_CALL_BUDGET,
    FreshnessCode,
    PIPELINE_VERSION,
    PROVIDER_EXECUTION_READY,
    PROVIDER_EXECUTING,
)
from .coverage import evaluate_target_period_coverage, CoverageResult, PlatformCoverage
from .eligibility import evaluate_intelligence_automation_eligibility, EligibilityResult
from .freshness import evaluate_tenant_freshness, FreshnessResult
from .identity import (
    compute_approval_token,
    compute_block_state_hash,
    compute_execution_identity,
    get_deterministic_report_source_hash,
    verify_executive_report_reuse,
    verify_executive_narrative_reuse,
)
from .locking import ConcurrencyLockError, SingleFlightLock
from .orchestrator import execute_intelligence_automation, preview_intelligence_automation
from .period import (
    calculate_next_due_datetime,
    calculate_reporting_period,
    get_calendar_month_bounds,
    get_rolling_window_bounds,
    is_tenant_due,
)

__all__ = [
    "PIPELINE_VERSION",
    "DEFAULT_PROVIDER_CALL_BUDGET",
    "DEFAULT_MAX_RETRY_COUNT",
    "PROVIDER_EXECUTION_READY",
    "PROVIDER_EXECUTING",
    "AutomationStage",
    "AutomationStatus",
    "ApprovalStatus",
    "AutomationTriggerType",
    "CoverageCode",
    "FreshnessCode",
    "EligibilityResult",
    "FreshnessResult",
    "CoverageResult",
    "PlatformCoverage",
    "SingleFlightLock",
    "ConcurrencyLockError",
    "ApprovalError",
    "ApprovalStateError",
    "ApprovalIdentityMismatchError",
    "DoubleApprovalError",
    "StaleApprovalError",
    "AuthorizationError",
    "compute_execution_identity",
    "compute_block_state_hash",
    "compute_approval_token",
    "get_deterministic_report_source_hash",
    "verify_executive_report_reuse",
    "verify_executive_narrative_reuse",
    "approve_intelligence_run",
    "reject_intelligence_run",
    "resume_approved_intelligence_run",
    "reserve_provider_execution",
    "calculate_reporting_period",
    "calculate_next_due_datetime",
    "is_tenant_due",
    "get_calendar_month_bounds",
    "get_rolling_window_bounds",
    "evaluate_tenant_freshness",
    "evaluate_target_period_coverage",
    "evaluate_intelligence_automation_eligibility",
    "preview_intelligence_automation",
    "execute_intelligence_automation",
]
