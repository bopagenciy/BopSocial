"""
BS-4H Grounded AI Executive Narrative Schemas & Constants.
"""
import copy
from typing import Dict, List, Any

CONTEXT_SCHEMA_VERSION = "bs4h-context-v1"
PROMPT_VERSION = "bs4h-prompt-v2"

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


# Canonical JSON Schema for Executive Narrative Output (Single Source of Truth)
EXECUTIVE_NARRATIVE_JSON_SCHEMA: Dict[str, Any] = {
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


def get_executive_narrative_json_schema() -> Dict[str, Any]:
    """
    Returns a deep copy of the canonical ExecutiveNarrative JSON Schema.
    Ensures callers cannot mutate the shared global definition.
    """
    return copy.deepcopy(EXECUTIVE_NARRATIVE_JSON_SCHEMA)

