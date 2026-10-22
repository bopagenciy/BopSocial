"""
BS-4H Grounded AI Executive Narrative Schemas & Constants.
"""
from typing import Dict, List, Any

CONTEXT_SCHEMA_VERSION = "bs4h-context-v1"
PROMPT_VERSION = "bs4h-prompt-v1"

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
