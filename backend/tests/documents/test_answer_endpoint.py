from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.conversation_types import (
    ConversationHistoryMessage,
)
from app.documents.rag_service import RagGenerationError
from app.models.document_conversation import (
    DocumentConversationMessage,
)


def register_user(
    client: TestClient,
    *,
    email: str = "answer-user@example.com",
    organization_name: str = "Answer Organization",
) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Answer Test User",
            "email": email,
            "password": "StrongPassword123!",
            "organization_name": organization_name,
        },
    )

    assert response.status_code == 201

    return response.json()


def authorization_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
    }


def answer_url(organization_id: str) -> str:
    return f"/organizations/{organization_id}/documents/answer"


def conversations_url(organization_id: str) -> str:
    return f"/organizations/{organization_id}/documents/conversations"


def create_conversation(
    client: TestClient,
    *,
    organization_id: str,
    access_token: str,
    title: str = "Test Conversation",
) -> dict:
    response = client.post(
        conversations_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "title": title,
        },
    )

    assert response.status_code == 201

    return response.json()


def install_answer_dependencies(
    monkeypatch,
    *,
    answer: str = "This is a grounded test answer.",
    recorded_calls: list[dict] | None = None,
) -> None:
    """
    Replace external embedding and LLM dependencies.

    The router evaluates provider arguments before calling the RAG service,
    so both provider factories are patched as well.
    """

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
        del args

        if recorded_calls is not None:
            recorded_calls.append(kwargs)

        return SimpleNamespace(
            answer=answer,
            citations=[],
        )

    monkeypatch.setattr(
        "app.documents.router.generate_document_answer",
        fake_generate_document_answer,
    )


