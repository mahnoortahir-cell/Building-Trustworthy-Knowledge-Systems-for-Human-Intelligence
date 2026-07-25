from collections.abc import Sequence

# from app.documents.llm import LanguageModelProvider
from app.documents.prompt_builder import (
    build_document_answer_prompt,
)
from app.documents.retrieval import RetrievedChunk
from app.documents.llm_provider import BaseLLMProvider

class LLMAnswerGenerator:
    """
    Generates grounded document answers through a language-model provider.

    This adapter keeps the RAG service independent from any specific
    provider such as OpenAI, Ollama, or another hosted model.
    """

    def __init__(
        self,
        *,
        provider: BaseLLMProvider
    ) -> None:
        self.provider = provider
        self.model_name = provider.model_name

    def generate_answer(
        self,
        *,
        question: str,
        context_chunks: Sequence[RetrievedChunk],
    ) -> str:
        system_prompt, user_prompt = build_document_answer_prompt(
            question=question,
            context_chunks=context_chunks,
        )

        response = self.provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        return response.strip()