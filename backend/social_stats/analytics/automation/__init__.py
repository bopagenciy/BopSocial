"""
BS-6A Production Intelligence Automation & Scheduling Foundation.
"""
from .constants import (
    AutomationStage,
    AutomationStatus,
    AutomationTriggerType,
    DEFAULT_MAX_RETRY_COUNT,
    DEFAULT_PROVIDER_CALL_BUDGET,
    FreshnessCode,
    PIPELINE_VERSION,
)
from .eligibility import evaluate_intelligence_automation_eligibility, EligibilityResult
from .freshness import evaluate_tenant_freshness, FreshnessResult
from .identity import compute_execution_identity
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
    "AutomationStage",
    "AutomationStatus",
    "AutomationTriggerType",
    "FreshnessCode",
    "EligibilityResult",
    "FreshnessResult",
    "SingleFlightLock",
    "ConcurrencyLockError",
    "compute_execution_identity",
    "calculate_reporting_period",
    "calculate_next_due_datetime",
    "is_tenant_due",
    "get_calendar_month_bounds",
    "get_rolling_window_bounds",
    "evaluate_tenant_freshness",
    "evaluate_intelligence_automation_eligibility",
    "preview_intelligence_automation",
    "execute_intelligence_automation",
]
