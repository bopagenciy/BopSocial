"""
BS-4H Grounded AI Executive Narrative Schemas & Constants.
"""
import copy
from typing import Dict, List, Any

CONTEXT_SCHEMA_VERSION = "bs4h-context-v2"
PROMPT_VERSION = "bs5d-prompt-v1"

# Legacy aliases for backward compatibility
BS4H_CONTEXT_SCHEMA_VERSION = "bs4h-context-v1"
BS4H_PROMPT_VERSION = "bs4h-prompt-v4"

RECOMMENDATION_TAXONOMY = [
    "CONTINUE_COLLECTING_DATA",
    "INCREASE_FORMAT_ALLOCATION",
    "DECREASE_FORMAT_ALLOCATION",
    "TEST_POSTING_WINDOW",
    "MAINTAIN_CURRENT_STRATEGY",
    "INVESTIGATE_DECLINE",
    "REVIEW_PLATFORM_PERFORMANCE",
    "EXPAND_SAMPLE",
    "REVIEW_PROVIDER_PERMISSIONS",
]

# BS-5E Multichannel Claim Classification & Action Mappings
CLAIM_CATEGORIES = [
    "AUDIENCE_CONTEXT",
    "METRIC_COMPARISON",
    "DATA_LIMITATION",
    "SEMANTIC_LIMITATION",
    "RECOMMENDATION",
]

CLAIM_EVIDENCE_MAPPING = {
    "AUDIENCE_CONTEXT": ["MC-SIG-6"],
    "METRIC_COMPARISON": ["MC-SIG-7"],
    "DATA_LIMITATION": [
        "MC-SIG-8",
        "LIMITATION-CROSS-PLATFORM-PARTIAL",
        "LIMITATION-IG-PARTIAL",
    ],
    "SEMANTIC_LIMITATION": ["MC-SIG-9"],
    "RECOMMENDATION": [
        "MC-SIG-7",
        "MC-SIG-8",
        "SIG-1",
        "SIG-2",
        "SIG-3",
        "SIG-4",
        "SIG-5",
    ],
}

CROSS_PLATFORM_ACTION_MAPPING = {
    "MC-SIG-7": "REVIEW_PLATFORM_PERFORMANCE",
    "MC-SIG-8": "REVIEW_PROVIDER_PERMISSIONS",
    "MC-SIG-6": None,  # Informational only
    "MC-SIG-9": "CONTINUE_COLLECTING_DATA",  # Informational semantic limitation
}

RECOMMENDATION_STRENGTHS = [
    "OBSERVE",
    "CONSIDER",
    "RECOMMEND",
]

CONFIDENCE_LEVELS = [
    "NONE",
    "LOW",
    "MEDIUM",
    "HIGH",
]

SUPPORTED_LANGUAGES = [
    "es",
    "en",
]

SUPPORTED_STYLES = [
    "EXECUTIVE",
    "CONCISE",
    "ADVISORY",
]

FORBIDDEN_KEYS = {
    "access_token",
    "refresh_token",
    "token",
    "secret",
    "client_secret",
    "api_key",
    "password",
    "private_key",
    "aws_secret",
    "signature",
    "credentials",
    "credential",
    "auth_token",
    "authorization",
}

# Token and content boundary budgets (Section Z)
MAX_SIGNALS_IN_CONTEXT = 10
MAX_CONTENT_EXAMPLES = 5
MAX_LIMITATIONS_IN_CONTEXT = 10


# Canonical JSON Schema for Executive Narrative Output (Internal Domain & Persistence)
CANONICAL_EXECUTIVE_NARRATIVE_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "executive_summary": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 5,
            "description": "Executive summary paragraphs in Spanish summarizing period performance.",
        },
        "performance_observations": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 6,
            "description": "Factual observations grounded strictly in supplied data.",
        },
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Actionable recommendation text in Spanish.",
                    },
                    "recommendation_type": {
                        "type": "string",
                        "enum": RECOMMENDATION_TAXONOMY,
                        "description": "Controlled taxonomy recommendation type.",
                    },
                    "strength": {
                        "type": "string",
                        "enum": RECOMMENDATION_STRENGTHS,
                        "description": "Strength level: OBSERVE, CONSIDER, or RECOMMEND.",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": CONFIDENCE_LEVELS,
                        "description": "Confidence level: NONE, LOW, MEDIUM, or HIGH.",
                    },
                    "evidence_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "List of referenced evidence IDs (e.g. SIG-1, LIMITATION-IG-PARTIAL).",
                    },
                },
                "required": [
                    "text",
                    "recommendation_type",
                    "strength",
                    "confidence",
                    "evidence_refs",
                ],
                "additionalProperties": False,
            },
            "minItems": 0,
            "maxItems": 5,
            "description": "Actionable recommendations backed by evidence.",
        },
        "limitations": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 5,
            "description": "Explicit data limitations or permission constraints.",
        },
    },
    "required": [
        "executive_summary",
        "performance_observations",
        "recommendations",
        "limitations",
    ],
    "additionalProperties": False,
}

# Alias for backwards compatibility
EXECUTIVE_NARRATIVE_JSON_SCHEMA: Dict[str, Any] = CANONICAL_EXECUTIVE_NARRATIVE_JSON_SCHEMA


# Provider/LLM JSON Schema for Executive Narrative Output (BS-4H.1D)
# Relieves the model of confidence authoring; additionalProperties: False strictly rejects confidence.
LLM_EXECUTIVE_NARRATIVE_JSON_SCHEMA: Dict[str, Any] = copy.deepcopy(CANONICAL_EXECUTIVE_NARRATIVE_JSON_SCHEMA)
# Remove confidence from provider recommendation item schema
_llm_rec_props = LLM_EXECUTIVE_NARRATIVE_JSON_SCHEMA["properties"]["recommendations"]["items"]["properties"]
if "confidence" in _llm_rec_props:
    del _llm_rec_props["confidence"]

_llm_rec_req = LLM_EXECUTIVE_NARRATIVE_JSON_SCHEMA["properties"]["recommendations"]["items"]["required"]
if "confidence" in _llm_rec_req:
    _llm_rec_req.remove("confidence")


def get_executive_narrative_json_schema(for_provider: bool = False) -> Dict[str, Any]:
    """
    Returns a deep copy of the ExecutiveNarrative JSON Schema.
    If for_provider=True, returns LLM_EXECUTIVE_NARRATIVE_JSON_SCHEMA (without confidence).
    Otherwise returns CANONICAL_EXECUTIVE_NARRATIVE_JSON_SCHEMA (with confidence).
    """
    schema = LLM_EXECUTIVE_NARRATIVE_JSON_SCHEMA if for_provider else CANONICAL_EXECUTIVE_NARRATIVE_JSON_SCHEMA
    return copy.deepcopy(schema)


def get_provider_narrative_json_schema() -> Dict[str, Any]:
    """Returns a deep copy of LLM_EXECUTIVE_NARRATIVE_JSON_SCHEMA for provider dispatch."""
    return copy.deepcopy(LLM_EXECUTIVE_NARRATIVE_JSON_SCHEMA)


def get_canonical_narrative_json_schema() -> Dict[str, Any]:
    """Returns a deep copy of CANONICAL_EXECUTIVE_NARRATIVE_JSON_SCHEMA for domain validation."""
    return copy.deepcopy(CANONICAL_EXECUTIVE_NARRATIVE_JSON_SCHEMA)

