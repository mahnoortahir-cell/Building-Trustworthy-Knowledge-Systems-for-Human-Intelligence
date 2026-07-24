import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.documents.models import (
    Document,
    DocumentStatus,
    DocumentVersion,
    ExtractionStatus,
)


class InvalidDocumentError(Exception):
    """Raised when an uploaded document is invalid."""


class DocumentStorageError(Exception):
    """Raised when a document cannot be stored."""

class DocumentCreationError(Exception):
    """Raised when document database records cannot be created."""    


def get_allowed_content_types() -> set[str]:
    return {
        content_type.strip()
        for content_type in settings.allowed_document_content_types.split(",")
        if content_type.strip()
    }


def validate_upload(file: UploadFile) -> None:
    allowed_content_types = get_allowed_content_types()

    if file.content_type not in allowed_content_types:
        raise InvalidDocumentError(
            "Only PDF documents are currently supported."
        )

    if not file.filename:
        raise InvalidDocumentError(
            "The uploaded file must have a filename."
        )

    if not file.filename.lower().endswith(".pdf"):
        raise InvalidDocumentError(
            "The uploaded file must use the .pdf extension."
        )


def calculate_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def build_storage_path(
    organization_id: str,
    original_filename: str,
) -> Path:
    safe_suffix = Path(original_filename).suffix.lower()
    generated_filename = f"{uuid4()}{safe_suffix}"

    return (
        Path(settings.upload_directory)
        / organization_id
        / generated_filename
    )


async def store_uploaded_file(
    file: UploadFile,
    organization_id: str,
) -> tuple[str, int, str]:
    validate_upload(file)

    file_bytes = await file.read()

    if not file_bytes:
        raise InvalidDocumentError(
            "The uploaded file is empty."
        )

    maximum_bytes = settings.max_upload_size_mb * 1024 * 1024

    if len(file_bytes) > maximum_bytes:
        raise InvalidDocumentError(
            f"The uploaded file exceeds the "
            f"{settings.max_upload_size_mb} MB limit."
        )

    # PDF files should begin with the PDF signature.
    if not file_bytes.startswith(b"%PDF-"):
        raise InvalidDocumentError(
            "The uploaded file does not appear to be a valid PDF."
        )

    checksum = calculate_sha256(file_bytes)

    storage_path = build_storage_path(
        organization_id=organization_id,
        original_filename=file.filename or "document.pdf",
    )

    try:
        storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        storage_path.write_bytes(file_bytes)

    except OSError as exc:
        raise DocumentStorageError(
            "The document could not be stored."
        ) from exc

    finally:
        await file.close()

    return (
        str(storage_path),
        len(file_bytes),
        checksum,
    )

def create_document_records(
    db: Session,
    organization_id: str,
    created_by_user_id: str,
    title: str,
    original_filename: str,
    content_type: str,
    storage_path: str,
    file_size: int,
    file_checksum: str,
) -> tuple[Document, DocumentVersion]:
    cleaned_title = title.strip()

    if not cleaned_title:
        cleaned_title = Path(original_filename).stem.strip()

    if not cleaned_title:
        raise InvalidDocumentError(
            "The document title cannot be empty."
        )

    document = Document(
        organization_id=organization_id,
        created_by_user_id=created_by_user_id,
        title=cleaned_title[:255],
        original_filename=original_filename[:255],
        content_type=content_type[:100],
        status=DocumentStatus.pending,
    )

    version = DocumentVersion(
        document=document,
        version_number=1,
        storage_path=storage_path,
        file_size=file_size,
        file_checksum=file_checksum,
        extraction_status=ExtractionStatus.pending,
    )

    try:
        db.add_all([document, version])
        db.commit()

        db.refresh(document)
        db.refresh(version)

    except IntegrityError as exc:
        db.rollback()

        raise DocumentCreationError(
            "The document records could not be created."
        ) from exc

    except Exception:
        db.rollback()
        raise

    return document, version

def delete_stored_file(storage_path: str) -> None:
    """Delete a stored file when database creation fails."""
    try:
        file_path = Path(storage_path)

        if file_path.exists():
            file_path.unlink()

    except OSError:
        # Cleanup failure should not hide the original application error.
        pass