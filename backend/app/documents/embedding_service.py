from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.documents.embeddings import (
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.documents.models import (
    DocumentChunk,
    EmbeddingStatus,
)
# from collections.abc import Sequence
from app.documents.models import DocumentChunk

class EmbeddingStorageError(Exception):
    """Raised when generated embeddings cannot be stored."""


class EmbeddingStore(Protocol):
    """
    Storage contract for chunk embeddings.

    A PostgreSQL/pgvector implementation will be added later.
    Tests can use an in-memory implementation.
    """

    def save_embeddings(
        self,
        db: Session,
        *,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
        model_name: str,
    ) -> None:
        ...

class DatabaseEmbeddingStore:
    """Persist embeddings directly on DocumentChunk rows."""

    def save_embeddings(
        self,
        db: Session,
        *,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
        model_name: str,
    ) -> None:
        for chunk, embedding in zip(
            chunks,
            embeddings,
            strict=True,
        ):
            chunk.embedding = list(embedding)
            chunk.embedding_model = model_name

        db.flush()

def process_chunk_embeddings(
    db: Session,
    *,
    chunks: list[DocumentChunk],
    provider: EmbeddingProvider,
    store: EmbeddingStore,
) -> None:
    """
    Generate and store embeddings for document chunks.

    Chunks move through:

        pending → processing → completed

    If generation or storage fails:

        processing → failed
    """
    if not chunks:
        return

    for chunk in chunks:
        chunk.embedding_status = EmbeddingStatus.processing
        chunk.embedding_error = None

    db.commit()

    try:
        texts = [chunk.text for chunk in chunks]

        embeddings = provider.embed_texts(texts)

        _validate_embeddings(
            chunks=chunks,
            embeddings=embeddings,
            expected_dimensions=provider.dimensions,
        )

        store.save_embeddings(
            db,
            chunks=chunks,
            embeddings=embeddings,
            model_name=provider.model_name,
        )

        embedded_at = datetime.now(timezone.utc)

        for chunk in chunks:
            chunk.embedding_status = EmbeddingStatus.completed
            chunk.embedding_model = provider.model_name
            chunk.embedding_error = None
            chunk.embedded_at = embedded_at

        db.commit()

        for chunk in chunks:
            db.refresh(chunk)

    except Exception as exc:
        db.rollback()

        error_message = _safe_error_message(exc)

        for chunk in chunks:
            chunk.embedding_status = EmbeddingStatus.failed
            chunk.embedding_error = error_message
            chunk.embedding_model = None
            chunk.embedded_at = None

        db.commit()

        for chunk in chunks:
            db.refresh(chunk)

        raise


def _validate_embeddings(
    *,
    chunks: list[DocumentChunk],
    embeddings: list[list[float]],
    expected_dimensions: int,
) -> None:
    if len(embeddings) != len(chunks):
        raise EmbeddingProviderError(
            "Embedding provider returned an unexpected number of vectors."
        )

    for embedding in embeddings:
        if len(embedding) != expected_dimensions:
            raise EmbeddingProviderError(
                "Embedding provider returned a vector with invalid dimensions."
            )


def _safe_error_message(exc: Exception) -> str:
    if isinstance(
        exc,
        (
            EmbeddingProviderError,
            EmbeddingStorageError,
        ),
    ):
        return str(exc)

    return "An unexpected error occurred during embedding generation."