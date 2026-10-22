"""
Deterministic string explanation templates for Bop Social Business Intelligence.
No LLM calls, no hallucinations, strictly defensible and explainable prose.
"""
from decimal import Decimal
from typing import Dict, Any, Optional


def format_pct(relative_delta: Optional[Decimal]) -> str:
    if relative_delta is None:
        return "N/A"
    pct = (relative_delta * Decimal("100")).quantize(Decimal("0.1"))
    sign = "+" if pct > Decimal("0") else ""
    return f"{sign}{pct}%"


def build_explanation(signal_type: str, context: Dict[str, Any]) -> str:
    """
    Renders an explainable, deterministic natural-language summary based on evidence parameters.
    """
    metric_name = context.get("metric_display", context.get("metric", "interactions"))
    observed = context.get("observed_value")
    baseline = context.get("baseline_value")
    sample_size = context.get("sample_size", 0)
    rel_pct = format_pct(context.get("relative_delta"))
    platform = (context.get("platform") or "social").title()
    fmt_name = context.get("format", "content")
    window_days = context.get("window_days", 30)

    if signal_type in ("CONTENT_OUTPERFORMING", "CONTENT_UNDERPERFORMING"):
        direction_prep = "above" if (context.get("direction") == "UP" or "+" in rel_pct) else "below"
        return (
            f"This post generated {observed} {metric_name}, which is "
            f"{rel_pct} {direction_prep} the recent median ({baseline}) of {sample_size} comparable "
            f"{fmt_name} posts on {platform} over the last {window_days} days."
        )

    elif signal_type in ("FORMAT_OUTPERFORMING", "FORMAT_UNDERPERFORMING"):
        direction_prep = "above" if (context.get("direction") == "UP" or "+" in rel_pct) else "below"
        return (
            f"{fmt_name.title()} content achieved a median of {observed} {metric_name}, performing "
            f"{rel_pct} {direction_prep} the overall platform median ({baseline}) across {sample_size} posts."
        )

    elif signal_type in ("POSTING_TIME_OUTPERFORMING", "POSTING_TIME_UNDERPERFORMING"):
        bucket = context.get("bucket", "scheduled")
        tz = context.get("timezone", "local time")
        direction_prep = "above" if (context.get("direction") == "UP" or "+" in rel_pct) else "below"
        return (
            f"Posts published during the {bucket} window ({tz}) achieved a median of {observed} {metric_name}, "
            f"performing {rel_pct} {direction_prep} the baseline median ({baseline}) based on {sample_size} observations."
        )

    elif signal_type in ("ENGAGEMENT_TREND_UP", "ENGAGEMENT_TREND_DOWN"):
        dir_word = "up" if context.get("direction") == "UP" else "down"
        return (
            f"Overall {metric_name} on {platform} trended {dir_word} by {rel_pct} "
            f"compared to the previous {window_days}-day baseline ({observed} vs {baseline})."
        )

    elif signal_type in ("FOLLOWER_GROWTH_UP", "FOLLOWER_GROWTH_DOWN"):
        dir_word = "accelerated" if context.get("direction") == "UP" else "slowed"
        total_followers = context.get("followers_total", "recorded")
        return (
            f"Net follower growth {dir_word} with {observed} new followers in the period "
            f"({rel_pct} change vs prior baseline of {baseline}). Total audience is currently {total_followers} followers."
        )

    elif signal_type in ("MOMENTUM_UP", "MOMENTUM_DOWN"):
        dir_word = "higher" if context.get("direction") == "UP" else "lower"
        return (
            f"Recent 7-day median of {observed} {metric_name} is {rel_pct} {dir_word} "
            f"than the preceding 7-day median of {baseline}."
        )

    elif signal_type in ("POSITIVE_OUTLIER", "NEGATIVE_OUTLIER"):
        outlier_label = "positive outlier" if signal_type == "POSITIVE_OUTLIER" else "negative outlier"
        return (
            f"Post #{context.get('object_id', '')} was identified as a {outlier_label} with {observed} {metric_name} "
            f"relative to the cohort median of {baseline}."
        )

    elif signal_type == "INSUFFICIENT_SAMPLE":
        min_req = context.get("min_required", 3)
        return (
            f"Insufficient comparable historical data for {fmt_name} content on {platform} "
            f"(sample size n={sample_size}, minimum required is {min_req}). Baselines will activate once more content is published."
        )

    elif signal_type == "PROVIDER_PARTIAL":
        return (
            f"Instagram analytics is operating in PARTIAL capability mode. Core source-backed metrics "
            f"(Reactions, Comments, Total Followers) are active, while advanced metrics (Reach, Saves, Video Views) "
            f"remain unavailable under current Meta permissions."
        )

    elif signal_type == "DATA_STALE":
        hours = context.get("hours_stale", "unknown")
        return (
            f"Analytics data for {platform} has not synchronized in {hours} hours. "
            f"Active business signals carry reduced confidence until synchronization resumes."
        )

    elif signal_type == "METRIC_UNAVAILABLE":
        return (
            f"Metric {metric_name} is not available for {platform} with current permissions. "
            f"No speculative signals or fabricated zeros will be emitted."
        )

    return f"Business signal for {platform} {metric_name}: observed={observed}, baseline={baseline} ({rel_pct})."
