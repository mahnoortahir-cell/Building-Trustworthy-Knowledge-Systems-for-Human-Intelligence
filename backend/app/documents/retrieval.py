from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.documents.models import (
    DocumentChunk,
    DocumentVersion,
    EmbeddingStatus,
)
from app.documents.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
    EmbeddingStatus,
)

@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_version_id: str
    chunk_index: int
    content: str
    score: float


class ChunkSearchStore(Protocol):
    def search(
        self,
        db: Session,
        *,
        query_embedding: Sequence[float],
        organization_id: str,
        limit: int,
        document_id: str | None = None,
        document_version_id: str | None = None,
    ) -> list[RetrievedChunk]:
        """Return chunks ordered from most relevant to least relevant."""
        ...

class DatabaseChunkSearchStore:
    def search(
        self,
        db: Session,
        *,
        query_embedding: Sequence[float],
        organization_id: str,
        limit: int,
        document_id: UUID | None = None,
        document_version_id: UUID | None = None,
    ) -> list[RetrievedChunk]:
        distance = DocumentChunk.embedding.cosine_distance(
            list(query_embedding)
        )

        statement = (
            select(
                DocumentChunk.id,
                DocumentVersion.document_id,
                DocumentChunk.document_version_id,
                DocumentChunk.chunk_index,
                DocumentChunk.text,
                distance.label("distance"),
            )
            .join(
                DocumentVersion,
                DocumentVersion.id == DocumentChunk.document_version_id,
            )
            .join(
                Document,
                Document.id == DocumentVersion.document_id,
            )
            .where(
                Document.organization_id == organization_id,
                DocumentChunk.embedding.is_not(None),
                DocumentChunk.embedding_status == EmbeddingStatus.completed,
            )
        )

        if document_id is not None:
            statement = statement.where(
                DocumentVersion.document_id == document_id
            )

        if document_version_id is not None:
            statement = statement.where(
                DocumentChunk.document_version_id == document_version_id
            )

        statement = statement.order_by(distance).limit(limit)

        rows = db.execute(statement).all()

        return [
            RetrievedChunk(
                chunk_id=row.id,
                document_id=row.document_id,
                document_version_id=row.document_version_id,
                chunk_index=row.chunk_index,
                content=row.text,
                score=1.0 - float(row.distance),
            )
            for row in rows
        ]