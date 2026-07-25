from uuid import UUID
import pytest
from sqlalchemy.orm import Session

from app.documents.embedding_service import (
    EmbeddingStorageError,
    process_chunk_embeddings,
)
from app.documents.service import process_document_extraction
from app.documents.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProviderError,
)
from app.documents.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
    EmbeddingStatus,
    ExtractionStatus,
)


def create_document_version(
    db_session: Session,
) -> DocumentVersion:
    document = Document(
        organization_id="organization-id",
        created_by_user_id="user-id",
        title="Embedding Test Document",
        original_filename="embedding-test.pdf",
        content_type="application/pdf",
        status=DocumentStatus.ready,
    )

    version = DocumentVersion(
        document=document,
        version_number=1,
        storage_path="uploads/embedding-test.pdf",
        file_size=300,
        file_checksum="e" * 64,
        extraction_status=ExtractionStatus.completed,
        extracted_text="Embedding test document text.",
    )

    db_session.add(document)
    db_session.commit()
    db_session.refresh(version)

    return version


def create_chunks(
    db_session: Session,
    version: DocumentVersion,
) -> list[DocumentChunk]:
    first_text = "First knowledge chunk"
    second_text = "Second knowledge chunk"

    chunks = [
        DocumentChunk(
            document_version=version,
            chunk_index=0,
            text=first_text,
            character_count=len(first_text),
        ),
        DocumentChunk(
            document_version=version,
            chunk_index=1,
            text=second_text,
            character_count=len(second_text),
        ),
    ]

    db_session.add_all(chunks)
    db_session.commit()

    for chunk in chunks:
        db_session.refresh(chunk)

    return chunks


class InMemoryEmbeddingStore:
    def __init__(self) -> None:
        self.saved: dict[str, list[float]] = {}
        self.model_name: str | None = None

    def save_embeddings(
        self,
        db: Session,
        *,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
        model_name: str,
    ) -> None:
        self.model_name = model_name

        for chunk, embedding in zip(
            chunks,
            embeddings,
            strict=True,
        ):
            self.saved[chunk.id] = list(embedding)

class FailingEmbeddingStore:
    def save_embeddings(
        self,
        db: Session,
        *,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
        model_name: str,
    ) -> None:
        raise EmbeddingStorageError(
            "Embedding storage is unavailable."
        )


class InvalidCountProvider:
    @property
    def model_name(self) -> str:
        return "invalid-count-provider"

    @property
    def dimensions(self) -> int:
        return 4

    def embed_texts(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return []


def test_process_chunk_embeddings_successfully(
    db_session: Session,
) -> None:
    version = create_document_version(
        db_session
    )

    chunks = create_chunks(
        db_session,
        version,
    )

    provider = DeterministicEmbeddingProvider(
        dimensions=8,
    )

    store = InMemoryEmbeddingStore()

    process_chunk_embeddings(
        db_session,
        chunks=chunks,
        provider=provider,
        store=store,
    )

    assert len(store.saved) == 2
    assert store.model_name == provider.model_name

    for chunk in chunks:
        assert (
            chunk.embedding_status
            == EmbeddingStatus.completed
        )
        assert chunk.embedding_model == provider.model_name
        assert chunk.embedding_error is None
        assert chunk.embedded_at is not None
        assert chunk.id in store.saved
        assert len(store.saved[chunk.id]) == 8


def test_embedding_storage_failure_marks_chunks_failed(
    db_session: Session,
) -> None:
    version = create_document_version(
        db_session
    )

    chunks = create_chunks(
        db_session,
        version,
    )

    provider = DeterministicEmbeddingProvider()
    store = FailingEmbeddingStore()

    with pytest.raises(
        EmbeddingStorageError,
        match="storage is unavailable",
    ):
        process_chunk_embeddings(
            db_session,
            chunks=chunks,
            provider=provider,
            store=store,
        )

    for chunk in chunks:
        assert (
            chunk.embedding_status
            == EmbeddingStatus.failed
        )
        assert chunk.embedding_error == (
            "Embedding storage is unavailable."
        )
        assert chunk.embedding_model is None
        assert chunk.embedded_at is None        

def test_invalid_embedding_count_marks_chunks_failed(
    db_session: Session,
) -> None:
    version = create_document_version(
        db_session
    )

    chunks = create_chunks(
        db_session,
        version,
    )

    provider = InvalidCountProvider()
    store = InMemoryEmbeddingStore()

    with pytest.raises(
        EmbeddingProviderError,
        match="unexpected number",
    ):
        process_chunk_embeddings(
            db_session,
            chunks=chunks,
            provider=provider,
            store=store,
        )

    assert store.saved == {}

    for chunk in chunks:
        assert (
            chunk.embedding_status
            == EmbeddingStatus.failed
        )
        assert chunk.embedding_error == (
            "Embedding provider returned an unexpected number of vectors."
        )
        assert chunk.embedding_model is None
        assert chunk.embedded_at is None        

def test_process_chunk_embeddings_accepts_empty_list(
    db_session: Session,
) -> None:
    provider = DeterministicEmbeddingProvider()
    store = InMemoryEmbeddingStore()

    process_chunk_embeddings(
        db_session,
        chunks=[],
        provider=provider,
        store=store,
    )

    assert store.saved == {}
    assert store.model_name is None        

def test_extraction_requires_provider_and_store_together(
    db_session: Session,
) -> None:
    version = create_document_version(db_session)
    document = version.document

    provider = DeterministicEmbeddingProvider()

    with pytest.raises(
        ValueError,
        match="must be supplied together",
    ):
        process_document_extraction(
            db_session,
            document,
            version,
            embedding_provider=provider,
        )

    assert document.status == DocumentStatus.ready
    assert (
        version.extraction_status
        == ExtractionStatus.completed
    )    