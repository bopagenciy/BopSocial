"""
Metric Comparison Rule Dataclass and Registry Abstraction.
Phase BS-5A: Multichannel Metric Compatibility & Comparison Model.

Provides the single source of truth for platform pair comparison rules,
ensuring comparison semantics are explicit, deterministic, and fail-closed.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .taxonomies import (
    ComparisonCompatibility,
    ComparisonDirection,
    NormalizationType,
    ComparisonReasonCode,
)


@dataclass(frozen=True)
class MetricComparisonRule:
    """
    Deterministic rule specifying cross-platform comparison behavior for a metric and platform pair.
    """
    metric: str
    platform_a: str
    platform_b: str
    compatibility: ComparisonCompatibility
    normalization: NormalizationType
    direction: ComparisonDirection
    rankable: bool
    required_metrics: List[str] = field(default_factory=list)
    minimum_sample: int = 1
    notes: str = ""
    default_reason_code: ComparisonReasonCode = ComparisonReasonCode.DIRECTLY_COMPARABLE

    def is_symmetric_with(self, platform_x: str, platform_y: str) -> bool:
        """Checks if this rule applies to the platform pair in either order."""
        px = platform_x.strip().lower()
        py = platform_y.strip().lower()
        pa = self.platform_a.strip().lower()
        pb = self.platform_b.strip().lower()
        return (pa == px and pb == py) or (pa == py and pb == px)


# Internal storage of rules indexed by (canonical_metric, platform_a, platform_b)
_RULE_REGISTRY: Dict[Tuple[str, str, str], MetricComparisonRule] = {}


def register_rule(rule: MetricComparisonRule) -> None:
    """Registers a rule in the internal rule registry."""
    key = (
        rule.metric.strip().upper(),
        rule.platform_a.strip().lower(),
        rule.platform_b.strip().lower(),
    )
    _RULE_REGISTRY[key] = rule


def get_metric_comparison_rule(
    metric: str,
    platform_a: str,
    platform_b: str,
) -> Optional[MetricComparisonRule]:
    """
    Retrieve comparison rule for metric between platform_a and platform_b.
    Symmetric lookup: if registered as (A, B), looking up (B, A) returns an
    oriented rule preserving semantic parity.
    Fails closed (returns None) if metric or platform pair is unregistered.
    """
    if not metric or not platform_a or not platform_b:
        return None

    m_key = metric.strip().upper()
    p_a = platform_a.strip().lower()
    p_b = platform_b.strip().lower()

    if p_a == p_b:
        # Same platform comparisons are by definition direct and self-consistent
        return MetricComparisonRule(
            metric=m_key,
            platform_a=p_a,
            platform_b=p_b,
            compatibility=ComparisonCompatibility.DIRECT,
            normalization=NormalizationType.NONE,
            direction=ComparisonDirection.HIGHER_IS_BETTER,
            rankable=True,
            required_metrics=[m_key],
            minimum_sample=1,
            notes="Same-platform self comparison.",
            default_reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
        )

    # 1. Direct key lookup
    direct_key = (m_key, p_a, p_b)
    if direct_key in _RULE_REGISTRY:
        return _RULE_REGISTRY[direct_key]

    # 2. Symmetric reverse lookup
    reverse_key = (m_key, p_b, p_a)
    if reverse_key in _RULE_REGISTRY:
        base = _RULE_REGISTRY[reverse_key]
        # Return an oriented rule for (p_a, p_b)
        return MetricComparisonRule(
            metric=base.metric,
            platform_a=p_a,
            platform_b=p_b,
            compatibility=base.compatibility,
            normalization=base.normalization,
            direction=base.direction,
            rankable=base.rankable,
            required_metrics=list(base.required_metrics),
            minimum_sample=base.minimum_sample,
            notes=base.notes,
            default_reason_code=base.default_reason_code,
        )

    # 3. Fail closed if unmapped
    return None


def get_all_registered_rules() -> List[MetricComparisonRule]:
    """Returns a list of all registered comparison rules."""
    return list(_RULE_REGISTRY.values())
