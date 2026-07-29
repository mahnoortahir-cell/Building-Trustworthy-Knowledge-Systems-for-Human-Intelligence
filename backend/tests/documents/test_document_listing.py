from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.models import (
    Document,
    DocumentStatus,
    DocumentVersion,
    ExtractionStatus,
)
from app.models.membership import Membership


def register_user(
    client: TestClient,
    *,
    email: str,
    organization_name: str,
) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Document Library User",
            "email": email,
            "password": "StrongPassword123!",
            "organization_name": organization_name,
        },
    )

    assert response.status_code == 201

    return response.json()


def get_membership(
    db_session: Session,
    *,
    organization_id: str,
) -> Membership:
    membership = db_session.scalar(
        select(Membership).where(
            Membership.organization_id
            == organization_id
        )
    )

    assert membership is not None

    return membership


def add_document(
    db_session: Session,
    *,
    organization_id: str,
    created_by_user_id: str,
    title: str,
    created_at: datetime,
) -> Document:
    document = Document(
        organization_id=organization_id,
        created_by_user_id=created_by_user_id,
        title=title,
        original_filename=f"{title.lower()}.pdf",
        content_type="application/pdf",
        status=DocumentStatus.ready,
        created_at=created_at,
        updated_at=created_at,
    )

    version = DocumentVersion(
        document=document,
        version_number=1,
        storage_path=f"uploads/{document.id}.pdf",
        file_size=512,
        file_checksum="a" * 64,
        extraction_status=ExtractionStatus.completed,
        created_at=created_at,
    )

    db_session.add_all([document, version])
    db_session.commit()
    db_session.refresh(document)

    return document


def test_list_documents_returns_newest_first(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = register_user(
        client,
        email="list-documents@example.com",
        organization_name="Document List Organization",
    )

    token = registration["access_token"]
    organization_id = registration["organization"]["id"]

    membership = get_membership(
        db_session,
        organization_id=organization_id,
    )

    base_time = datetime.now(timezone.utc)

    add_document(
        db_session,
        organization_id=organization_id,
        created_by_user_id=membership.user_id,
        title="Old",
        created_at=base_time,
    )
    add_document(
        db_session,
        organization_id=organization_id,
        created_by_user_id=membership.user_id,
        title="Middle",
        created_at=base_time + timedelta(minutes=1),
    )
    add_document(
        db_session,
        organization_id=organization_id,
        created_by_user_id=membership.user_id,
        title="Newest",
        created_at=base_time + timedelta(minutes=2),
    )

    response = client.get(
        f"/organizations/{organization_id}/documents",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert data["limit"] == 20
    assert data["offset"] == 0
    assert [
        item["title"]
        for item in data["items"]
    ] == [
        "Newest",
        "Middle",
        "Old",
    ]

    newest = data["items"][0]

    assert newest["status"] == "ready"
    assert newest["latest_version"]["version_number"] == 1
    assert (
        newest["latest_version"]["extraction_status"]
        == "completed"
    )


def test_list_documents_supports_pagination(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = register_user(
        client,
        email="paginate-documents@example.com",
        organization_name="Pagination Organization",
    )

    token = registration["access_token"]
    organization_id = registration["organization"]["id"]

    membership = get_membership(
        db_session,
        organization_id=organization_id,
    )

    base_time = datetime.now(timezone.utc)

    for index in range(3):
        add_document(
            db_session,
            organization_id=organization_id,
            created_by_user_id=membership.user_id,
            title=f"Document {index}",
            created_at=base_time
            + timedelta(minutes=index),
        )

    response = client.get(
        (
            f"/organizations/{organization_id}/documents"
            "?limit=1&offset=1"
        ),
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert data["limit"] == 1
    assert data["offset"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Document 1"


def test_list_documents_is_organization_scoped(
    client: TestClient,
    db_session: Session,
) -> None:
    first = register_user(
        client,
        email="first-library@example.com",
        organization_name="First Library",
    )
    second = register_user(
        client,
        email="second-library@example.com",
        organization_name="Second Library",
    )

    first_organization_id = first["organization"]["id"]
    second_organization_id = second["organization"]["id"]

    first_membership = get_membership(
        db_session,
        organization_id=first_organization_id,
    )
    second_membership = get_membership(
        db_session,
        organization_id=second_organization_id,
    )

    now = datetime.now(timezone.utc)

    add_document(
        db_session,
        organization_id=first_organization_id,
        created_by_user_id=first_membership.user_id,
        title="First Private Document",
        created_at=now,
    )
    add_document(
        db_session,
        organization_id=second_organization_id,
        created_by_user_id=second_membership.user_id,
        title="Second Private Document",
        created_at=now,
    )

    response = client.get(
        (
            f"/organizations/"
            f"{first_organization_id}/documents"
        ),
        headers={
            "Authorization": (
                f"Bearer {first['access_token']}"
            ),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert [
        item["title"]
        for item in data["items"]
    ] == ["First Private Document"]
