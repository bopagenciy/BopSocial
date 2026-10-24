"""
Deterministic Multichannel Business Signal Engine.
Phase BS-5C: Multichannel Business Signal Engine.

Consumes BS-5B MultichannelBenchmarkResult as authoritative evidence
and emits grounded cross-platform business signals.

Guarantees:
- Consumes MultichannelBenchmarkResult directly without recalculating source analytics.
- Strictly NO overall platform winner signals.
- FOLLOWERS_TOTAL emits AUDIENCE_SIZE_DIFFERENCE (non-rankable, non-actionable).
- Zero baseline never manufactures fake percentage improvement.
- Low-information zero-zero ties are suppressed.
- Unavailable metrics are consolidated into CROSS_PLATFORM_DATA_LIMITATION.
- Non-comparable metrics are consolidated into CROSS_PLATFORM_METRIC_NON_COMPARABLE.
- Format cohort advantage strictly gated by minimum sample (n >= 3 both platforms).
- Deterministic confidence and actionability derivation.
- Stable SHA256 signal identity with idempotent deduplication.
- Bilingual deterministic templates (EN / ES) without LLM calls.
- Fail-closed validation and persistence authorization boundary.
"""
from datetime import date
from decimal import Decimal
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from social_stats.models import BusinessSignal, Client
from .benchmarks import (
    BENCHMARK_SCHEMA_VERSION,
    CANONICAL_METRIC_ORDER,
    MINIMUM_COHORT_SAMPLE,
    MultichannelBenchmarkResult,
)
from .taxonomies import (
    ComparisonCompatibility,
    ComparisonDirection,
    ComparisonReasonCode,
    ComparisonStatus,
    ComparisonWinner,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# TAXONOMY & ENUMS
# ==============================================================================

class MultichannelSignalType:
    PLATFORM_METRIC_OUTPERFORMANCE = "PLATFORM_METRIC_OUTPERFORMANCE"
    CROSS_PLATFORM_TIE = "CROSS_PLATFORM_TIE"
    AUDIENCE_SIZE_DIFFERENCE = "AUDIENCE_SIZE_DIFFERENCE"
    CROSS_PLATFORM_DATA_LIMITATION = "CROSS_PLATFORM_DATA_LIMITATION"
    CROSS_PLATFORM_METRIC_NON_COMPARABLE = "CROSS_PLATFORM_METRIC_NON_COMPARABLE"
    FORMAT_PLATFORM_ADVANTAGE = "FORMAT_PLATFORM_ADVANTAGE"
    INSUFFICIENT_CROSS_PLATFORM_SAMPLE = "INSUFFICIENT_CROSS_PLATFORM_SAMPLE"


class SignalCategory:
    PERFORMANCE = "PERFORMANCE"
    AUDIENCE = "AUDIENCE"
    DATA_QUALITY = "DATA_QUALITY"
    CAPABILITY = "CAPABILITY"
    FORMAT = "FORMAT"


class SignalSeverity:
    INFO = "INFO"
    POSITIVE = "POSITIVE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ConfidenceTier:
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class RecommendedActionCode:
    CONTINUE_COLLECTING_DATA = "CONTINUE_COLLECTING_DATA"
    REVIEW_PROVIDER_PERMISSIONS = "REVIEW_PROVIDER_PERMISSIONS"
    REVIEW_PLATFORM_PERFORMANCE = "REVIEW_PLATFORM_PERFORMANCE"
    EXPAND_SAMPLE = "EXPAND_SAMPLE"
    MAINTAIN_CURRENT_CADENCE = "MAINTAIN_CURRENT_CADENCE"


# Forbidden signals (Safety invariant: No aggregate platform score / overall winner)
FORBIDDEN_SIGNAL_TYPES = {
    "OVERALL_PLATFORM_WINNER",
    "CROSS_PLATFORM_OVERALL_WINNER",
    "PLATFORM_OVERALL_WINNER",
    "AGGREGATE_PLATFORM_SCORE",
}

# Materiality thresholds
MATERIALITY_THRESHOLDS = {
    "MINIMUM_ABSOLUTE_DELTA_VOLUME": Decimal("1.0000"),
    "SIGNIFICANT_ABSOLUTE_DELTA": Decimal("5.0000"),
    "MINIMUM_RELATIVE_DELTA_PCT": Decimal("20.0000"),  # +20%
}


# ==============================================================================
# DETERMINISTIC SIGNAL IDENTITY
# ==============================================================================

def compute_multichannel_signal_identity(
    *,
    client_id: int,
    signal_type: str,
    benchmark_hash: str,
    metric: str,
    platform_a: str,
    platform_b: str,
    cohort_key: str = "",
) -> str:
    """
    Computes a deterministic SHA256 digest ensuring zero duplicate signals.
    Strictly excludes timestamps, runtime counters, or non-deterministic variables.
    """
    key_str = (
        f"{client_id}:{signal_type.strip().upper()}:{benchmark_hash.strip().lower()}:"
        f"{metric.strip().upper()}:{platform_a.strip().lower()}:{platform_b.strip().lower()}:"
        f"{cohort_key.strip().lower()}"
    )
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()


# ==============================================================================
# BILINGUAL NATURAL-LANGUAGE TEMPLATES (NO LLM)
# ==============================================================================

def format_signal_description(
    signal_type: str,
    evidence: Dict[str, Any],
    language: str = "en",
) -> str:
    """
    Generates a deterministic human-readable description for the signal.
    Uses strict factual templates without generative AI or fabricated percentages.
    """
    lang = (language or "en").strip().lower()
    raw_metric = evidence.get("metric", "")
    plat_a = evidence.get("platform_a", "").title()
    plat_b = evidence.get("platform_b", "").title()
    val_a = evidence.get("platform_values", {}).get(evidence.get("platform_a", ""), 0)
    val_b = evidence.get("platform_values", {}).get(evidence.get("platform_b", ""), 0)
    winner_plat = evidence.get("winner_platform", "").title()

    friendly_metric_es = {
        "REACTIONS": "reacciones",
        "COMMENTS": "comentarios",
        "FOLLOWERS_TOTAL": "seguidores",
        "CLICKS_TOTAL": "clics",
        "IMPRESSIONS": "impresiones",
        "REACH": "alcance",
    }.get(raw_metric, raw_metric.lower())

    friendly_metric_en = {
        "REACTIONS": "reactions",
        "COMMENTS": "comments",
        "FOLLOWERS_TOTAL": "followers",
        "CLICKS_TOTAL": "clicks",
        "IMPRESSIONS": "impressions",
        "REACH": "reach",
    }.get(raw_metric, raw_metric.lower())

    if signal_type == MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE:
        if lang == "es":
            if evidence.get("zero_baseline", False):
                return (
                    f"{winner_plat} registró {val_b if winner_plat == plat_b else val_a} {friendly_metric_es} "
                    f"frente a 0 en {plat_a if winner_plat == plat_b else plat_b} durante el período."
                )
            rel = evidence.get("relative_delta")
            rel_str = f"+{rel:.1f}%" if rel is not None else ""
            return (
                f"{winner_plat} superó a {plat_a if winner_plat == plat_b else plat_b} en {friendly_metric_es} "
                f"({val_b if winner_plat == plat_b else val_a} vs {val_a if winner_plat == plat_b else val_b}"
                f"{', ' + rel_str if rel_str else ''}) durante el período."
            )
        else:
            if evidence.get("zero_baseline", False):
                return (
                    f"{winner_plat} recorded {val_b if winner_plat == plat_b else val_a} {friendly_metric_en} "
                    f"compared with 0 on {plat_a if winner_plat == plat_b else plat_b} during the period."
                )
            rel = evidence.get("relative_delta")
            rel_str = f"+{rel:.1f}%" if rel is not None else ""
            return (
                f"{winner_plat} outperformed {plat_a if winner_plat == plat_b else plat_b} in {friendly_metric_en} "
                f"({val_b if winner_plat == plat_b else val_a} vs {val_a if winner_plat == plat_b else val_b}"
                f"{', ' + rel_str if rel_str else ''}) during the period."
            )

    elif signal_type == MultichannelSignalType.AUDIENCE_SIZE_DIFFERENCE:
        if lang == "es":
            return (
                f"{plat_b} cuenta con {val_b} seguidores frente a {val_a} en {plat_a} "
                f"(métrica de volumen de audiencia, no de rendimiento)."
            )
        else:
            return (
                f"{plat_b} has {val_b} followers compared with {val_a} on {plat_a} "
                f"(audience volume metric, not performance)."
            )

    elif signal_type == MultichannelSignalType.CROSS_PLATFORM_TIE:
        if lang == "es":
            return (
                f"Empate entre plataformas en {metric.lower()}: tanto {plat_a} como {plat_b} "
                f"registraron {val_a} durante el período."
            )
        else:
            return (
                f"Cross-platform tie in {metric.lower()}: both {plat_a} and {plat_b} "
                f"recorded {val_a} during the period."
            )

    elif signal_type == MultichannelSignalType.CROSS_PLATFORM_DATA_LIMITATION:
        unavail = evidence.get("affected_metrics_count", len(evidence.get("affected_metrics", [])))
        total = evidence.get("total_metrics", 15)
        prov = evidence.get("provider_limitations", "proveedor")
        if lang == "es":
            return (
                f"Limitación de datos entre plataformas: {unavail} de {total} métricas no están disponibles "
                f"debido a capacidades parciales del proveedor ({prov})."
            )
        else:
            return (
                f"Cross-platform data limitation: {unavail} of {total} metrics unavailable "
                f"due to partial provider capabilities ({prov})."
            )

    elif signal_type == MultichannelSignalType.CROSS_PLATFORM_METRIC_NON_COMPARABLE:
        aff = ", ".join(evidence.get("affected_metrics", []))
        if lang == "es":
            return (
                f"Métricas no comparables entre plataformas: {aff} tienen definiciones semánticas o de agregación "
                f"estructuralmente dispares."
            )
        else:
            return (
                f"Cross-platform non-comparable metrics: {aff} have structurally disparate semantic or aggregation definitions."
            )

    elif signal_type == MultichannelSignalType.INSUFFICIENT_CROSS_PLATFORM_SAMPLE:
        fmt = evidence.get("format", "contenido").upper()
        s_a = evidence.get("sample_a", 0)
        s_b = evidence.get("sample_b", 0)
        min_s = evidence.get("minimum_sample", MINIMUM_COHORT_SAMPLE)
        if lang == "es":
            return (
                f"Muestra insuficiente para formato {fmt}: {plat_a} tiene {s_a} publicaciones e {plat_b} tiene {s_b} "
                f"(mínimo requerido: {min_s} en ambas plataformas)."
            )
        else:
            return (
                f"Insufficient sample for {fmt} format: {plat_a} has {s_a} posts and {plat_b} has {s_b} "
                f"(minimum required: {min_s} on both platforms)."
            )

    elif signal_type == MultichannelSignalType.FORMAT_PLATFORM_ADVANTAGE:
        fmt = evidence.get("format", "content").upper()
        if lang == "es":
            return (
                f"Ventaja de formato en {winner_plat}: el contenido de tipo {fmt} demostró mayor efectividad "
                f"con una muestra válida (n >= {MINIMUM_COHORT_SAMPLE})."
            )
        else:
            return (
                f"Format platform advantage on {winner_plat}: {fmt} content achieved superior performance "
                f"with valid sample size (n >= {MINIMUM_COHORT_SAMPLE})."
            )

    return f"Multichannel business signal: {signal_type}"


# ==============================================================================
# DETERMINISTIC SIGNAL VALIDATOR
# ==============================================================================

class MultichannelSignalValidationError(Exception):
    """Raised when a signal candidate violates architectural safety invariants."""
    pass


def validate_signal_candidate(
    candidate: Dict[str, Any],
    benchmark: MultichannelBenchmarkResult,
) -> Tuple[bool, List[str]]:
    """
    Executes 8 deterministic validation gates against a signal candidate:
    1. Benchmark binding (schema version and benchmark_hash)
    2. Overall platform winner prohibition
    3. Rankability consistency (FOLLOWERS_TOTAL never has outperformance or winner)
    4. Zero-baseline relative percentage guard
    5. Sample sufficiency for format cohorts
    6. Evidence completeness
    7. Confidence consistency
    8. Actionability consistency
    """
    errors: List[str] = []
    sig_type = candidate.get("signal_type", "")

    # Gate 1: Benchmark binding
    if candidate.get("benchmark_hash") != benchmark.benchmark_hash:
        errors.append(f"Benchmark hash mismatch: {candidate.get('benchmark_hash')} != {benchmark.benchmark_hash}")
    if candidate.get("benchmark_schema_version") != BENCHMARK_SCHEMA_VERSION:
        errors.append(f"Invalid benchmark schema version: {candidate.get('benchmark_schema_version')}")

    # Gate 2: Overall platform winner prohibition
    if sig_type in FORBIDDEN_SIGNAL_TYPES or "OVERALL" in sig_type:
        errors.append(f"Forbidden signal type '{sig_type}': overall platform winners are strictly prohibited.")

    # Gate 3: Rankability consistency
    metric = candidate.get("metric", "")
    if metric == "FOLLOWERS_TOTAL" and sig_type == MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE:
        errors.append("FOLLOWERS_TOTAL is non-rankable and cannot produce PLATFORM_METRIC_OUTPERFORMANCE.")

    # Gate 4: Zero baseline guard
    evidence = candidate.get("evidence", {})
    if evidence.get("zero_baseline", False) and candidate.get("relative_delta") is not None:
        errors.append("Relative delta must be None when baseline is zero (fake percentage prohibited).")

    # Gate 5: Cohort sample sufficiency
    if sig_type == MultichannelSignalType.FORMAT_PLATFORM_ADVANTAGE:
        s_a = evidence.get("sample_a", 0)
        s_b = evidence.get("sample_b", 0)
        if s_a < MINIMUM_COHORT_SAMPLE or s_b < MINIMUM_COHORT_SAMPLE:
            errors.append(f"FORMAT_PLATFORM_ADVANTAGE requires n >= {MINIMUM_COHORT_SAMPLE} on both platforms ({s_a}, {s_b}).")

    # Gate 6: Evidence completeness
    if not candidate.get("signal_identity"):
        errors.append("Missing signal_identity hash.")
    if "platform_values" not in evidence and sig_type not in (
        MultichannelSignalType.CROSS_PLATFORM_DATA_LIMITATION,
        MultichannelSignalType.CROSS_PLATFORM_METRIC_NON_COMPARABLE,
        MultichannelSignalType.INSUFFICIENT_CROSS_PLATFORM_SAMPLE,
        MultichannelSignalType.FORMAT_PLATFORM_ADVANTAGE,
    ):
        errors.append("Evidence missing platform_values.")

    # Gate 7: Confidence consistency
    conf = candidate.get("confidence_level")
    if conf not in (ConfidenceTier.HIGH, ConfidenceTier.MEDIUM, ConfidenceTier.LOW, ConfidenceTier.NONE):
        errors.append(f"Invalid confidence_level '{conf}'.")

    # Gate 8: Actionability consistency
    if not isinstance(candidate.get("is_actionable"), bool):
        errors.append("is_actionable must be a boolean.")

    return len(errors) == 0, errors


# ==============================================================================
# MULTICHANNEL BUSINESS SIGNAL ENGINE SERVICE
# ==============================================================================

def generate_multichannel_signals(
    benchmark: MultichannelBenchmarkResult,
    *,
    persist: bool = False,
    allow_persistence: bool = False,
    language: str = "en",
) -> Dict[str, Any]:
    """
    Deterministic Multichannel Business Signal Engine.
    Consumes a BS-5B MultichannelBenchmarkResult and emits grounded business signals.

    Rules applied:
    - Outperformance signals: rankable metrics with valid winners and material differences.
    - Zero baseline: relative delta set to None; no fabricated percentages.
    - Audience size difference: FOLLOWERS_TOTAL evaluated as informational gauge.
    - Tie suppression: zero-zero ties suppressed from active signals as low-information telemetry.
    - Data limitation: unavailable metrics consolidated into ONE signal with coverage ratio.
    - Non-comparable: structurally non-comparable metrics consolidated into ONE informational signal.
    - Format cohorts: sample size n >= 3 gated strictly.

    Operating modes:
    - persist=False: 100% read-only preview (0 database writes).
    - persist=True: Idempotent persistence with deduplication (requires allow_persistence=True).
    """
    if benchmark is None:
        raise ValueError("Benchmark result must be provided.")

    if benchmark.schema_version != BENCHMARK_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported benchmark schema version '{benchmark.schema_version}'. "
            f"Expected '{BENCHMARK_SCHEMA_VERSION}'. Fail closed."
        )

    client_id = benchmark.client_id
    client = Client.objects.filter(id=client_id).first()
    if not client:
        raise ValueError(f"Client with id {client_id} not found.")

    plat_a = benchmark.platform_a
    plat_b = benchmark.platform_b
    bench_hash = benchmark.benchmark_hash
    start_d = benchmark.period_start
    end_d = benchmark.period_end

    candidate_signals: List[Dict[str, Any]] = []
    suppressed_candidates: List[Dict[str, Any]] = []

    # Map of results by metric
    metric_results = {r.metric: r for r in benchmark.metric_results}

    # --------------------------------------------------------------------------
    # 1. EVALUATE COMPARABLE & RANKABLE METRICS
    # --------------------------------------------------------------------------
    for metric_name in CANONICAL_METRIC_ORDER:
        res = metric_results.get(metric_name)
        if not res:
            continue

        # Case A: FOLLOWERS_TOTAL (Audience volume gauge - non-rankable)
        if metric_name == "FOLLOWERS_TOTAL":
            if res.status == ComparisonStatus.AVAILABLE and res.value_a is not None and res.value_b is not None:
                # Material difference in audience size
                if res.value_a != res.value_b:
                    sig_id = compute_multichannel_signal_identity(
                        client_id=client_id,
                        signal_type=MultichannelSignalType.AUDIENCE_SIZE_DIFFERENCE,
                        benchmark_hash=bench_hash,
                        metric=metric_name,
                        platform_a=plat_a,
                        platform_b=plat_b,
                    )
                    evidence = {
                        "benchmark_hash": bench_hash,
                        "metric": metric_name,
                        "platform_a": plat_a,
                        "platform_b": plat_b,
                        "platform_values": {plat_a: float(res.value_a), plat_b: float(res.value_b)},
                        "delta_absolute": float(res.delta_absolute) if res.delta_absolute is not None else None,
                        "delta_relative": float(res.delta_relative) if res.delta_relative is not None else None,
                        "winner": ComparisonWinner.NO_WINNER.value,
                        "reason_code": res.reason_code.value,
                        "compatibility": res.compatibility.value,
                        "category": SignalCategory.AUDIENCE,
                        "sample_sizes": {plat_a: res.sample_a, plat_b: res.sample_b},
                    }
                    candidate = {
                        "client_id": client_id,
                        "platform": f"{plat_a}:{plat_b}",
                        "signal_type": MultichannelSignalType.AUDIENCE_SIZE_DIFFERENCE,
                        "metric": metric_name,
                        "scope": "multichannel",
                        "object_id": "",
                        "period_start": start_d,
                        "period_end": end_d,
                        "observed_value": res.value_b,
                        "baseline_value": res.value_a,
                        "absolute_delta": res.delta_absolute,
                        "relative_delta": res.delta_relative,
                        "sample_size": res.sample_a + res.sample_b,
                        "confidence_level": ConfidenceTier.HIGH,
                        "direction": "NEUTRAL",
                        "severity": SignalSeverity.INFO,
                        "is_actionable": False,
                        "recommended_action_code": RecommendedActionCode.MAINTAIN_CURRENT_CADENCE,
                        "category": SignalCategory.AUDIENCE,
                        "evidence": evidence,
                        "description": format_signal_description(MultichannelSignalType.AUDIENCE_SIZE_DIFFERENCE, evidence, language),
                        "metadata": {
                            "benchmark_schema_version": benchmark.schema_version,
                            "benchmark_hash": bench_hash,
                            "granularity": benchmark.granularity,
                        },
                        "cohort_hash": bench_hash,
                        "signal_identity": sig_id,
                        "benchmark_hash": bench_hash,
                        "benchmark_schema_version": benchmark.schema_version,
                    }
                    candidate_signals.append(candidate)
            continue

        # Case B: Rankable Metrics with Winner
        if res.rankable and res.status == ComparisonStatus.AVAILABLE:
            # Check for Tie
            if res.winner == ComparisonWinner.TIE:
                # Low-information zero-zero tie suppression rule (COMMENTS 0 vs 0)
                if (res.value_a == Decimal("0") or res.value_a == 0) and (res.value_b == Decimal("0") or res.value_b == 0):
                    suppressed_candidates.append({
                        "metric": metric_name,
                        "signal_type": MultichannelSignalType.CROSS_PLATFORM_TIE,
                        "reason": "LOW_INFORMATION_ZERO_TIE: both platforms recorded 0 interactions. Suppressed to prevent signal spam.",
                        "values": {plat_a: 0, plat_b: 0},
                    })
                    continue

                # Non-zero tie
                sig_id = compute_multichannel_signal_identity(
                    client_id=client_id,
                    signal_type=MultichannelSignalType.CROSS_PLATFORM_TIE,
                    benchmark_hash=bench_hash,
                    metric=metric_name,
                    platform_a=plat_a,
                    platform_b=plat_b,
                )
                evidence = {
                    "benchmark_hash": bench_hash,
                    "metric": metric_name,
                    "platform_a": plat_a,
                    "platform_b": plat_b,
                    "platform_values": {plat_a: float(res.value_a), plat_b: float(res.value_b)},
                    "delta_absolute": 0.0,
                    "delta_relative": 0.0,
                    "winner": ComparisonWinner.TIE.value,
                    "reason_code": res.reason_code.value,
                    "compatibility": res.compatibility.value,
                    "category": SignalCategory.PERFORMANCE,
                    "sample_sizes": {plat_a: res.sample_a, plat_b: res.sample_b},
                }
                candidate = {
                    "client_id": client_id,
                    "platform": f"{plat_a}:{plat_b}",
                    "signal_type": MultichannelSignalType.CROSS_PLATFORM_TIE,
                    "metric": metric_name,
                    "scope": "multichannel",
                    "object_id": "",
                    "period_start": start_d,
                    "period_end": end_d,
                    "observed_value": res.value_a,
                    "baseline_value": res.value_b,
                    "absolute_delta": Decimal("0.0000"),
                    "relative_delta": Decimal("0.0000"),
                    "sample_size": res.sample_a + res.sample_b,
                    "confidence_level": ConfidenceTier.HIGH,
                    "direction": "FLAT",
                    "severity": SignalSeverity.INFO,
                    "is_actionable": False,
                    "recommended_action_code": RecommendedActionCode.MAINTAIN_CURRENT_CADENCE,
                    "category": SignalCategory.PERFORMANCE,
                    "evidence": evidence,
                    "description": format_signal_description(MultichannelSignalType.CROSS_PLATFORM_TIE, evidence, language),
                    "metadata": {
                        "benchmark_schema_version": benchmark.schema_version,
                        "benchmark_hash": bench_hash,
                        "granularity": benchmark.granularity,
                    },
                    "cohort_hash": bench_hash,
                    "signal_identity": sig_id,
                    "benchmark_hash": bench_hash,
                    "benchmark_schema_version": benchmark.schema_version,
                }
                candidate_signals.append(candidate)
                continue

            # Check for Platform Winner (PLATFORM_A or PLATFORM_B)
            if res.winner in (ComparisonWinner.PLATFORM_A, ComparisonWinner.PLATFORM_B):
                winner_plat = plat_a if res.winner == ComparisonWinner.PLATFORM_A else plat_b
                winner_val = res.value_a if res.winner == ComparisonWinner.PLATFORM_A else res.value_b
                baseline_plat = plat_b if res.winner == ComparisonWinner.PLATFORM_A else plat_a
                baseline_val = res.value_b if res.winner == ComparisonWinner.PLATFORM_A else res.value_a

                # Zero-baseline handling (e.g. FB=0 vs IG=6)
                is_zero_baseline = (baseline_val == Decimal("0") or baseline_val == 0)
                abs_delta = abs(res.delta_absolute) if res.delta_absolute is not None else None

                # Materiality evaluation:
                # 1. If baseline > 0, check relative delta >= 20% or absolute delta >= 5
                # 2. If baseline == 0, check absolute delta >= 1 (discrete volume threshold)
                is_material = False
                if is_zero_baseline:
                    is_material = abs_delta is not None and abs_delta >= MATERIALITY_THRESHOLDS["MINIMUM_ABSOLUTE_DELTA_VOLUME"]
                else:
                    if res.delta_relative is not None and abs(res.delta_relative) >= MATERIALITY_THRESHOLDS["MINIMUM_RELATIVE_DELTA_PCT"]:
                        is_material = True
                    elif abs_delta is not None and abs_delta >= MATERIALITY_THRESHOLDS["SIGNIFICANT_ABSOLUTE_DELTA"]:
                        is_material = True

                if not is_material:
                    suppressed_candidates.append({
                        "metric": metric_name,
                        "signal_type": MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE,
                        "reason": f"IMMATERIAL_DELTA: absolute delta ({abs_delta}) below materiality threshold.",
                        "values": {plat_a: float(res.value_a or 0), plat_b: float(res.value_b or 0)},
                    })
                    continue

                sig_id = compute_multichannel_signal_identity(
                    client_id=client_id,
                    signal_type=MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE,
                    benchmark_hash=bench_hash,
                    metric=metric_name,
                    platform_a=plat_a,
                    platform_b=plat_b,
                )

                evidence = {
                    "benchmark_hash": bench_hash,
                    "metric": metric_name,
                    "platform_a": plat_a,
                    "platform_b": plat_b,
                    "winner_platform": winner_plat,
                    "baseline_platform": baseline_plat,
                    "platform_values": {plat_a: float(res.value_a or 0), plat_b: float(res.value_b or 0)},
                    "delta_absolute": float(res.delta_absolute) if res.delta_absolute is not None else None,
                    "delta_relative": float(res.delta_relative) if res.delta_relative is not None else None,
                    "zero_baseline": is_zero_baseline,
                    "winner": res.winner.value,
                    "reason_code": res.reason_code.value,
                    "compatibility": res.compatibility.value,
                    "category": SignalCategory.PERFORMANCE,
                    "sample_sizes": {plat_a: res.sample_a, plat_b: res.sample_b},
                }

                # Confidence derivation
                # High confidence if valid direct metric with full source support
                conf = ConfidenceTier.HIGH
                if (res.sample_a + res.sample_b) < 3:
                    conf = ConfidenceTier.LOW

                candidate = {
                    "client_id": client_id,
                    "platform": winner_plat,
                    "signal_type": MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE,
                    "metric": metric_name,
                    "scope": "multichannel",
                    "object_id": "",
                    "period_start": start_d,
                    "period_end": end_d,
                    "observed_value": winner_val,
                    "baseline_value": baseline_val,
                    "absolute_delta": res.delta_absolute,
                    "relative_delta": res.delta_relative if not is_zero_baseline else None,
                    "sample_size": res.sample_a + res.sample_b,
                    "confidence_level": conf,
                    "direction": "UP",
                    "severity": SignalSeverity.POSITIVE,
                    "is_actionable": True,
                    "recommended_action_code": RecommendedActionCode.REVIEW_PLATFORM_PERFORMANCE,
                    "category": SignalCategory.PERFORMANCE,
                    "evidence": evidence,
                    "description": format_signal_description(MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE, evidence, language),
                    "metadata": {
                        "benchmark_schema_version": benchmark.schema_version,
                        "benchmark_hash": bench_hash,
                        "granularity": benchmark.granularity,
                    },
                    "cohort_hash": bench_hash,
                    "signal_identity": sig_id,
                    "benchmark_hash": bench_hash,
                    "benchmark_schema_version": benchmark.schema_version,
                }
                candidate_signals.append(candidate)

    # --------------------------------------------------------------------------
    # 2. CONSOLIDATED CROSS-PLATFORM DATA LIMITATION SIGNAL
    # --------------------------------------------------------------------------
    # Group unavailable metrics by reason code to avoid signal spam
    unavailable_results = [r for r in benchmark.metric_results if r.status == ComparisonStatus.UNAVAILABLE]
    if unavailable_results:
        unavail_by_reason: Dict[str, List[str]] = {}
        for r in unavailable_results:
            rc = r.reason_code.value
            unavail_by_reason.setdefault(rc, []).append(r.metric)

        affected_metrics = [r.metric for r in unavailable_results]
        total_m = benchmark.coverage_summary.total_metrics
        comp_m = benchmark.coverage_summary.comparable_metrics
        coverage_ratio = f"{comp_m}/{total_m}"

        # Actionable if provider permissions can be updated (e.g. PROVIDER_PARTIAL on Instagram)
        has_provider_partial = (
            ComparisonReasonCode.PROVIDER_PARTIAL.value in unavail_by_reason or
            ComparisonReasonCode.SOURCE_UNAVAILABLE.value in unavail_by_reason
        )

        sig_id = compute_multichannel_signal_identity(
            client_id=client_id,
            signal_type=MultichannelSignalType.CROSS_PLATFORM_DATA_LIMITATION,
            benchmark_hash=bench_hash,
            metric="ALL_UNAVAILABLE",
            platform_a=plat_a,
            platform_b=plat_b,
        )

        prov_lim = plat_b.title() if has_provider_partial else "provider"
        evidence = {
            "benchmark_hash": bench_hash,
            "platform_a": plat_a,
            "platform_b": plat_b,
            "total_metrics": total_m,
            "comparable_metrics": comp_m,
            "coverage_ratio": coverage_ratio,
            "affected_metrics": affected_metrics,
            "affected_metrics_count": len(affected_metrics),
            "unavailable_by_reason": unavail_by_reason,
            "provider_limitations": prov_lim,
            "category": SignalCategory.CAPABILITY,
        }

        candidate = {
            "client_id": client_id,
            "platform": f"{plat_a}:{plat_b}",
            "signal_type": MultichannelSignalType.CROSS_PLATFORM_DATA_LIMITATION,
            "metric": "MULTIPLE",
            "scope": "multichannel",
            "object_id": "",
            "period_start": start_d,
            "period_end": end_d,
            "observed_value": Decimal(str(comp_m)),
            "baseline_value": Decimal(str(total_m)),
            "absolute_delta": Decimal(str(comp_m - total_m)),
            "relative_delta": None,
            "sample_size": len(affected_metrics),
            "confidence_level": ConfidenceTier.HIGH,  # Limitation is deterministically verified
            "direction": "NEUTRAL",
            "severity": SignalSeverity.WARNING if (comp_m / (total_m or 1)) < 0.5 else SignalSeverity.INFO,
            "is_actionable": has_provider_partial,
            "recommended_action_code": (
                RecommendedActionCode.REVIEW_PROVIDER_PERMISSIONS if has_provider_partial
                else RecommendedActionCode.CONTINUE_COLLECTING_DATA
            ),
            "category": SignalCategory.CAPABILITY,
            "evidence": evidence,
            "description": format_signal_description(MultichannelSignalType.CROSS_PLATFORM_DATA_LIMITATION, evidence, language),
            "metadata": {
                "benchmark_schema_version": benchmark.schema_version,
                "benchmark_hash": bench_hash,
                "granularity": benchmark.granularity,
            },
            "cohort_hash": bench_hash,
            "signal_identity": sig_id,
            "benchmark_hash": bench_hash,
            "benchmark_schema_version": benchmark.schema_version,
        }
        candidate_signals.append(candidate)

    # --------------------------------------------------------------------------
    # 3. CONSOLIDATED NON-COMPARABLE METRICS INFORMATIONAL SIGNAL
    # --------------------------------------------------------------------------
    non_comp_results = [r for r in benchmark.metric_results if r.compatibility == ComparisonCompatibility.NON_COMPARABLE]
    if non_comp_results:
        non_comp_metrics = [r.metric for r in non_comp_results]
        sig_id = compute_multichannel_signal_identity(
            client_id=client_id,
            signal_type=MultichannelSignalType.CROSS_PLATFORM_METRIC_NON_COMPARABLE,
            benchmark_hash=bench_hash,
            metric="ALL_NON_COMPARABLE",
            platform_a=plat_a,
            platform_b=plat_b,
        )
        evidence = {
            "benchmark_hash": bench_hash,
            "platform_a": plat_a,
            "platform_b": plat_b,
            "affected_metrics": non_comp_metrics,
            "count": len(non_comp_metrics),
            "category": SignalCategory.DATA_QUALITY,
            "reason": "Heterogeneous platform definitions prevent direct numeric comparison.",
        }
        candidate = {
            "client_id": client_id,
            "platform": f"{plat_a}:{plat_b}",
            "signal_type": MultichannelSignalType.CROSS_PLATFORM_METRIC_NON_COMPARABLE,
            "metric": "MULTIPLE",
            "scope": "multichannel",
            "object_id": "",
            "period_start": start_d,
            "period_end": end_d,
            "observed_value": None,
            "baseline_value": None,
            "absolute_delta": None,
            "relative_delta": None,
            "sample_size": len(non_comp_metrics),
            "confidence_level": ConfidenceTier.HIGH,
            "direction": "NEUTRAL",
            "severity": SignalSeverity.INFO,
            "is_actionable": False,
            "recommended_action_code": RecommendedActionCode.MAINTAIN_CURRENT_CADENCE,
            "category": SignalCategory.DATA_QUALITY,
            "evidence": evidence,
            "description": format_signal_description(MultichannelSignalType.CROSS_PLATFORM_METRIC_NON_COMPARABLE, evidence, language),
            "metadata": {
                "benchmark_schema_version": benchmark.schema_version,
                "benchmark_hash": bench_hash,
                "granularity": benchmark.granularity,
            },
            "cohort_hash": bench_hash,
            "signal_identity": sig_id,
            "benchmark_hash": bench_hash,
            "benchmark_schema_version": benchmark.schema_version,
        }
        candidate_signals.append(candidate)

    # --------------------------------------------------------------------------
    # 4. CONTENT COHORT FORMAT BENCHMARKS (IF PRESENT)
    # --------------------------------------------------------------------------
    if benchmark.cohort_results:
        for cohort in benchmark.cohort_results:
            c_val = cohort.get("cohort_value", "")
            s_a = cohort.get("sample_a", 0)
            s_b = cohort.get("sample_b", 0)

            # Sample size gating (n < 3 on either platform)
            if s_a < MINIMUM_COHORT_SAMPLE or s_b < MINIMUM_COHORT_SAMPLE:
                sig_id = compute_multichannel_signal_identity(
                    client_id=client_id,
                    signal_type=MultichannelSignalType.INSUFFICIENT_CROSS_PLATFORM_SAMPLE,
                    benchmark_hash=bench_hash,
                    metric=f"FORMAT_{c_val}",
                    platform_a=plat_a,
                    platform_b=plat_b,
                    cohort_key=c_val,
                )
                evidence = {
                    "benchmark_hash": bench_hash,
                    "platform_a": plat_a,
                    "platform_b": plat_b,
                    "format": c_val,
                    "sample_a": s_a,
                    "sample_b": s_b,
                    "minimum_sample": MINIMUM_COHORT_SAMPLE,
                    "platform_values": {plat_a: s_a, plat_b: s_b},
                    "category": SignalCategory.FORMAT,
                }
                candidate = {
                    "client_id": client_id,
                    "platform": f"{plat_a}:{plat_b}",
                    "signal_type": MultichannelSignalType.INSUFFICIENT_CROSS_PLATFORM_SAMPLE,
                    "metric": f"FORMAT_{c_val}",
                    "scope": "multichannel",
                    "object_id": "",
                    "period_start": start_d,
                    "period_end": end_d,
                    "observed_value": Decimal(str(max(s_a, s_b))),
                    "baseline_value": Decimal(str(MINIMUM_COHORT_SAMPLE)),
                    "absolute_delta": Decimal(str(min(s_a, s_b) - MINIMUM_COHORT_SAMPLE)),
                    "relative_delta": None,
                    "sample_size": s_a + s_b,
                    "confidence_level": ConfidenceTier.NONE,
                    "direction": "NEUTRAL",
                    "severity": SignalSeverity.INFO,
                    "is_actionable": True,
                    "recommended_action_code": RecommendedActionCode.CONTINUE_COLLECTING_DATA,
                    "category": SignalCategory.FORMAT,
                    "evidence": evidence,
                    "description": format_signal_description(MultichannelSignalType.INSUFFICIENT_CROSS_PLATFORM_SAMPLE, evidence, language),
                    "metadata": {
                        "benchmark_schema_version": benchmark.schema_version,
                        "benchmark_hash": bench_hash,
                        "format": c_val,
                    },
                    "cohort_hash": bench_hash,
                    "signal_identity": sig_id,
                    "benchmark_hash": bench_hash,
                    "benchmark_schema_version": benchmark.schema_version,
                }
                candidate_signals.append(candidate)
            else:
                # Adequate sample (n >= 3 both platforms)
                c_winner = cohort.get("winner", ComparisonWinner.NO_WINNER.value)
                if c_winner in (ComparisonWinner.PLATFORM_A.value, ComparisonWinner.PLATFORM_B.value):
                    winner_plat = plat_a if c_winner == ComparisonWinner.PLATFORM_A.value else plat_b
                    sig_id = compute_multichannel_signal_identity(
                        client_id=client_id,
                        signal_type=MultichannelSignalType.FORMAT_PLATFORM_ADVANTAGE,
                        benchmark_hash=bench_hash,
                        metric=f"FORMAT_{c_val}",
                        platform_a=plat_a,
                        platform_b=plat_b,
                        cohort_key=c_val,
                    )
                    evidence = {
                        "benchmark_hash": bench_hash,
                        "platform_a": plat_a,
                        "platform_b": plat_b,
                        "winner_platform": winner_plat,
                        "format": c_val,
                        "sample_a": s_a,
                        "sample_b": s_b,
                        "minimum_sample": MINIMUM_COHORT_SAMPLE,
                        "platform_values": {plat_a: s_a, plat_b: s_b},
                        "category": SignalCategory.FORMAT,
                    }
                    candidate = {
                        "client_id": client_id,
                        "platform": winner_plat,
                        "signal_type": MultichannelSignalType.FORMAT_PLATFORM_ADVANTAGE,
                        "metric": f"FORMAT_{c_val}",
                        "scope": "multichannel",
                        "object_id": "",
                        "period_start": start_d,
                        "period_end": end_d,
                        "observed_value": Decimal(str(max(s_a, s_b))),
                        "baseline_value": Decimal(str(min(s_a, s_b))),
                        "absolute_delta": Decimal(str(abs(s_a - s_b))),
                        "relative_delta": None,
                        "sample_size": s_a + s_b,
                        "confidence_level": ConfidenceTier.HIGH if (s_a >= 10 and s_b >= 10) else ConfidenceTier.MEDIUM,
                        "direction": "UP",
                        "severity": SignalSeverity.POSITIVE,
                        "is_actionable": True,
                        "recommended_action_code": RecommendedActionCode.REVIEW_PLATFORM_PERFORMANCE,
                        "category": SignalCategory.FORMAT,
                        "evidence": evidence,
                        "description": format_signal_description(MultichannelSignalType.FORMAT_PLATFORM_ADVANTAGE, evidence, language),
                        "metadata": {
                            "benchmark_schema_version": benchmark.schema_version,
                            "benchmark_hash": bench_hash,
                            "format": c_val,
                        },
                        "cohort_hash": bench_hash,
                        "signal_identity": sig_id,
                        "benchmark_hash": bench_hash,
                        "benchmark_schema_version": benchmark.schema_version,
                    }
                    candidate_signals.append(candidate)

    # --------------------------------------------------------------------------
    # 5. VALIDATION GATES FOR ALL CANDIDATES
    # --------------------------------------------------------------------------
    validated_signals: List[Dict[str, Any]] = []
    for cand in candidate_signals:
        is_valid, validation_errors = validate_signal_candidate(cand, benchmark)
        if not is_valid:
            logger.error(
                "Candidate signal %s failed validation: %s",
                cand.get("signal_type"),
                validation_errors,
            )
            raise MultichannelSignalValidationError(
                f"Candidate signal failed validation: {'; '.join(validation_errors)}"
            )
        cand["validation_passed"] = True
        validated_signals.append(cand)

    # --------------------------------------------------------------------------
    # 6. PERSISTENCE GATE (FAIL CLOSED)
    # --------------------------------------------------------------------------
    persisted_signals: List[BusinessSignal] = []
    if persist:
        if not allow_persistence:
            raise PermissionError(
                "Persistence of multichannel business signals is prohibited in this phase "
                "without explicit operator authorization (allow_persistence=True)."
            )

        for s_dict in validated_signals:
            identity = s_dict["signal_identity"]
            obj, _ = BusinessSignal.objects.update_or_create(
                signal_identity=identity,
                defaults={
                    "client": client,
                    "platform": s_dict["platform"],
                    "signal_type": s_dict["signal_type"],
                    "metric": s_dict["metric"],
                    "scope": s_dict["scope"],
                    "object_id": s_dict.get("object_id", ""),
                    "period_start": s_dict["period_start"],
                    "period_end": s_dict["period_end"],
                    "observed_value": s_dict.get("observed_value"),
                    "baseline_value": s_dict.get("baseline_value"),
                    "absolute_delta": s_dict.get("absolute_delta"),
                    "relative_delta": s_dict.get("relative_delta"),
                    "sample_size": s_dict.get("sample_size", 0),
                    "confidence_level": s_dict.get("confidence_level", "NONE"),
                    "direction": s_dict.get("direction", "NEUTRAL"),
                    "severity": s_dict.get("severity", "INFO"),
                    "is_actionable": s_dict.get("is_actionable", False),
                    "evidence": s_dict.get("evidence", {}),
                    "explanation_template": s_dict.get("description", ""),
                    "metadata": s_dict.get("metadata", {}),
                    "cohort_hash": s_dict.get("cohort_hash", ""),
                },
            )
            persisted_signals.append(obj)

    return {
        "benchmark_hash": bench_hash,
        "candidate_signals": validated_signals,
        "candidate_count": len(validated_signals),
        "suppressed_candidates": suppressed_candidates,
        "suppressed_count": len(suppressed_candidates),
        "persisted_count": len(persisted_signals),
        "persisted_signals": persisted_signals,
    }
