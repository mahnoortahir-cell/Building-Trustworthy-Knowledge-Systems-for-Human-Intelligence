from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
    ExtractionStatus,
)


def test_document_chunk_can_be_created(db_session: Session) -> None:
    document = Document(
        organization_id="organization-id",
        created_by_user_id="user-id",
        title="Test Document",
        original_filename="test.pdf",
        content_type="application/pdf",
        status=DocumentStatus.ready,
    )

    version = DocumentVersion(
        document=document,
        version_number=1,
        storage_path="uploads/test.pdf",
        file_size=100,
        file_checksum="a" * 64,
        extraction_status=ExtractionStatus.completed,
        extracted_text="First chunk. Second chunk.",
    )

    chunk = DocumentChunk(
        document_version=version,
        chunk_index=0,
        text="First chunk.",
        character_count=len("First chunk."),
    )

    db_session.add(document)
    db_session.commit()

    stored_chunk = db_session.scalar(
        select(DocumentChunk).where(
            DocumentChunk.id == chunk.id
        )
    )

    assert stored_chunk is not None
    assert stored_chunk.document_version_id == version.id
    assert stored_chunk.chunk_index == 0
    assert stored_chunk.text == "First chunk."
    assert stored_chunk.character_count == len("First chunk.")


def test_document_version_orders_chunks_by_index(
    db_session: Session,
) -> None:
    document = Document(
        organization_id="organization-id",
        created_by_user_id="user-id",
        title="Ordered Chunks",
        original_filename="ordered.pdf",
        content_type="application/pdf",
        status=DocumentStatus.ready,
    )

    version = DocumentVersion(
        document=document,
        version_number=1,
        storage_path="uploads/ordered.pdf",
        file_size=200,
        file_checksum="b" * 64,
        extraction_status=ExtractionStatus.completed,
        extracted_text="Zero. One. Two.",
    )

    version.chunks.extend(
        [
            DocumentChunk(
                chunk_index=2,
                text="Two.",
                character_count=4,
            ),
            DocumentChunk(
                chunk_index=0,
                text="Zero.",
                character_count=5,
            ),
            DocumentChunk(
                chunk_index=1,
                text="One.",
                character_count=4,
            ),
        ]
    )

    db_session.add(document)
    db_session.commit()
    db_session.refresh(version)

    assert [chunk.chunk_index for chunk in version.chunks] == [0, 1, 2]


def test_deleting_document_version_deletes_chunks(
    db_session: Session,
) -> None:
    document = Document(
        organization_id="organization-id",
        created_by_user_id="user-id",
        title="Cascade Test",
        original_filename="cascade.pdf",
        content_type="application/pdf",
        status=DocumentStatus.ready,
    )

    version = DocumentVersion(
        document=document,
        version_number=1,
        storage_path="uploads/cascade.pdf",
        file_size=300,
        file_checksum="c" * 64,
        extraction_status=ExtractionStatus.completed,
        extracted_text="Delete this chunk.",
    )

    chunk = DocumentChunk(
        document_version=version,
        chunk_index=0,
        text="Delete this chunk.",
        character_count=len("Delete this chunk."),
    )

    db_session.add(document)
    db_session.commit()

    chunk_id = chunk.id

    db_session.delete(version)
    db_session.commit()

    deleted_chunk = db_session.get(DocumentChunk, chunk_id)

    assert deleted_chunk is None