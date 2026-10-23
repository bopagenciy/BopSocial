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

        # 3. Metric Allowlist: Unavailable metrics check
        platforms = context.get("platforms", {})
        ig_data = platforms.get("instagram", {})
        ig_status = ig_data.get("status", "")
        if ig_status == "PARTIAL":
            unsupported_metrics = [m.lower() for m in ig_data.get("unsupported_metrics", ["reach", "shares", "saves", "video_views", "engagement_total"])]
            # Check if text claims Instagram reached X or had shares/saves
            for m in unsupported_metrics:
                # check patterns like "instagram reached", "instagram reach", "alcanzó en instagram", "shares de instagram"
                patterns = [
                    rf"instagram.*?{m}",
                    rf"{m}.*?instagram",
                    rf"instagram.*?alcanz",
                ] if m == "reach" else [rf"instagram.*?{m}", rf"{m}.*?instagram"]

                for p in patterns:
                    if re.search(p, full_text_lower):
                        errors.append(f"Metric allowlist failed: Claimed unavailable Instagram metric '{m}'.")
                        break

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

        # 5. Confidence Lock
        evidence_registry = context.get("evidence_registry", {})
        for idx, rec in enumerate(recs):
            rec_conf = rec.get("confidence")
            rec_refs = rec.get("evidence_refs", [])
            # Find referenced signals
            for ref in rec_refs:
                ev = evidence_registry.get(ref)
                if ev and ev.get("type") == "BUSINESS_SIGNAL":
                    sig_conf = ev.get("confidence", "NONE")
                    # Check upgrade
                    if sig_conf in ("NONE", "LOW") and rec_conf in ("MEDIUM", "HIGH"):
                        errors.append(f"Confidence lock failed: Recommendation #{idx + 1} upgraded confidence from {sig_conf} to {rec_conf}.")
                    elif sig_conf == "MEDIUM" and rec_conf == "HIGH":
                        errors.append(f"Confidence lock failed: Recommendation #{idx + 1} upgraded confidence from MEDIUM to HIGH.")

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
