"""
Grounded AI Executive Narrative Package.
"""
from .service import (
    preview_narrative,
    generate_and_save_narrative,
    get_latest_narrative_for_report,
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
    EXECUTIVE_NARRATIVE_JSON_SCHEMA,
    get_executive_narrative_json_schema,
)

__all__ = [
    "preview_narrative",
    "generate_and_save_narrative",
    "get_latest_narrative_for_report",
    "build_grounded_narrative_context",
    "compute_context_hash",
    "NarrativeValidator",
    "CONTEXT_SCHEMA_VERSION",
    "PROMPT_VERSION",
    "RECOMMENDATION_TAXONOMY",
    "RECOMMENDATION_STRENGTHS",
    "CONFIDENCE_LEVELS",
    "EXECUTIVE_NARRATIVE_JSON_SCHEMA",
    "get_executive_narrative_json_schema",
]
