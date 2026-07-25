from dataclasses import dataclass
from typing import Protocol, Sequence

from app.documents.retrieval import RetrievedChunk


@dataclass(frozen=True)
class AnswerCitation:
    chunk_id: str
    document_id: str
    document_version_id: str
    chunk_index: int
    content: str
    score: float


@dataclass(frozen=True)
class GeneratedAnswer:
    answer: str
    citations: list[AnswerCitation]


class AnswerGenerator(Protocol):
    model_name: str

    def generate_answer(
        self,
        *,
        question: str,
        context_chunks: Sequence[RetrievedChunk],
    ) -> str:
        """Generate an answer grounded only in the supplied chunks."""
        ...