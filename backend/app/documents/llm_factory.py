import os

from app.documents.deterministic_llm import (
    DeterministicLLMProvider,
)
from app.documents.llm_provider import BaseLLMProvider
from app.documents.openai_llm import OpenAILLMProvider


class UnsupportedLLMProviderError(ValueError):
    """Raised when the configured LLM provider is unsupported."""


def get_llm_provider() -> BaseLLMProvider:
    provider_name = os.getenv(
        "LLM_PROVIDER",
        "deterministic",
    ).strip().lower()

    if provider_name == "deterministic":
        return DeterministicLLMProvider()

    if provider_name == "openai":
        return OpenAILLMProvider()

    raise UnsupportedLLMProviderError(
        f"Unsupported LLM provider: {provider_name}"
    )