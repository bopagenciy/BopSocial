"""
Grounded AI Executive Narrative Package.
"""
from .service import (
    preview_narrative,
    generate_and_save_narrative,
    get_latest_narrative_for_report,
    execute_controlled_narrative_generation,
    ControlledLiveExecutionError,
)
from .context import (
    build_grounded_narrative_context,
    compute_context_hash,
)
from .validator import NarrativeValidator
from .schemas import (
    CONTEXT_SCHEMA_VERSION,
    PROMPT_VERSION,
    RECOMMENDATION_TAXONOMY,
    RECOMMENDATION_STRENGTHS,
    CONFIDENCE_LEVELS,
    CLAIM_CATEGORIES,
    SIGNAL_TYPE_TO_CLAIM_CATEGORY,
    MAX_PROVIDER_CALLS,
    GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
    GENERATION_POLICY_DEFAULT,
    EXECUTIVE_NARRATIVE_JSON_SCHEMA,
    CANONICAL_EXECUTIVE_NARRATIVE_JSON_SCHEMA,
    LLM_EXECUTIVE_NARRATIVE_JSON_SCHEMA,
    get_executive_narrative_json_schema,
    get_provider_narrative_json_schema,
    get_canonical_narrative_json_schema,
)
from .confidence import (
    derive_recommendation_confidence,
    enrich_narrative_with_derived_confidence,
    CONFIDENCE_RANK,
)

__all__ = [
    "preview_narrative",
    "generate_and_save_narrative",
    "get_latest_narrative_for_report",
    "execute_controlled_narrative_generation",
    "ControlledLiveExecutionError",
    "build_grounded_narrative_context",
    "compute_context_hash",
    "NarrativeValidator",
    "CONTEXT_SCHEMA_VERSION",
    "PROMPT_VERSION",
    "RECOMMENDATION_TAXONOMY",
    "RECOMMENDATION_STRENGTHS",
    "CONFIDENCE_LEVELS",
    "CLAIM_CATEGORIES",
    "SIGNAL_TYPE_TO_CLAIM_CATEGORY",
    "MAX_PROVIDER_CALLS",
    "GENERATION_POLICY_SINGLE_ATTEMPT_STRICT",
    "GENERATION_POLICY_DEFAULT",
    "EXECUTIVE_NARRATIVE_JSON_SCHEMA",
    "CANONICAL_EXECUTIVE_NARRATIVE_JSON_SCHEMA",
    "LLM_EXECUTIVE_NARRATIVE_JSON_SCHEMA",
    "get_executive_narrative_json_schema",
    "get_provider_narrative_json_schema",
    "get_canonical_narrative_json_schema",
    "derive_recommendation_confidence",
    "enrich_narrative_with_derived_confidence",
    "CONFIDENCE_RANK",
]
