"""
Deterministic Recommendation Confidence Derivation Module (BS-4H.1D).
Derives canonical recommendation confidence from resolved evidence references,
relieving the LLM of uncertainty estimation.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

CONFIDENCE_RANK: Dict[str, int] = {
    "NONE": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}

CONFIDENCE_BY_RANK: Dict[int, str] = {v: k for k, v in CONFIDENCE_RANK.items()}


def derive_recommendation_confidence(
    evidence_refs: List[str],
    evidence_registry: Dict[str, Any],
) -> str:
    """
    Deterministically computes recommendation confidence from cited evidence references.
    Policy: Minimum confidence across all materially cited evidence refs.
    Fail closed: If evidence_refs is empty or references an unknown ID, raises ValueError.
    """
    if not isinstance(evidence_refs, list) or len(evidence_refs) == 0:
        raise ValueError("Cannot derive confidence: evidence_refs must be a non-empty list.")

    confidences: List[str] = []

    for ref in evidence_refs:
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError(f"Invalid evidence reference: '{ref}'.")
        if ref not in evidence_registry:
            raise ValueError(f"Unknown evidence reference '{ref}' not found in evidence_registry.")

        ev = evidence_registry[ref]
        ev_type = ev.get("type")

        if ev_type == "DATA_LIMITATION":
            # Verified system limitations carry deterministic HIGH confidence
            c = ev.get("confidence", "HIGH")
        elif ev_type == "BUSINESS_SIGNAL":
            c = ev.get("confidence") or ev.get("confidence_level") or "NONE"
        else:
            c = ev.get("confidence") or "NONE"

        if c not in CONFIDENCE_RANK:
            c = "NONE"

        confidences.append(c)

    min_rank = min(CONFIDENCE_RANK[c] for c in confidences)
    return CONFIDENCE_BY_RANK[min_rank]


def enrich_narrative_with_derived_confidence(
    narrative: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Enriches an LLM draft narrative with deterministically derived recommendation confidence.
    Text Immutability Guarantee:
      - Does NOT modify executive_summary, performance_observations, limitations.
      - Does NOT modify recommendation text, recommendation_type, strength, evidence_refs.
      - ONLY attaches canonical 'confidence' to each recommendation.
    """
    if not isinstance(narrative, dict):
        return narrative

    enriched = copy.deepcopy(narrative)
    evidence_registry = context.get("evidence_registry", {})
    recs = enriched.get("recommendations", [])

    if isinstance(recs, list):
        for rec in recs:
            if not isinstance(rec, dict):
                continue
            refs = rec.get("evidence_refs", [])
            try:
                derived_conf = derive_recommendation_confidence(refs, evidence_registry)
                rec["confidence"] = derived_conf
            except ValueError:
                # If refs are invalid/unknown, leave as-is or omit;
                # NarrativeValidator will fail closed with specific error.
                pass

    return enriched
