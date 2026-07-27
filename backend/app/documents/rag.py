from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.documents.conversation_types import (
    ConversationHistoryMessage,
)
from app.documents.retrieval import RetrievedChunk


@dataclass(frozen=True, slots=True)
class AnswerCitation:
    """
    Structured evidence used to generate a document answer.
    """

    chunk_id: str
    document_id: str
    document_version_id: str
    chunk_index: int
    content: str
    score: float


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    """
    Final complete answer produced by the RAG service.
    """

    answer: str
    citations: list[AnswerCitation]


@dataclass(frozen=True, slots=True)
class StreamingGeneratedAnswer:
    """
    Streaming answer returned by the RAG service.

    answer_chunks is consumed lazily by the API layer. Citations are available
    before answer generation starts because retrieval completes first.
    """

    answer_chunks: Iterator[str]
    citations: list[AnswerCitation]


@runtime_checkable
class AnswerGenerator(Protocol):
    """
    Contract implemented by complete-response answer generators.
    """

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
        Generate a complete grounded answer.
        """
        ...


@runtime_checkable
class StreamingAnswerGenerator(Protocol):
    """
    Contract implemented by streaming answer generators.
    """

    def stream_answer(
        self,
        *,
        question: str,
        context_chunks: Sequence[RetrievedChunk],
        conversation_history: Sequence[
            ConversationHistoryMessage
        ] = (),
    ) -> Iterator[str]:
        """
        Yield grounded answer text chunks.
        """
        ...
