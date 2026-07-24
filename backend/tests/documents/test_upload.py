from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings


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


def test_upload_pdf_successfully(
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

    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog >>\n"
        b"endobj\n"
        b"%%EOF"
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
    assert response_data["status"] == "pending"

    version = response_data["latest_version"]

    assert version["version_number"] == 1
    assert version["file_size"] == len(pdf_content)
    assert version["extraction_status"] == "pending"
    assert len(version["file_checksum"]) == 64

    stored_file = Path(version["storage_path"])

    assert stored_file.exists()
    assert stored_file.read_bytes() == pdf_content

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