def get_saved_messages(
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


def test_answer_without_conversation_returns_one_off_answer(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    install_answer_dependencies(monkeypatch)

    registration = register_user(client)

    access_token = registration["access_token"]
    organization_id = registration["organization"]["id"]

    response = client.post(
        answer_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "question": "What is NoorOS?",
            "limit": 5,
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["answer"] == (
        "This is a grounded test answer."
    )
    assert response_data["citations"] == []
    assert response_data["conversation_id"] is None

    messages = list(
        db_session.scalars(
            select(DocumentConversationMessage)
        ).all()
    )

    assert messages == []


def test_answer_with_conversation_persists_user_and_assistant_messages(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    install_answer_dependencies(
        monkeypatch,
        answer="NoorOS uses grounded retrieval.",
    )

    registration = register_user(client)

    access_token = registration["access_token"]
    organization_id = registration["organization"]["id"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
    )

    conversation_id = conversation["id"]

    response = client.post(
        answer_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "question": "How does NoorOS answer questions?",
            "conversation_id": conversation_id,
            "limit": 5,
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["conversation_id"] == conversation_id
    assert response_data["answer"] == (
        "NoorOS uses grounded retrieval."
    )
    assert response_data["citations"] == []

    db_session.expire_all()

    messages = get_saved_messages(
        db_session,
        conversation_id=conversation_id,
    )

    assert len(messages) == 2

    assert messages[0].role == "user"
    assert messages[0].content == (
        "How does NoorOS answer questions?"
    )

    assert messages[1].role == "assistant"
    assert messages[1].content == (
        "NoorOS uses grounded retrieval."
    )


def test_answer_passes_existing_history_to_rag(
    client: TestClient,
    monkeypatch,
) -> None:
    recorded_calls: list[dict] = []

    install_answer_dependencies(
        monkeypatch,
        answer="Recorded answer.",
        recorded_calls=recorded_calls,
    )

    registration = register_user(client)

    access_token = registration["access_token"]
    organization_id = registration["organization"]["id"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
    )

    conversation_id = conversation["id"]

    first_response = client.post(
        answer_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "question": "What methodology was used?",
            "conversation_id": conversation_id,
        },
    )

    assert first_response.status_code == 200

    second_response = client.post(
        answer_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "question": "Why was it selected?",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    assert len(recorded_calls) == 2

    first_history = recorded_calls[0]["conversation_history"]
    second_history = recorded_calls[1]["conversation_history"]

    assert first_history == []

    assert second_history == [
        ConversationHistoryMessage(
            role="user",
            content="What methodology was used?",
        ),
        ConversationHistoryMessage(
            role="assistant",
            content="Recorded answer.",
        ),
    ]


def test_multiple_answers_preserve_message_order(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    answers = iter(
        [
            "First assistant answer.",
            "Second assistant answer.",
        ]
    )

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
        del args
        del kwargs

        return SimpleNamespace(
            answer=next(answers),
            citations=[],
        )

    monkeypatch.setattr(
        "app.documents.router.generate_document_answer",
        fake_generate_document_answer,
    )

    registration = register_user(client)

    access_token = registration["access_token"]
    organization_id = registration["organization"]["id"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
    )

    conversation_id = conversation["id"]

    first_response = client.post(
        answer_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "question": "First user question.",
            "conversation_id": conversation_id,
        },
    )

    second_response = client.post(
        answer_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "question": "Second user question.",
            "conversation_id": conversation_id,
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    db_session.expire_all()

    messages = get_saved_messages(
        db_session,
        conversation_id=conversation_id,
    )

    assert [
        (message.role, message.content)
        for message in messages
    ] == [
        ("user", "First user question."),
        ("assistant", "First assistant answer."),
        ("user", "Second user question."),
        ("assistant", "Second assistant answer."),
    ]


def test_answer_rejects_empty_conversation_id(
    client: TestClient,
    monkeypatch,
) -> None:
    install_answer_dependencies(monkeypatch)

    registration = register_user(client)

    access_token = registration["access_token"]
    organization_id = registration["organization"]["id"]

    response = client.post(
        answer_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "question": "What is NoorOS?",
            "conversation_id": "   ",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "conversation_id must not be empty."
    }


def test_answer_with_unknown_conversation_returns_not_found(
    client: TestClient,
    monkeypatch,
) -> None:
    install_answer_dependencies(monkeypatch)

    registration = register_user(client)

    access_token = registration["access_token"]
    organization_id = registration["organization"]["id"]

    unknown_conversation_id = (
        "11111111-1111-1111-1111-111111111111"
    )

    response = client.post(
        answer_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "question": "What is NoorOS?",
            "conversation_id": unknown_conversation_id,
        },
    )

    assert response.status_code == 404


def test_answer_cannot_access_another_organizations_conversation(
    client: TestClient,
    monkeypatch,
) -> None:
    install_answer_dependencies(monkeypatch)

    first_registration = register_user(
        client,
        email="first-answer-user@example.com",
        organization_name="First Answer Organization",
    )

    first_token = first_registration["access_token"]
    first_organization_id = (
        first_registration["organization"]["id"]
    )

    first_conversation = create_conversation(
        client,
        organization_id=first_organization_id,
        access_token=first_token,
        title="Private First Organisation Conversation",
    )

    second_registration = register_user(
        client,
        email="second-answer-user@example.com",
        organization_name="Second Answer Organization",
    )

    second_token = second_registration["access_token"]
    second_organization_id = (
        second_registration["organization"]["id"]
    )

    response = client.post(
        answer_url(second_organization_id),
        headers=authorization_headers(second_token),
        json={
            "question": "Read the other organisation's conversation.",
            "conversation_id": first_conversation["id"],
        },
    )

    assert response.status_code == 404


def test_generation_failure_rolls_back_user_message(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
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

    def fail_generation(*args, **kwargs):
        del args
        del kwargs

        raise RagGenerationError(
            "The test answer generator failed."
        )

    monkeypatch.setattr(
        "app.documents.router.generate_document_answer",
        fail_generation,
    )

    registration = register_user(client)

    access_token = registration["access_token"]
    organization_id = registration["organization"]["id"]

    conversation = create_conversation(
        client,
        organization_id=organization_id,
        access_token=access_token,
    )

    conversation_id = conversation["id"]

    response = client.post(
        answer_url(organization_id),
        headers=authorization_headers(access_token),
        json={
            "question": "This message must be rolled back.",
            "conversation_id": conversation_id,
        },
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "The test answer generator failed."
    }

    db_session.expire_all()

    messages = get_saved_messages(
        db_session,
        conversation_id=conversation_id,
    )

    assert messages == []


def test_answer_requires_authentication(
    client: TestClient,
) -> None:
    response = client.post(
        answer_url("11111111-1111-1111-1111-111111111111"),
        json={
            "question": "What is NoorOS?",
        },
    )

    assert response.status_code == 401