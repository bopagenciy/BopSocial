"""
Provider registry for Grounded AI Executive Narrative.
"""
from typing import Optional
from .base import BaseNarrativeProvider, NarrativeProviderResult
from .fake import FakeNarrativeProvider
from .anthropic import AnthropicNarrativeProvider
from .openai import OpenAINarrativeProvider
from .gemini import GeminiNarrativeProvider
from .ollama import OllamaNarrativeProvider

_PROVIDERS = {
    "fake": FakeNarrativeProvider,
    "anthropic": AnthropicNarrativeProvider,
    "openai": OpenAINarrativeProvider,
    "gemini": GeminiNarrativeProvider,
    "ollama": OllamaNarrativeProvider,
}


def get_narrative_provider(name: str = "fake", model_name: Optional[str] = None, **kwargs) -> BaseNarrativeProvider:
    """
    Returns an instance of the requested narrative provider.
    Defaults safely to FakeNarrativeProvider.
    """
    provider_cls = _PROVIDERS.get(name.lower(), FakeNarrativeProvider)
    if model_name:
        return provider_cls(model_name=model_name, **kwargs)
    return provider_cls(**kwargs)
