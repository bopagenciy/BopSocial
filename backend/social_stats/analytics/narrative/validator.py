"""
Deterministic Validation Pipeline for Grounded AI Executive Narrative (BS-4H).
Validates schema, facts, metric availability, sample locks, confidence locks, causality, and evidence.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple

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
        allowed_root_keys = set(required_keys)
        extra_root_keys = set(output.keys()) - allowed_root_keys
        if extra_root_keys:
            errors.append(f"Unexpected extra root keys in output: {', '.join(sorted(extra_root_keys))}")
            return False, {"status": "FAIL", "results": checks, "errors": errors}

        if not all(isinstance(output[k], list) for k in required_keys):
            errors.append("All top-level sections must be lists.")
            return False, {"status": "FAIL", "results": checks, "errors": errors}

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

        # 5. Confidence Lock: Deterministic conservative evidence propagation
        evidence_registry = context.get("evidence_registry", {})
        for idx, rec in enumerate(recs):
            rec_conf = rec.get("confidence")
            rec_refs = rec.get("evidence_refs", [])
            if rec_conf not in CONFIDENCE_RANK:
                continue

            evidence_confidences = []
            for ref in rec_refs:
                ev = evidence_registry.get(ref)
                if not ev:
                    continue
                ev_type = ev.get("type")
                if ev_type == "DATA_LIMITATION":
                    evidence_confidences.append("HIGH")
                elif ev_type == "BUSINESS_SIGNAL":
                    sig_conf = ev.get("confidence") or ev.get("confidence_level") or "NONE"
                    evidence_confidences.append(sig_conf)
                else:
                    sig_conf = ev.get("confidence") or "NONE"
                    evidence_confidences.append(sig_conf)

            if evidence_confidences:
                # Conservative rule: recommendation confidence cannot exceed lowest material evidence confidence
                min_evidence_rank = min(CONFIDENCE_RANK.get(c, 0) for c in evidence_confidences)
                rec_rank = CONFIDENCE_RANK[rec_conf]
                if rec_rank > min_evidence_rank:
                    allowed_conf_str = [k for k, v in CONFIDENCE_RANK.items() if v == min_evidence_rank][0]
                    refs_str = ", ".join(rec_refs)
                    errors.append(
                        f"Confidence lock failed: Recommendation #{idx + 1} confidence '{rec_conf}' "
                        f"exceeds allowed '{allowed_conf_str}' from evidence refs [{refs_str}]."
                    )

        if not any("Confidence lock failed" in e for e in errors):
            checks["confidence_preserved"] = True

        # 6. Causality Guard
        causal_forbidden = [
            r"\bcaused\b",
            r"\bbecause\b",
            r"\byour audience prefers\b",
            r"\bthis proves\b",
            r"\bthis strategy drove\b",
            r"\bcausó\b",
            r"\bprovocó\b",
            r"\bdebido a que\b",
            r"\btu audiencia prefiere\b",
            r"\besto demuestra\b",
            r"\besta estrategia impulsó\b",
            r"\bporque la audiencia\b",
        ]
        for pattern in causal_forbidden:
            if re.search(pattern, full_text_lower):
                errors.append(f"Causality guard failed: Found unsupported causal phrase matching '{pattern}'.")
                break

        if not any("Causality guard failed" in e for e in errors):
            checks["causality_safe"] = True

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
