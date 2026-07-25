from uuid import UUID

from sqlalchemy.orm import Session

from app.documents.embeddings import EmbeddingProvider
from app.documents.retrieval import ChunkSearchStore, RetrievedChunk


class RetrievalValidationError(ValueError):
    """Raised when a semantic-search request is invalid."""


class RetrievalEmbeddingError(RuntimeError):
    """Raised when the embedding provider returns an invalid result."""


def search_document_chunks(
    db: Session,
    *,
    query: str,
    organization_id: str,
    provider: EmbeddingProvider,
    store: ChunkSearchStore,
    limit: int = 5,
    document_id: str | None = None,
    document_version_id: str | None = None,
) -> list[RetrievedChunk]:
    normalized_query = query.strip()

    if not normalized_query:
        raise RetrievalValidationError("Search query must not be empty.")

    if limit < 1:
        raise RetrievalValidationError("Search limit must be at least 1.")

    if limit > 100:
        raise RetrievalValidationError("Search limit must not exceed 100.")

    embeddings = provider.embed_texts([normalized_query])

    if len(embeddings) != 1:
        raise RetrievalEmbeddingError(
            "Embedding provider must return exactly one query embedding."
        )

    query_embedding = embeddings[0]

    if len(query_embedding) != provider.dimensions:
        raise RetrievalEmbeddingError(
            "Query embedding dimensions do not match the provider dimensions."
        )

    return store.search(
        db,
        query_embedding=query_embedding,
        organization_id=organization_id,
        limit=limit,
        document_id=document_id,
        document_version_id=document_version_id,
    )