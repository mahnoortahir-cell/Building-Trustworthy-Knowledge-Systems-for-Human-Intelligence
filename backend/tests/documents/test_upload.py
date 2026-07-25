from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.service import process_document_extraction
from app.documents.models import Document, DocumentChunk, DocumentVersion


def register_user(client: TestClient) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Document User",
            "email": "documents@example.com",
            "password": "StrongPassword123!",
            "organization_name": "Document Organization",
        },
    )

    assert response.status_code == 201

    return response.json()

def create_text_pdf(
    file_path: Path,
    text: str,
) -> bytes:
    pdf = canvas.Canvas(str(file_path))
    pdf.drawString(72, 720, text)
    pdf.save()

    return file_path.read_bytes()

def test_upload_pdf_successfully(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
) -> None:
    test_upload_directory = tmp_path / "uploads"

    monkeypatch.setattr(
        settings,
        "upload_directory",
        str(test_upload_directory),
    )

    registration_data = register_user(client)

    access_token = registration_data["access_token"]
    organization_id = registration_data["organization"]["id"]

    pdf_content = create_text_pdf(
        file_path=tmp_path / "research-paper.pdf",
        text="NoorOS trustworthy knowledge system",
    )

    response = client.post(
        f"/organizations/{organization_id}/documents",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        data={
            "title": "My Test Document",
        },
        files={
            "file": (
                "research-paper.pdf",
                pdf_content,
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 201

    response_data = response.json()

    assert response_data["organization_id"] == organization_id
    assert response_data["title"] == "My Test Document"
    assert response_data["original_filename"] == "research-paper.pdf"
    assert response_data["content_type"] == "application/pdf"
    assert response_data["status"] == "ready"

    version = response_data["latest_version"]

    assert version["version_number"] == 1
    assert version["file_size"] == len(pdf_content)
    assert version["extraction_status"] == "completed"
    assert len(version["file_checksum"]) == 64

    stored_file = Path(version["storage_path"])

    assert stored_file.exists()
    assert stored_file.read_bytes() == pdf_content

    saved_version = db_session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.id == version["id"]
        )
    )

    assert saved_version is not None
    assert saved_version.extraction_status.value == "completed"
    assert saved_version.processing_error is None
    assert saved_version.extracted_text is not None
    assert "NoorOS trustworthy knowledge system" in saved_version.extracted_text   

    saved_chunks = db_session.scalars(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_version_id == saved_version.id
        )
        .order_by(DocumentChunk.chunk_index)
    ).all()

    assert len(saved_chunks) >= 1

    assert [chunk.chunk_index for chunk in saved_chunks] == list(
        range(len(saved_chunks))
    )

    assert all(chunk.text for chunk in saved_chunks)

    assert all(
        chunk.character_count == len(chunk.text)
        for chunk in saved_chunks
    )

    assert saved_chunks[0].text in saved_version.extracted_text     

def test_reprocessing_document_replaces_existing_chunks(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
) -> None:
    test_upload_directory = tmp_path / "uploads"

    monkeypatch.setattr(
        settings,
        "upload_directory",
        str(test_upload_directory),
    )

    registration_data = register_user(client)

    access_token = registration_data["access_token"]
    organization_id = registration_data["organization"]["id"]

    pdf_content = create_text_pdf(
        file_path=tmp_path / "reprocess.pdf",
        text="Original extracted document text",
    )

    response = client.post(
        f"/organizations/{organization_id}/documents",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        data={
            "title": "Reprocessing Test",
        },
        files={
            "file": (
                "reprocess.pdf",
                pdf_content,
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 201

    response_data = response.json()
    version_data = response_data["latest_version"]

    saved_version = db_session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.id == version_data["id"]
        )
    )

    assert saved_version is not None

    saved_document = db_session.scalar(
        select(Document).where(
            Document.id == saved_version.document_id
        )
    )

    assert saved_document is not None

    existing_chunks = db_session.scalars(
        select(DocumentChunk).where(
            DocumentChunk.document_version_id == saved_version.id
        )
    ).all()

    assert len(existing_chunks) >= 1

    old_chunk_ids = {
        chunk.id
        for chunk in existing_chunks
    }

    process_document_extraction(
        db=db_session,
        document=saved_document,
        version=saved_version,
    )

    refreshed_chunks = db_session.scalars(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_version_id == saved_version.id
        )
        .order_by(DocumentChunk.chunk_index)
    ).all()

    assert len(refreshed_chunks) >= 1

    assert [chunk.chunk_index for chunk in refreshed_chunks] == list(
        range(len(refreshed_chunks))
    )

    assert not old_chunk_ids.intersection(
        chunk.id
        for chunk in refreshed_chunks
    )

