"""
Deterministic Validation Pipeline for Grounded AI Executive Narrative (BS-4H).
Validates schema, facts, metric availability, sample locks, confidence locks, causality, and evidence.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple

from .confidence import derive_recommendation_confidence
from .schemas import (
    RECOMMENDATION_TAXONOMY,
    RECOMMENDATION_STRENGTHS,
    CONFIDENCE_LEVELS,
)


def _extract_all_numbers(text: str) -> Set[float]:
    """
    Extracts all numeric values (integers, floats, percentages) from a string.
    Normalizes commas/periods.
    """
    cleaned = text.replace(",", "")
    matches = re.findall(r"(?<![a-zA-Z_])[-+]?\d*\.?\d+(?:%)?", cleaned)
    numbers = set()
    for m in matches:
        raw = m.rstrip("%")
        try:
            val = float(raw)
            numbers.add(val)
        except ValueError:
            pass
    return numbers


def _collect_context_numbers(context: Dict[str, Any]) -> Set[float]:
    """
    Recursively collects all numeric values present in the grounded context.
    Also includes standard allowable reference integers (1-10) and dates.
    """
    context_numbers = set()

    def _walk(obj):
        if isinstance(obj, (int, float)):
            context_numbers.add(float(obj))
        elif isinstance(obj, str):
            for n in _extract_all_numbers(obj):
                context_numbers.add(n)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                _walk(v)
        elif isinstance(obj, (list, tuple, set)):
            for item in obj:
                _walk(item)

    _walk(context)
    # Allow natural reference indexes 1 through 10
    for i in range(1, 11):
        context_numbers.add(float(i))
    return context_numbers


def _extract_sentences(text: str) -> List[str]:
    """Splits a block of text into individual sentences, preserving sentence-level context."""
    raw_sentences = re.split(r'(?<=[.!?;\n])\s+', text)
    sentences = []
    for s in raw_sentences:
        clean = s.strip()
        if clean:
            sentences.append(clean)
    return sentences


# Canonical metric keys mapped to regex patterns (English and Spanish)
METRIC_ALIASES: Dict[str, List[str]] = {
    "reach": [
        r"\breach\b",
        r"\breached\b",
        r"\balcance\b",
        r"\balcanz(?:ó|aron|ado|ar)?\b",
    ],
    "average_daily_reach": [
        r"\baverage daily reach\b",
        r"\bdaily reach\b",
        r"\balcance diario promedio\b",
        r"\balcance diario\b",
    ],
    "shares": [
        r"\bshares\b",
        r"\bcompartidos\b",
        r"\bcompartidas\b",
        r"\bveces compartido\b",
    ],
    "saves": [
        r"\bsaves\b",
        r"\bguardados\b",
        r"\bguardadas\b",
    ],
    "video_views": [
        r"\bvideo views\b",
        r"\bvisualizaciones de video\b",
        r"\breproducciones de video\b",
        r"\bvistas de video\b",
    ],
    "engagement_total": [
        r"\bengagement total\b",
        r"\btotal engagement\b",
        r"\binteracciones totales\b",
        r"\binteracción total\b",
    ],
    "impressions": [
        r"\bimpressions\b",
        r"\bimpresiones\b",
    ],
    "profile_views": [
        r"\bprofile views\b",
        r"\bvisitas al perfil\b",
        r"\bvistas al perfil\b",
    ],
    "clicks_total": [
        r"\bclicks total\b",
        r"\btotal clicks\b",
        r"\bclics totales\b",
        r"\bclics\b",
    ],
}

AVAILABLE_METRIC_ALIASES: Dict[str, List[str]] = {
    "followers_total": [r"\bfollowers\b", r"\bseguidores\b"],
    "reactions": [r"\breactions\b", r"\breacciones\b"],
    "comments": [r"\bcomments\b", r"\bcomentarios\b"],
}

AVAILABILITY_PATTERNS: List[str] = [
    r"\bunavailable\b",
    r"\bnot\s+(?:\w+\s+)?available\b",
    r"\bunsupported\b",
    r"\bnot\s+(?:\w+\s+)?supported\b",
    r"\bnot\s+(?:\w+\s+)?provided\b",
    r"\bnot\s+(?:\w+\s+)?exposed\b",
    r"\bnot\s+(?:\w+\s+)?accessible\b",
    r"\bnot\s+(?:\w+\s+)?reported\b",
    r"\bremain\s+unavailable\b",
    r"\bcannot be evaluated\b",
    r"\bno actionable insights can be generated\b",
    r"\bunlock unavailable metrics\b",
    r"\boperating in partial capability mode\b",
    r"\bpartial capability mode\b",
    r"\bpartial api access\b",
    r"\bmissing (?:meta|provider)?\s*permissions\b",
    r"\bmissing permissions\b",
    r"\bprovider constraints\b",
    r"\bno disponible(?:s)?\b",
    r"\bno\s+(?:\w+\s+)?disponible(?:s)?\b",
    r"\bno\s+(?:\w+\s+)?provisto(?:s)?\b",
    r"\bno\s+(?:\w+\s+)?suministrado(?:s)?\b",
    r"\bno\s+(?:\w+\s+)?expuesto(?:s)?\b",
    r"\bno\s+(?:\w+\s+)?accesible(?:s)?\b",
    r"\bno\s+(?:\w+\s+)?soportado(?:s)?\b",
    r"\bno\s+(?:\w+\s+)?compatible(?:s)?\b",
    r"\bno\s+(?:\w+\s+)?reportado(?:s)?\b",
    r"\bpermanecen no disponible(?:s)?\b",
    r"\bno puede(?:n)? ser evaluado(?:s)?\b",
    r"\bcapacidad parcial\b",
    r"\bpermisos faltantes\b",
    r"\bfaltante debido a permisos\b",
    r"\bdesbloquear métricas no disponibles\b",
    r"\bnot\s+(?:\w+\s+)?comparable\b",
    r"\bnot\s+directly\s+comparable\b",
    r"\bno\s+(?:\w+\s+)?comparable(?:s)?\b",
    r"\bno\s+directamente\s+comparable(?:s)?\b",
    r"\bno\s+(?:se\s+)?comparan?\b",
    r"\bno\s+admiten\s+(?:una\s+)?comparaci.n\b",
    r"\bdiferencias\s+sem.nticas\b",
    r"\bdivergencia\s+sem.ntica\b",
    r"\bdefiniciones\s+sem.nticas\b",
]

NON_COMPARABLE_PATTERNS: List[str] = [
    r"\bnot\s+(?:\w+\s+)?comparable\b",
    r"\bnot\s+directly\s+comparable\b",
    r"\bno\s+(?:\w+\s+)?comparable(?:s)?\b",
    r"\bno\s+directamente\s+comparable(?:s)?\b",
    r"\bno\s+(?:se\s+)?comparan?\b",
    r"\bno\s+admiten\s+(?:una\s+)?comparaci.n\b",
    r"\bdiferencias\s+sem.nticas\b",
    r"\bdivergencia\s+sem.ntica\b",
    r"\bdefiniciones\s+sem.nticas\b",
]

OVERALL_WINNER_PATTERNS: List[str] = [
    r"\bpeor plataforma\b",
    r"\bworst platform\b",
    r"\b(?:canal|plataforma)\s+m[aá]s\s+fuerte\b",
    r"\bstrongest\s+(?:channel|platform)\b",
    r"\breplace\s+(?:facebook|instagram|fb|ig)\b",
    r"\breemplaz(?:ar|e)\s+a?\s*(?:facebook|instagram|fb|ig)\b",
    r"\b(?:wins|loses|gan[oó]|perdi[oó])\s+(?:overall|en general)\b",
    r"\b(?:instagram|facebook|ig|fb)\s+(?:es la mejor plataforma|es la peor plataforma|es el canal m[aá]s fuerte|es el mejor canal|wins overall|loses overall|should replace)\b",
    r"\bganador general\b",
    r"\bganadora general\b",
    r"\bplataforma ganadora\b",
    r"\bganó en general\b",
    r"\boverall winner\b",
    r"\bbest platform\b",
    r"\boverall platform winner\b",
    r"\bplataforma superior en general\b",
    r"\bganador entre plataformas\b",
    r"\bsuperó en general\b",
    r"\bmejor plataforma\b",
    r"\bwinning platform\b",
]

SYNTHETIC_AGGREGATION_PATTERNS: List[str] = [
    r"\bpuntuaci[oó]n compuesta\b",
    r"\bcomposite score\b",
    r"\brank(?:ing)? general\b",
    r"\boverall rank(?:ing)?\b",
    r"\bpuntaje ponderado\b",
    r"\bweighted score\b",
    r"\bdesempeño sintetizado\b",
    r"\bsynthetic performance\b",
    r"\brendimiento combinado\b",
    r"\bcombined performance\b",
]

CLAIM_FORBIDDEN_PATTERNS: List[str] = [
    # Numeric values and percentages
    r"\d",
    r"%",
    r"\bpercent\b",
    r"\bpor ciento\b",
    # Trend verbs and directional changes
    r"\bincreas(?:e|ed|ing|es)\b",
    r"\bdecreas(?:e|ed|ing|es)\b",
    r"\bgrew\b",
    r"\bgrow(?:th|ing|s)?\b",
    r"\bfell\b",
    r"\bfall(?:ing|s)?\b",
    r"\bdeclin(?:e|ed|ing|es)\b",
    r"\bdropp(?:ed|ing)\b",
    r"\bdrop(?:s)?\b",
    r"\bimprov(?:e|ed|ing|es|ement)\b",
    r"\bworsen(?:ed|ing|s)?\b",
    r"\baument(?:ó|aron|ar|ado|an|o)\b",
    r"\bdisminu(?:yó|yeron|ir|ido|yen|ción)\b",
    r"\bcreci(?:ó|eron|miento)\b",
    r"\bcay(?:ó|eron)\b",
    r"\bmejor(?:ó|aron|ar|ado|an|ía|a)?\b",
    r"\bempeor(?:ó|aron|ar|ado)\b",
    r"\breducci(?:ón|ones)\b",
    # Performance adjectives and phrases
    r"\bperforming well\b",
    r"\bperformance\b",
    r"\bstrong\b",
    r"\bweak\b",
    r"\bgood\b",
    r"\bbad\b",
    r"\bbest\b",
    r"\bworst\b",
    r"\bfuerte\b",
    r"\bdébil\b",
    r"\bbueno\b",
    r"\bmalo\b",
    r"\bóptimo\b",
    r"\bdesempeño\b",
    r"\brendimiento\b",
    # Comparison language
    r"\bhigher\b",
    r"\blower\b",
    r"\bmore\b",
    r"\bless\b",
    r"\bthan\b",
    r"\bcompared to\b",
    r"\bmayor\b",
    r"\bmenor\b",
    r"\bmás\b",
    r"\bmenos\b",
    r"\bcomparado\b",
    # Ranking language
    r"\btop\b",
    r"\bbottom\b",
    r"\brank(?:ed|ing|s)?\b",
    r"\bprimero\b",
    r"\búltimo\b",
]

CONFIDENCE_RANK: Dict[str, int] = {
    "NONE": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}


class NarrativeValidator:
    """
    Deterministic validator running all BS-4H verification gates.
    """

    @classmethod
    def validate(cls, output: Any, context: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        errors = []
        checks = {
            "json_schema": False,
            "facts_supported": False,
            "metrics_supported": False,
            "insufficient_sample_preserved": False,
            "confidence_preserved": False,
            "causality_safe": False,
            "recommendations_grounded": False,
            "multichannel_safety": False,
        }

        # 1. JSON Schema validation
        if not isinstance(output, dict):
            errors.append("Output must be a valid JSON object.")
            return False, {"status": "FAIL", "results": checks, "errors": errors}

        required_keys = ["executive_summary", "performance_observations", "recommendations", "limitations"]
        missing_keys = [k for k in required_keys if k not in output]
        if missing_keys:
            errors.append(f"Missing required keys in output: {', '.join(missing_keys)}")
            return False, {"status": "FAIL", "results": checks, "errors": errors}

        # Root-level additionalProperties: false enforcement
        allowed_root_keys = set(required_keys) | {"cross_platform_coverage_disclosure"}
        extra_root_keys = set(output.keys()) - allowed_root_keys
        if extra_root_keys:
            errors.append(f"Unexpected extra root keys in output: {', '.join(sorted(extra_root_keys))}")
            return False, {"status": "FAIL", "results": checks, "errors": errors}

        if not all(isinstance(output[k], list) for k in required_keys):
            errors.append("All top-level sections must be lists.")
            return False, {"status": "FAIL", "results": checks, "errors": errors}

        # Validate optional structured cross-platform coverage disclosure
        if "cross_platform_coverage_disclosure" in output:
            cov_disc = output["cross_platform_coverage_disclosure"]
            if not isinstance(cov_disc, dict):
                errors.append("cross_platform_coverage_disclosure must be an object.")
            else:
                req_disc_keys = {"comparable_metrics", "total_metrics", "status", "statement"}
                extra_disc_keys = set(cov_disc.keys()) - req_disc_keys
                if extra_disc_keys:
                    errors.append(f"cross_platform_coverage_disclosure has unexpected extra keys: {', '.join(sorted(extra_disc_keys))}.")
                if not isinstance(cov_disc.get("comparable_metrics"), int):
                    errors.append("cross_platform_coverage_disclosure.comparable_metrics must be an integer.")
                if not isinstance(cov_disc.get("total_metrics"), int):
                    errors.append("cross_platform_coverage_disclosure.total_metrics must be an integer.")
                if not isinstance(cov_disc.get("status"), str):
                    errors.append("cross_platform_coverage_disclosure.status must be a string.")
                if not isinstance(cov_disc.get("statement"), str) or not cov_disc.get("statement").strip():
                    errors.append("cross_platform_coverage_disclosure.statement must be a non-empty string.")

        # Validate executive_summary bounds (minItems: 1, maxItems: 5)
        exec_summary = output["executive_summary"]
        if len(exec_summary) < 1:
            errors.append("executive_summary must contain at least 1 item.")
        elif len(exec_summary) > 5:
            errors.append("executive_summary exceeds maximum limit of 5 items.")
        if not all(isinstance(item, str) and item.strip() for item in exec_summary):
            errors.append("All items in executive_summary must be non-empty strings.")

        # Validate performance_observations bounds (minItems: 1, maxItems: 6)
        perf_obs = output["performance_observations"]
        if len(perf_obs) < 1:
            errors.append("performance_observations must contain at least 1 item.")
        elif len(perf_obs) > 6:
            errors.append("performance_observations exceeds maximum limit of 6 items.")
        if not all(isinstance(item, str) and item.strip() for item in perf_obs):
            errors.append("All items in performance_observations must be non-empty strings.")

        # Validate limitations bounds (minItems: 1, maxItems: 5)
        limitations = output["limitations"]
        if len(limitations) < 1:
            errors.append("limitations must contain at least 1 item.")
        elif len(limitations) > 5:
            errors.append("limitations exceeds maximum limit of 5 items.")
        if not all(isinstance(item, str) and item.strip() for item in limitations):
            errors.append("All items in limitations must be non-empty strings.")

        # Validate recommendations schema (minItems: 0, maxItems: 5)
        recs = output.get("recommendations", [])
        if len(recs) > 5:
            errors.append("recommendations exceeds maximum limit of 5 items.")

        allowed_rec_keys = {"text", "recommendation_type", "strength", "confidence", "evidence_refs"}
        for idx, rec in enumerate(recs):
            if not isinstance(rec, dict):
                errors.append(f"Recommendation #{idx + 1} is not an object.")
                continue
            extra_rec_keys = set(rec.keys()) - allowed_rec_keys
            if extra_rec_keys:
                errors.append(f"Recommendation #{idx + 1} has unexpected extra keys: {', '.join(sorted(extra_rec_keys))}.")
            if not rec.get("text") or not isinstance(rec.get("text"), str):
                errors.append(f"Recommendation #{idx + 1} has missing or empty text.")
            if rec.get("recommendation_type") not in RECOMMENDATION_TAXONOMY:
                errors.append(f"Recommendation #{idx + 1} has invalid taxonomy: '{rec.get('recommendation_type')}'.")
            if rec.get("strength") not in RECOMMENDATION_STRENGTHS:
                errors.append(f"Recommendation #{idx + 1} has invalid strength: '{rec.get('strength')}'.")
            if rec.get("confidence") not in CONFIDENCE_LEVELS:
                errors.append(f"Recommendation #{idx + 1} has invalid confidence: '{rec.get('confidence')}'.")
            if not isinstance(rec.get("evidence_refs"), list) or len(rec.get("evidence_refs", [])) == 0:
                errors.append(f"Recommendation #{idx + 1} must include a non-empty evidence_refs list.")
            elif not all(isinstance(ref, str) and ref.strip() for ref in rec.get("evidence_refs", [])):
                errors.append(f"Recommendation #{idx + 1} evidence_refs must all be non-empty strings.")

        if errors:
            return False, {"status": "FAIL", "results": checks, "errors": errors}
        checks["json_schema"] = True

        # Extract all text from output for text-based checks
        all_text_parts = []
        for s in output.get("executive_summary", []):
            if isinstance(s, str):
                all_text_parts.append(s)
        for s in output.get("performance_observations", []):
            if isinstance(s, str):
                all_text_parts.append(s)
        for r in recs:
            if isinstance(r, dict) and "text" in r:
                all_text_parts.append(r["text"])
        for lim in output.get("limitations", []):
            if isinstance(lim, str):
                all_text_parts.append(lim)
        if "cross_platform_coverage_disclosure" in output and isinstance(output["cross_platform_coverage_disclosure"], dict):
            disc_stmt = output["cross_platform_coverage_disclosure"].get("statement")
            if isinstance(disc_stmt, str):
                all_text_parts.append(disc_stmt)

        full_text = " ".join(all_text_parts)
        full_text_lower = full_text.lower()

        # 2. Fact Lock: Validate numbers against context
        context_numbers = _collect_context_numbers(context)
        output_numbers = _extract_all_numbers(full_text)
        unsupported_numbers = []
        for num in output_numbers:
            # Check if num or close approximation exists in context numbers
            if not any(abs(num - c_num) < 0.001 for c_num in context_numbers):
                unsupported_numbers.append(num)

        if unsupported_numbers:
            errors.append(f"Fact lock failed: Output contains unsupported numeric facts: {unsupported_numbers}")
        else:
            checks["facts_supported"] = True

        # 3. Metric Allowlist: Context-aware availability vs claim checking
        all_sentences = []
        for part in all_text_parts:
            all_sentences.extend(_extract_sentences(part))

        platforms = context.get("platforms", {})
        platform_capabilities = {}
        for p_name, p_data in platforms.items():
            if not isinstance(p_data, dict):
                continue
            p_name_lower = p_name.lower()
            unavail = [m.lower() for m in (p_data.get("unavailable_metrics") or p_data.get("unsupported_metrics") or [])]
            avail = [m.lower() for m in (p_data.get("available_metrics") or p_data.get("supported_metrics") or [])]
            if p_data.get("status") in ("PARTIAL", "DEGRADED") and not unavail:
                unavail = ["reach", "shares", "saves", "video_views", "engagement_total"]
            platform_capabilities[p_name_lower] = {
                "status": p_data.get("status", "FULL"),
                "unavailable": set(unavail),
                "available": set(avail),
            }

        all_unavailable = set()
        for cap in platform_capabilities.values():
            all_unavailable.update(cap["unavailable"])

        for sent in all_sentences:
            sent_lower = sent.lower()

            # A. Check for contradicted availability claims (Section H & X)
            has_avail_wording = any(re.search(pat, sent_lower) for pat in AVAILABILITY_PATTERNS)
            if has_avail_wording:
                # 1. Claiming an available metric is unavailable
                for m_key, patterns in AVAILABLE_METRIC_ALIASES.items():
                    if any(re.search(pat, sent_lower) for pat in patterns):
                        for p_name, cap in platform_capabilities.items():
                            if p_name in sent_lower or len(platform_capabilities) == 1:
                                if m_key in cap["available"] or m_key not in cap["unavailable"]:
                                    errors.append(
                                        f"Metric allowlist failed: Contradicted capability: Claimed metric '{m_key}' "
                                        f"is unavailable, but it is supported/available in context for {p_name}."
                                    )
                                    break

                # 2. Claiming an unavailable metric is unavailable on a platform where it IS available
                for m_key, patterns in METRIC_ALIASES.items():
                    if any(re.search(pat, sent_lower) for pat in patterns):
                        if any(re.search(p, sent_lower) for p in NON_COMPARABLE_PATTERNS):
                            continue
                        for p_name, cap in platform_capabilities.items():
                            if p_name in sent_lower and m_key in cap["available"]:
                                errors.append(
                                    f"Metric allowlist failed: Contradicted capability: Claimed metric '{m_key}' "
                                    f"is unavailable for {p_name}, but metric is supported/available in context."
                                )

            # B. Check mentions of unavailable metrics
            for m_key, patterns in METRIC_ALIASES.items():
                if m_key not in all_unavailable:
                    continue

                metric_matched = any(re.search(pat, sent_lower) for pat in patterns)
                if not metric_matched:
                    continue

                # Determine which platform this metric belongs to
                ref_platform = None
                for p_name, cap in platform_capabilities.items():
                    if m_key in cap["unavailable"]:
                        ref_platform = p_name
                        break
                platform_label = ref_platform.capitalize() if ref_platform else "Provider"

                # Check for claim forbidden patterns (digits, trends, percentages, comparisons, performance)
                found_forbidden = []
                for c_pat in CLAIM_FORBIDDEN_PATTERNS:
                    m = re.search(c_pat, sent_lower)
                    if m:
                        found_forbidden.append(m.group(0))

                is_availability = any(re.search(a_pat, sent_lower) for a_pat in AVAILABILITY_PATTERNS)

                if found_forbidden and is_availability:
                    # Mixed / ambiguous statement: combines availability wording with performance/trend claim
                    errors.append(
                        f"Metric allowlist failed: Mixed statement combines availability wording with "
                        f"unsupported claim/trend/value ('{found_forbidden[0]}') for unavailable {platform_label} metric '{m_key}'."
                    )
                elif found_forbidden and not is_availability:
                    # Direct performance or numeric claim on unavailable metric
                    errors.append(
                        f"Metric allowlist failed: Unsupported numeric or performance claim for unavailable {platform_label} metric '{m_key}'."
                    )
                elif not is_availability:
                    # Mentioned without availability qualification
                    errors.append(
                        f"Metric allowlist failed: Unavailable {platform_label} metric '{m_key}' mentioned without availability statement."
                    )
                else:
                    # Valid availability description (matches availability pattern, no forbidden claim patterns)
                    pass

        if not any("Metric allowlist failed" in e for e in errors):
            checks["metrics_supported"] = True

        # 4. Insufficient Sample Lock
        has_sufficient_data = context.get("has_sufficient_data", True)
        signals = context.get("signals", [])
        has_insufficient_sample_signals = any(s.get("signal_type") == "INSUFFICIENT_SAMPLE" for s in signals)

        if not has_sufficient_data or has_insufficient_sample_signals:
            forbidden_phrases = [
                "are your best format",
                "is your best format",
                "are your best-performing format",
                "is your best-performing format",
                "es tu mejor formato",
                "son tu mejor formato",
                "formato ganador es",
                "el formato ganador es",
                "winning format is",
                "best time to post is",
                "mejor hora para publicar es",
            ]
            for phrase in forbidden_phrases:
                if phrase in full_text_lower:
                    errors.append(f"Insufficient sample lock failed: Output claims definitive format/time outcome '{phrase}' with insufficient data.")
                    break

        if not any("Insufficient sample lock failed" in e for e in errors):
            checks["insufficient_sample_preserved"] = True

        # 5. Confidence Lock: Verify canonical confidence matches deterministic derivation
        evidence_registry = context.get("evidence_registry", {})
        for idx, rec in enumerate(recs):
            rec_conf = rec.get("confidence")
            rec_refs = rec.get("evidence_refs", [])
            if not rec_refs:
                continue

            try:
                expected_conf = derive_recommendation_confidence(rec_refs, evidence_registry)
                if rec_conf != expected_conf:
                    refs_str = ", ".join(rec_refs)
                    errors.append(
                        f"Confidence lock failed: Recommendation #{idx + 1} confidence '{rec_conf}' "
                        f"exceeds allowed '{expected_conf}' from evidence refs [{refs_str}]."
                    )
            except ValueError as e:
                errors.append(f"Confidence lock failed: Recommendation #{idx + 1} evidence resolution failed: {e}")

        if not any("Confidence lock failed" in e for e in errors):
            checks["confidence_preserved"] = True

        # 6. Causality Guard (Precision-scoped in BS-5E.1C)
        unsupported_causal_tokens = [
            r"\bcaused\b",
            r"\byour audience prefers\b",
            r"\bthis proves\b",
            r"\bthis strategy drove\b",
            r"\bcausó\b",
            r"\bprovocó\b",
            r"\btu audiencia prefiere\b",
            r"\besto demuestra\b",
            r"\besta estrategia impulsó\b",
            r"\bdebido a su contenido\b",
            r"\bdebido a la calidad\b",
            r"\bdebido a la creatividad\b",
            r"\bdebido a las publicaciones\b",
            r"\bdebido al contenido\b",
            r"\bdebido a que su contenido\b",
            r"\bdebido a que la calidad\b",
            r"\bdebido a que la estrategia\b",
        ]
        for pattern in unsupported_causal_tokens:
            if re.search(pattern, full_text_lower):
                errors.append(f"Causality guard failed: Found unsupported causal phrase matching '{pattern}'.")
                break

        # Check connectives: allow definitional/mathematical explanations, reject performance attribution
        approved_definitional_causal_patterns = [
            r"(?:debido a que|porque|ya que|because)\s+(?:la\s+)?l[ií]nea\s+base(?:\s+observada)?(?:\s+en\s+\w+)?\s+es\s+cero",
            r"(?:debido a que|porque|ya que|because)\s+la\s+línea\s+base\s+observada\s+es\s+cero",
            r"(?:debido a que|porque|ya que|because)\s+(?:se\s+trata\s+de\s+|es\s+)?(?:una\s+)?m[eé]trica\s+de\s+(?:escala|volumen|audiencia)",
            r"(?:debido a que|porque|ya que|because)\s+followers_total\s+es\s+(?:una\s+)?m[eé]trica\s+de\s+volumen",
            r"(?:debido a que|porque|ya que|because)\s+se\s+trata\s+de\s+una\s+m[eé]trica\s+de\s+escala\s+absoluta",
            r"(?:debido a que|porque|ya que|because)\s+(?:existen\s+|se\s+observan\s+)?(?:las\s+)?diferencias\s+en\s+las\s+definiciones",
            r"(?:debido a que|porque|ya que|because)\s+(?:existen\s+|se\s+observan\s+)?diferencias\s+(?:sem[aá]nticas|de\s+definici[oó]n)",
            r"(?:debido a que|porque|ya que|because)\s+restricciones\s+de\s+api",
            r"(?:debido a que|porque|ya que|because)\s+la\s+configuraci[oó]n\s+actual\s+del\s+proveedor",
        ]

        connective_patterns = [
            r"\bya que\b",
            r"\bporque\b",
            r"\bbecause\b",
            r"\bdebido a que\b",
        ]
        for sent in all_sentences:
            s_low = sent.lower()
            for conn_pat in connective_patterns:
                if re.search(conn_pat, s_low):
                    # Must match at least one approved definitional/mathematical explanation
                    matches_approved = any(re.search(ad_pat, s_low) for ad_pat in approved_definitional_causal_patterns)
                    if not matches_approved:
                        errors.append(f"Causality guard failed: Found unsupported causal phrase matching '{conn_pat}'.")
                        break

        if not any("Causality guard failed" in e for e in errors):
            checks["causality_safe"] = True

        # 6B. Multichannel Safety Locks (BS-5D, BS-5E)
        # Gate A: Overall Winner Lock
        for ow_pat in OVERALL_WINNER_PATTERNS:
            m = re.search(ow_pat, full_text_lower)
            if m:
                errors.append(
                    f"Multichannel lock failed: Overall cross-platform winner claim is strictly forbidden ('{m.group(0)}')."
                )
                break

        # Gate B: Comparability Lock on Non-Comparable Metrics (SAVES, VIDEO_VIEWS)
        for sent in all_sentences:
            s_low = sent.lower()
            for non_comp_name in ["saves", "guardados", "video views", "reproducciones de video", "video_views"]:
                if non_comp_name in s_low:
                    comp_claim_patterns = [
                        r"\b(superó|supero|outperformed|ganó|gano|won|mayor rendimiento|mejor desempeño|mejores|mejor|better|fewer|less|más|mas|menos|aumentó frente a)\b"
                    ]
                    for c_pat in comp_claim_patterns:
                        if re.search(c_pat, s_low):
                            errors.append(
                                f"Comparability lock failed: Non-comparable metric '{non_comp_name}' cannot be ranked competitively across platforms."
                            )
                            break

        # Gate C: Zero-Baseline Lock (Forbid fabricated percentage when baseline is zero)
        for sent in all_sentences:
            s_low = sent.lower()
            if any(term in s_low for term in ["reaccion", "reacciones", "reaction", "reactions"]):
                has_pct = (
                    re.search(r"[-+]?\d+\s*%", s_low)
                    or re.search(r"\b\d+\s*(?:percent|por ciento)\b", s_low)
                    or re.search(r"\b(?:six\s+hundred|seiscientos)\s+(?:percent|por ciento)\b", s_low)
                    or re.search(r"\b\d+%", s_low)
                    or re.search(r"\bpor ciento\b", s_low)
                    or re.search(r"\bpercent\b", s_low)
                )
                if has_pct:
                    # Check if zero baseline is present in context for reactions
                    mc_intel = context.get("multichannel_intelligence", {})
                    comparisons = mc_intel.get("platform_comparisons", [])
                    has_zero_baseline = any(c.get("metric") == "REACTIONS" and c.get("delta_relative") is None for c in comparisons)
                    if has_zero_baseline:
                        errors.append(
                            "Zero-baseline lock failed: Cannot claim percentage variation for reactions when baseline platform is zero."
                        )
                        break

        # Gate D: Cross-Metric Synthetic Aggregation Lock (Section S)
        for agg_pat in SYNTHETIC_AGGREGATION_PATTERNS:
            m = re.search(agg_pat, full_text_lower)
            if m:
                errors.append(
                    f"Multichannel lock failed: Cross-metric synthetic aggregation or scoring is forbidden ('{m.group(0)}')."
                )
                break

        # Gate E: Audience Non-Performance Lock (Section W & AT, BS-5E.1C Negation-Aware)
        audience_disclaimer_patterns = [
            r"no\s+(?:necesariamente\s+)?(?:implica|representa|significa|conlleva|supone|equivale\s+a|es)?\s*(?:superioridad|mejor\s+(?:rendimiento|desempe[nñ]o)|ventaja)",
            r"no\s+(?:se\s+utiliza|se\s+interpreta|debe\s+interpretarse)\s+para\s+(?:evaluar\s+)?(?:desempe[nñ]o|rendimiento|superioridad)",
            r"no\s+debe\s+interpretarse\s+como\s+(?:mejor\s+(?:rendimiento|desempe[nñ]o)|superioridad)",
            r"sin\s+(?:implicar|representar|significar)\s+superioridad",
            r"does\s+not\s+(?:necessarily\s+)?(?:imply|represent|mean|indicate)\s+(?:superior|better\s+performance)",
            r"not\s+used\s+to\s+evaluate\s+(?:cross-platform\s+)?performance",
        ]
        audience_affirmative_perf_patterns = [
            r"\b(?:rinde\s+mejor|mejor\s+rendimiento|desempe[nñ]o\s+superior|superioridad|gana|gan[oó]|superior|eficiencia|calidad\s+superior|m[aá]s\s+fuerte|mas\s+fuerte|domina|dominante|mejor|m[aá]s\s+efectivo|mas\s+efectivo)\b",
            r"\b(?:performs\s+better|better\s+performance|outperformed|superior|wins|won|stronger|dominant|best)\b",
        ]

        for sent in all_sentences:
            s_low = sent.lower()
            if any(term in s_low for term in ["seguidores", "followers", "audience", "audiencia", "followers_total"]):
                cleaned_sent = s_low
                for disc_pat in audience_disclaimer_patterns:
                    if re.search(disc_pat, cleaned_sent):
                        cleaned_sent = re.sub(disc_pat, " ", cleaned_sent)

                for ap_pat in audience_affirmative_perf_patterns:
                    m = re.search(ap_pat, cleaned_sent)
                    if m:
                        errors.append(
                            f"Audience non-performance lock failed: Audience volume (followers) cannot be claimed as performance superiority ('{m.group(0)}')."
                        )
                        break

        # Gate F: Budget Reallocation Lock (Section Z & AV)
        budget_patterns = [
            r"\bmover\s+(?:el\s+)?presupuesto\b",
            r"\breasignar\s+(?:el\s+)?presupuesto\b",
            r"\bshift\s+budget\b",
            r"\breallocate\s+budget\b",
            r"\bmove\s+budget\b",
            r"\bpresupuesto\s+de\s+facebook\s+a\s+instagram\b",
        ]
        for b_pat in budget_patterns:
            m = re.search(b_pat, full_text_lower)
            if m:
                errors.append(
                    f"Budget reallocation lock failed: Budget reallocation across platforms is forbidden based on limited coverage ('{m.group(0)}')."
                )
                break

        # Gate G: Limitation Preservation Lock (Section AY, BS-5E.1C Numeric Semantic Recognition)
        mc_intel = context.get("multichannel_intelligence", {})
        cov_summary = mc_intel.get("coverage_summary") or mc_intel.get("coverage", {})
        expected_comp = cov_summary.get("comparable_metrics")
        expected_total = cov_summary.get("total_metrics", 15)
        cov_ratio_str = cov_summary.get("coverage_ratio", "")
        is_limited_coverage = cov_summary.get("status") == "LIMITED" or cov_ratio_str in ("3/15", "0/15")
        has_cross_platform_claim = False
        cross_platform_claim_terms = [
            r"\bfrente\s+a\b",
            r"\bcompared\s+to\b",
            r"\bsuper[oó]\b",
            r"\boutperformed\b",
            r"\breacciones\b.*(?:frente|comparad|vs)",
            r"\breactions\b.*(?:frente|compared|vs)",
            r"\b6(?:\.0)?\s+reacciones\b",
        ]
        for term in cross_platform_claim_terms:
            if re.search(term, full_text_lower):
                has_cross_platform_claim = True
                break
        if not has_cross_platform_claim:
            for r in recs:
                if "MC-SIG-7" in r.get("evidence_refs", []):
                    has_cross_platform_claim = True
                    break

        # Zero comparable metrics safety guard:
        if (expected_comp == 0 or cov_ratio_str == "0/15") and has_cross_platform_claim:
            errors.append(
                "Comparability lock failed: Cross-platform performance comparison claimed, but 0 comparable metrics exist between platforms for this period."
            )

        # Comparable ratio contradiction check:
        ratio_matches = re.findall(r"(\d+)\s*(?:/|de)\s*(?:las\s+|un\s+total\s+de\s+)?15(?:\s+m[eé]tricas)?", full_text_lower)
        for rm in ratio_matches:
            stated_comp = int(rm)
            if expected_comp is not None and stated_comp != expected_comp:
                errors.append(
                    f"Limitation preservation lock failed: Stated comparable count ({stated_comp}/15) contradicts context benchmark coverage ({expected_comp}/{expected_total})."
                )
                break

        if is_limited_coverage and has_cross_platform_claim and expected_comp != 0:
            # Check coverage disclosure across limitations, executive_summary, and structured disclosure
            coverage_search_texts = list(output.get("limitations", [])) + list(output.get("executive_summary", []))
            if "cross_platform_coverage_disclosure" in output and isinstance(output["cross_platform_coverage_disclosure"], dict):
                stmt = output["cross_platform_coverage_disclosure"].get("statement")
                if isinstance(stmt, str):
                    coverage_search_texts.append(stmt)
            coverage_text = " ".join(coverage_search_texts).lower()

            coverage_ratio_semantic_regex = re.compile(
                r"(?:"
                r"3\s*/\s*15"
                r"|(?:solo\s+)?(?:3|tres)\s+de\s+(?:las\s+|un\s+total\s+de\s+)?(?:15|quince)(?:\s+m[eé]tricas)?"
                r"|(?:only\s+)?(?:3|three)\s+of\s+(?:the\s+)?(?:15|fifteen)(?:\s+metrics)?"
                r")",
                re.IGNORECASE
            )

            has_explicit_ratio = bool(coverage_ratio_semantic_regex.search(coverage_text))
            has_coverage_keyword = any(kw in coverage_text for kw in ["limitad", "cobertura", "limited", "coverage"])
            preserves_limitation = has_explicit_ratio and has_coverage_keyword

            if not preserves_limitation:
                errors.append(
                    "Limitation preservation lock failed: Cross-platform performance claim made without preserving the limited data coverage limitation (3/15 comparable metrics)."
                )

        # Gate H: Language Contract Lock (Section AZ, AL)
        report_lang = context.get("report", {}).get("language") or "es"
        has_mc = bool(context.get("multichannel_intelligence"))
        if report_lang == "es" and has_mc:
            english_markers = [
                r"\bthe\b",
                r"\bduring the\b",
                r"\bwith\b",
                r"\bwere\b",
                r"\bthis\b",
                r"\bthese\b",
            ]
            for sent in all_sentences:
                s_low = sent.lower()
                if any(re.search(pat, s_low) for pat in english_markers):
                    errors.append(
                        "Language contract failed: Output contains English text while report language contract requires Spanish ('es')."
                    )
                    break

        # Gate I: Competitive-Language & Claim-Scope Lock (BS-5E.1C Sections F, G, H)
        broad_competitive_patterns = [
            r"\bventaja\s+competitiva\b",
            r"\blidera\s+en\s+interacciones\b",
            r"\blidera\s+en\s+engagement\b",
            r"\blidera\s+en\b",
            r"\bliderazgo\s+general\b",
            r"\bliderazgo\s+en\s+interacciones\b",
            r"\bdominancia\b",
            r"\bmejor\s+canal\b",
            r"\bplataforma\s+superior\b",
            r"\bm[eé]tricas\s+de\s+rendimiento\s+clave\b",
            r"\bm[eé]tricas\s+clave\b",
            r"\brendimiento\s+clave\s+superior\b",
            r"\bdesempe[nñ]o\s+general\b",
            r"\binteracciones\s+totales\b",
            r"\bcompetitive\s+advantage\b",
            r"\bleads\s+in\s+interactions\b",
            r"\bleads\s+in\s+engagement\b",
            r"\boverall\s+leadership\b",
            r"\bkey\s+performance\s+metrics\b",
        ]
        for bcp in broad_competitive_patterns:
            m = re.search(bcp, full_text_lower)
            if m:
                errors.append(
                    f"Claim-scope lock failed: Broad competitive terminology or ungrounded metric generalization is forbidden under limited coverage pilot ('{m.group(0)}')."
                )
                break

        if not any(
            "Multichannel lock failed" in e
            or "Comparability lock failed" in e
            or "Zero-baseline lock failed" in e
            or "Audience non-performance lock failed" in e
            or "Budget reallocation lock failed" in e
            or "Limitation preservation lock failed" in e
            or "Language contract failed" in e
            or "Claim-scope lock failed" in e
            for e in errors
        ):
            checks["multichannel_safety"] = True

        # 7. Recommendations Grounding & Evidence Refs
        for idx, rec in enumerate(recs):
            rec_refs = rec.get("evidence_refs", [])
            for ref in rec_refs:
                if ref not in evidence_registry:
                    errors.append(f"Recommendation evidence failed: Recommendation #{idx + 1} cites non-existent reference '{ref}'.")

        if not any("Recommendation evidence failed" in e for e in errors):
            checks["recommendations_grounded"] = True

        # Final verdict
        is_valid = len(errors) == 0
        status = "PASS" if is_valid else "FAIL"

        return is_valid, {
            "status": status,
            "results": checks,
            "errors": errors,
        }
