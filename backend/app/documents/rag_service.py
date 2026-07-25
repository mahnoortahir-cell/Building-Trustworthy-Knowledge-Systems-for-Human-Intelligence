from sqlalchemy.orm import Session

from app.documents.embeddings import EmbeddingProvider
from app.documents.rag import (
    AnswerCitation,
    AnswerGenerator,
    GeneratedAnswer,
)
from app.documents.retrieval import ChunkSearchStore
from app.documents.retrieval_service import search_document_chunks

from collections.abc import Sequence

from app.documents.retrieval import RetrievedChunk

class RagValidationError(ValueError):
    """Raised when the RAG request is invalid."""


class RagGenerationError(RuntimeError):
    """Raised when answer generation fails or returns invalid output."""

def _deduplicate_chunks(
    chunks: Sequence[RetrievedChunk],
) -> list[RetrievedChunk]:
    unique_chunks: list[RetrievedChunk] = []
    seen_content: set[str] = set()

    for chunk in chunks:
        normalized_content = " ".join(
            chunk.content.lower().split()
        )

        if not normalized_content:
            continue

        if normalized_content in seen_content:
            continue

        seen_content.add(normalized_content)
        unique_chunks.append(chunk)

    return unique_chunks

def generate_document_answer(
    db: Session,
    *,
    question: str,
    organization_id: str,
    embedding_provider: EmbeddingProvider,
    search_store: ChunkSearchStore,
    answer_generator: AnswerGenerator,
    limit: int = 5,
    document_id: str | None = None,
    document_version_id: str | None = None,
) -> GeneratedAnswer:
    normalized_question = question.strip()

    if not normalized_question:
        raise RagValidationError("Question must not be empty")

    if limit < 1:
        raise RagValidationError("Context limit must be at least 1")

    if limit > 20:
        raise RagValidationError("Context limit must not exceed 20")

    chunks = search_document_chunks(
        db,
        query=normalized_question,
        organization_id=organization_id,
        provider=embedding_provider,
        store=search_store,
        limit=limit,
        document_id=document_id,
        document_version_id=document_version_id,
    )

    chunks = _deduplicate_chunks(chunks)

    if not chunks:
        return GeneratedAnswer(
            answer=(
                "I could not find enough relevant information "
                "in the selected documents."
            ),
            citations=[],
        )

    try:
        answer = answer_generator.generate_answer(
            question=normalized_question,
            context_chunks=chunks,
        ).strip()
    except Exception as exc:
        raise RagGenerationError(
            "Failed to generate a document answer"
        ) from exc

    if not answer:
        raise RagGenerationError(
            "Answer generator returned an empty answer"
        )

    citations = [
        AnswerCitation(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_version_id=chunk.document_version_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=chunk.score,
        )
        for chunk in chunks
    ]

    return GeneratedAnswer(
        answer=answer,
        citations=citations,
    )