def test_upload_blank_pdf_marks_extraction_as_failed(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
) -> None:
    test_upload_directory = tmp_path / "uploads"

    monkeypatch.setattr(
        settings,
        "upload_directory",
        str(test_upload_directory),
    )

    registration_data = register_user(client)

    access_token = registration_data["access_token"]
    organization_id = registration_data["organization"]["id"]

    blank_pdf_path = tmp_path / "blank.pdf"

    pdf = canvas.Canvas(str(blank_pdf_path))
    pdf.showPage()
    pdf.save()

    blank_pdf_content = blank_pdf_path.read_bytes()

    response = client.post(
        f"/organizations/{organization_id}/documents",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        data={
            "title": "Blank Document",
        },
        files={
            "file": (
                "blank.pdf",
                blank_pdf_content,
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 201

    response_data = response.json()

    assert response_data["status"] == "failed"

    version = response_data["latest_version"]

    assert version["extraction_status"] == "failed"

    stored_file = Path(version["storage_path"])

    assert stored_file.exists()
    assert stored_file.read_bytes() == blank_pdf_content    

    saved_version = db_session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.id == version["id"]
        )
    )

    assert saved_version is not None
    assert saved_version.processing_error == (
        "No extractable text was found in the PDF."
    )
    assert saved_version.extracted_text is None

def test_reject_png_upload(
    client: TestClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    test_upload_directory = tmp_path / "uploads"

    monkeypatch.setattr(
        settings,
        "upload_directory",
        str(test_upload_directory),
    )

    registration_data = register_user(client)

    access_token = registration_data["access_token"]
    organization_id = registration_data["organization"]["id"]

    png_content = b"\x89PNG\r\n\x1a\nfake-image-content"

    response = client.post(
        f"/organizations/{organization_id}/documents",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        data={
            "title": "Car Simulation Image",
        },
        files={
            "file": (
                "car-simulation.png",
                png_content,
                "image/png",
            ),
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Only PDF documents are currently supported."
    }

    assert not test_upload_directory.exists()    

def test_reject_fake_pdf(
    client: TestClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    test_upload_directory = tmp_path / "uploads"

    monkeypatch.setattr(
        settings,
        "upload_directory",
        str(test_upload_directory),
    )

    registration_data = register_user(client)

    access_token = registration_data["access_token"]
    organization_id = registration_data["organization"]["id"]

    fake_pdf_content = b"This is not a real PDF file."

    response = client.post(
        f"/organizations/{organization_id}/documents",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        data={
            "title": "Fake PDF",
        },
        files={
            "file": (
                "fake-document.pdf",
                fake_pdf_content,
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "The uploaded file does not appear to be a valid PDF."
    }

    assert not test_upload_directory.exists()    

def test_reject_empty_pdf(
    client: TestClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    test_upload_directory = tmp_path / "uploads"

    monkeypatch.setattr(
        settings,
        "upload_directory",
        str(test_upload_directory),
    )

    registration_data = register_user(client)

    access_token = registration_data["access_token"]
    organization_id = registration_data["organization"]["id"]

    response = client.post(
        f"/organizations/{organization_id}/documents",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        data={
            "title": "Empty PDF",
        },
        files={
            "file": (
                "empty.pdf",
                b"",
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 400

    assert response.json() == {
        "detail": "The uploaded file is empty."
    }

    assert not test_upload_directory.exists()    

def test_upload_requires_authentication(
    client: TestClient,
) -> None:
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog >>\n"
        b"endobj\n"
        b"%%EOF"
    )

    response = client.post(
        "/organizations/test-organization/documents",
        data={
            "title": "Unauthorized Upload",
        },
        files={
            "file": (
                "document.pdf",
                pdf_content,
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 401    

def test_upload_to_unrelated_organization_returns_not_found(
    client: TestClient,
) -> None:
    registration_data = register_user(client)

    access_token = registration_data["access_token"]

    unrelated_organization_id = "11111111-1111-1111-1111-111111111111"

    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog >>\n"
        b"endobj\n"
        b"%%EOF"
    )

    response = client.post(
        f"/organizations/{unrelated_organization_id}/documents",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        data={
            "title": "Unauthorized Organization Upload",
        },
        files={
            "file": (
                "document.pdf",
                pdf_content,
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Organization not found."
    }    