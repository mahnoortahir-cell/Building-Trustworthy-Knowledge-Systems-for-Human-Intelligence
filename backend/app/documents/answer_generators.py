from collections.abc import Sequence

from app.documents.conversation_types import (
    ConversationHistoryMessage,
)
from app.documents.retrieval import RetrievedChunk


class DeterministicAnswerGenerator:
    """
    Deterministic document-answer generator used during automated tests.

    It produces answers directly from retrieved document chunks and does not
    call an external language model.

    Conversation history is accepted to satisfy the shared AnswerGenerator
    contract, but it is intentionally not used when creating deterministic
    output.
    """

    model_name = "deterministic-context-answer-v1"

    def __init__(
        self,
        *,
        max_chunks: int = 3,
        max_characters_per_chunk: int = 600,
    ) -> None:
        if max_chunks < 1:
            raise ValueError(
                "max_chunks must be at least 1."
            )

        if max_characters_per_chunk < 1:
            raise ValueError(
                "max_characters_per_chunk must be at least 1."
            )

        self.max_chunks = max_chunks
        self.max_characters_per_chunk = (
            max_characters_per_chunk
        )

    def generate_answer(
        self,
        *,
        question: str,
        context_chunks: Sequence[RetrievedChunk],
        conversation_history: Sequence[
            ConversationHistoryMessage
        ] = (),
    ) -> str:
        """
        Return predictable text assembled from the retrieved chunks.
        """

        del question
        del conversation_history

        selected_chunks = context_chunks[: self.max_chunks]

        if not selected_chunks:
            return ""

        passages = [
            self._normalize_content(chunk.content)
            for chunk in selected_chunks
            if chunk.content.strip()
        ]

        if not passages:
            return ""

        return (
            "Based on the selected documents:\n\n"
            + "\n\n".join(passages)
        )

    def _normalize_content(
        self,
        content: str,
    ) -> str:
        normalized = " ".join(content.split())

        if len(normalized) <= self.max_characters_per_chunk:
            return normalized

        shortened = normalized[
            : self.max_characters_per_chunk
        ].rstrip()

        return f"{shortened}..."
