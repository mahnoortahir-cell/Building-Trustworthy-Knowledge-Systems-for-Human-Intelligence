from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_conversation import (
    DocumentConversationMessage,
)


PASSWORD = "StrongPassword123!"


def register_user(client: TestClient) -> dict:
    unique_value = uuid4().hex

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Regenerate User",
            "email": f"regenerate-{unique_value}@example.com",
            "password": PASSWORD,
            "organization_name": f"Regenerate Org {unique_value}",
        },
    )

    assert response.status_code == 201

    return response.json()


def authorization_headers(
    access_token: str,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
    }


def conversations_url(
    organization_id: str,
) -> str:
    return (
        f"/organizations/{organization_id}"
        "/documents/conversations"
    )


def answer_url(
    organization_id: str,
) -> str:
    return (
        f"/organizations/{organization_id}"
        "/documents/answer"
    )


def regenerate_url(
    organization_id: str,
    conversation_id: str,
) -> str:
    return (
        f"/organizations/{organization_id}"
        f"/documents/conversations/{conversation_id}/regenerate"
    )


def create_conversation(
    client: TestClient,
    *,
    organization_id: str,
    access_token: str,
) -> dict:
    response = client.post(
        conversations_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "title": "Regenerate Conversation",
        },
    )

    assert response.status_code == 201

    return response.json()


def install_answer_dependencies(
    monkeypatch,
    *,
    answers: list[str],
) -> None:
    answer_iterator = iter(answers)

    monkeypatch.setattr(
        "app.documents.router.get_embedding_provider",
        lambda: SimpleNamespace(
            model_name="test-embedding-model",
            dimensions=3,
        ),
    )

    monkeypatch.setattr(
        "app.documents.router.get_llm_provider",
        lambda: SimpleNamespace(
            model_name="test-llm-model",
        ),
    )

    def fake_generate_document_answer(*args, **kwargs):
        del args, kwargs

        return SimpleNamespace(
            answer=next(answer_iterator),
            citations=[],
        )

    monkeypatch.setattr(
        (
            "app.documents.conversation_regenerate_service."
            "generate_document_answer"
        ),
        fake_generate_document_answer,
    )

    monkeypatch.setattr(
        "app.documents.router.generate_document_answer",
        fake_generate_document_answer,
    )


def saved_messages(
    db_session: Session,
    *,
    conversation_id: str,
) -> list[DocumentConversationMessage]:
    statement = (
        select(DocumentConversationMessage)
        .where(
            DocumentConversationMessage.conversation_id
            == conversation_id
        )
        .order_by(
            DocumentConversationMessage.sequence_number.asc()
        )
    )

    return list(db_session.scalars(statement).all())


def test_regenerate_endpoint_appends_assistant_message(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    install_answer_dependencies(
        monkeypatch,
        answers=[
            "Original answer.",
            "Fresh regenerated answer.",
        ],
    )

    registration = register_user(client)

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
    )

    answer_response = client.post(
        answer_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "question": "What is NoorOS?",
            "conversation_id": conversation["id"],
            "limit": 10,
        },
    )

    assert answer_response.status_code == 200

    regenerate_response = client.post(
        regenerate_url(
            organization_id,
            conversation["id"],
        ),
        headers=authorization_headers(access_token),
        json={},
    )

    assert regenerate_response.status_code == 200

    data = regenerate_response.json()

    assert data["answer"] == "Fresh regenerated answer."
    assert data["conversation_id"] == conversation["id"]
    assert data["assistant_message_id"]
    assert data["source_user_message_id"]
    assert data["citations"] == []

    messages = saved_messages(
        db_session,
        conversation_id=conversation["id"],
    )

    assert [message.role for message in messages] == [
        "user",
        "assistant",
        "assistant",
    ]

    assert [message.content for message in messages] == [
        "What is NoorOS?",
        "Original answer.",
        "Fresh regenerated answer.",
    ]


def test_regenerate_endpoint_rejects_empty_conversation(
    client: TestClient,
    monkeypatch,
) -> None:
    install_answer_dependencies(
        monkeypatch,
        answers=["Unused answer"],
    )

    registration = register_user(client)

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
    )

    response = client.post(
        regenerate_url(
            organization_id,
            conversation["id"],
        ),
        headers=authorization_headers(access_token),
        json={},
    )

    assert response.status_code == 422

    assert response.json() == {
        "detail": (
            "Conversation does not contain a user message "
            "to regenerate."
        )
    }


def test_regenerate_endpoint_returns_404_for_missing_conversation(
    client: TestClient,
    monkeypatch,
) -> None:
    install_answer_dependencies(
        monkeypatch,
        answers=["Unused answer"],
    )

    registration = register_user(client)

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    response = client.post(
        regenerate_url(
            organization_id,
            "missing-conversation",
        ),
        headers=authorization_headers(access_token),
        json={},
    )

    assert response.status_code == 404


def test_regenerate_endpoint_is_organization_scoped(
    client: TestClient,
    monkeypatch,
) -> None:
    install_answer_dependencies(
        monkeypatch,
        answers=["Unused answer"],
    )

    first_registration = register_user(client)
    second_registration = register_user(client)

    first_organization_id = (
        first_registration["organization"]["id"]
    )
    second_organization_id = (
        second_registration["organization"]["id"]
    )

    first_access_token = first_registration["access_token"]
    second_access_token = second_registration["access_token"]

    conversation = create_conversation(
        client,
        organization_id=first_organization_id,
        access_token=first_access_token,
    )

    response = client.post(
        regenerate_url(
            second_organization_id,
            conversation["id"],
        ),
        headers=authorization_headers(second_access_token),
        json={},
    )

    assert response.status_code == 404


def test_regenerate_endpoint_validates_limits(
    client: TestClient,
    monkeypatch,
) -> None:
    install_answer_dependencies(
        monkeypatch,
        answers=["Unused answer"],
    )

    registration = register_user(client)

    organization_id = registration["organization"]["id"]
    access_token = registration["access_token"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
    )

    response = client.post(
        regenerate_url(
            organization_id,
            conversation["id"],
        ),
        headers=authorization_headers(access_token),
        json={
            "context_limit": 21,
        },
    )

    assert response.status_code == 422


def test_regenerate_endpoint_requires_authentication(
    client: TestClient,
) -> None:
    registration = register_user(client)

    organization_id = registration["organization"]["id"]

    response = client.post(
        regenerate_url(
            organization_id,
            "conversation-id",
        ),
        json={},
    )

    assert response.status_code == 401
