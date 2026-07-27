from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.documents.conversation_regenerate_service import (
    MAX_REGENERATE_CONTEXT_LIMIT,
    MAX_REGENERATE_HISTORY_LIMIT,
    regenerate_conversation_answer,
    validate_regenerate_options,
)
from app.documents.conversation_service import (
    ConversationNotFoundError,
    ConversationValidationError,
    add_conversation_message,
    create_document_conversation,
)
from app.models.document_conversation import (
    DocumentConversationMessage,
)


class FakeEmbeddingProvider:
    model_name = "fake-embedding-model"
    dimensions = 3


class FakeSearchStore:
    pass


class FakeAnswerGenerator:
    model_name = "fake-answer-generator"


def create_test_conversation(
    db_session,
    *,
    organization_id: str = "organization-1",
):
    return create_document_conversation(
        db_session,
        organization_id=organization_id,
        created_by_user_id="user-1",
        title="Regenerate Test",
    )


def saved_messages(
    db_session,
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


def install_fake_generation(
    monkeypatch,
    *,
    answer: str = "Fresh regenerated answer.",
    recorded_calls: list[dict] | None = None,
) -> None:
    def fake_generate_document_answer(*args, **kwargs):
        del args

        if recorded_calls is not None:
            recorded_calls.append(kwargs)

        return SimpleNamespace(
            answer=answer,
            citations=[
                {
                    "document_id": "document-1",
                }
            ],
        )

    monkeypatch.setattr(
        (
            "app.documents.conversation_regenerate_service."
            "generate_document_answer"
        ),
        fake_generate_document_answer,
    )


def test_regenerate_appends_new_assistant_message(
    db_session,
    monkeypatch,
) -> None:
    install_fake_generation(monkeypatch)

    conversation = create_test_conversation(db_session)

    add_conversation_message(
        db_session,
        conversation=conversation,
        role="user",
        content="What is NoorOS?",
    )

    original_assistant = add_conversation_message(
        db_session,
        conversation=conversation,
        role="assistant",
        content="Original assistant answer.",
    )

    result = regenerate_conversation_answer(
        db_session,
        organization_id="organization-1",
        conversation_id=conversation.id,
        embedding_provider=FakeEmbeddingProvider(),
        search_store=FakeSearchStore(),
        answer_generator=FakeAnswerGenerator(),
    )

    messages = saved_messages(
        db_session,
        conversation_id=conversation.id,
    )

    assert len(messages) == 3
    assert messages[0].role == "user"
    assert messages[1].id == original_assistant.id
    assert messages[1].content == "Original assistant answer."
    assert messages[2].role == "assistant"
    assert messages[2].content == "Fresh regenerated answer."

    assert result.answer == "Fresh regenerated answer."
    assert result.conversation_id == conversation.id
    assert result.assistant_message_id == messages[2].id
    assert result.source_user_message_id == messages[0].id


def test_regenerate_uses_latest_user_message(
    db_session,
    monkeypatch,
) -> None:
    recorded_calls: list[dict] = []

    install_fake_generation(
        monkeypatch,
        recorded_calls=recorded_calls,
    )

    conversation = create_test_conversation(db_session)

    add_conversation_message(
        db_session,
        conversation=conversation,
        role="user",
        content="First question",
    )

    add_conversation_message(
        db_session,
        conversation=conversation,
        role="assistant",
        content="First answer",
    )

    latest_user = add_conversation_message(
        db_session,
        conversation=conversation,
        role="user",
        content="Latest question",
    )

    add_conversation_message(
        db_session,
        conversation=conversation,
        role="assistant",
        content="Old answer to latest question",
    )

    result = regenerate_conversation_answer(
        db_session,
        organization_id="organization-1",
        conversation_id=conversation.id,
        embedding_provider=FakeEmbeddingProvider(),
        search_store=FakeSearchStore(),
        answer_generator=FakeAnswerGenerator(),
    )

    assert len(recorded_calls) == 1

    generation_call = recorded_calls[0]

    assert generation_call["question"] == "Latest question"
    assert result.source_user_message_id == latest_user.id


def test_regenerate_excludes_previous_answer_from_history(
    db_session,
    monkeypatch,
) -> None:
    recorded_calls: list[dict] = []

    install_fake_generation(
        monkeypatch,
        recorded_calls=recorded_calls,
    )

    conversation = create_test_conversation(db_session)

    add_conversation_message(
        db_session,
        conversation=conversation,
        role="user",
        content="First question",
    )

    add_conversation_message(
        db_session,
        conversation=conversation,
        role="assistant",
        content="First answer",
    )

    add_conversation_message(
        db_session,
        conversation=conversation,
        role="user",
        content="Latest question",
    )

    add_conversation_message(
        db_session,
        conversation=conversation,
        role="assistant",
        content="Answer that must be excluded",
    )

    regenerate_conversation_answer(
        db_session,
        organization_id="organization-1",
        conversation_id=conversation.id,
        embedding_provider=FakeEmbeddingProvider(),
        search_store=FakeSearchStore(),
        answer_generator=FakeAnswerGenerator(),
    )

    history = recorded_calls[0]["conversation_history"]

    assert [
        (message.role, message.content)
        for message in history
    ] == [
        ("user", "First question"),
        ("assistant", "First answer"),
    ]


def test_multiple_regenerations_keep_previous_answers(
    db_session,
    monkeypatch,
) -> None:
    answers = iter(
        [
            "First regenerated answer.",
            "Second regenerated answer.",
        ]
    )

    def fake_generate_document_answer(*args, **kwargs):
        del args, kwargs

        return SimpleNamespace(
            answer=next(answers),
            citations=[],
        )

    monkeypatch.setattr(
        (
            "app.documents.conversation_regenerate_service."
            "generate_document_answer"
        ),
        fake_generate_document_answer,
    )

    conversation = create_test_conversation(db_session)

    add_conversation_message(
        db_session,
        conversation=conversation,
        role="user",
        content="Regenerate this",
    )

    add_conversation_message(
        db_session,
        conversation=conversation,
        role="assistant",
        content="Original answer",
    )

    for _ in range(2):
        regenerate_conversation_answer(
            db_session,
            organization_id="organization-1",
            conversation_id=conversation.id,
            embedding_provider=FakeEmbeddingProvider(),
            search_store=FakeSearchStore(),
            answer_generator=FakeAnswerGenerator(),
        )

    messages = saved_messages(
        db_session,
        conversation_id=conversation.id,
    )

    assert [message.content for message in messages] == [
        "Regenerate this",
        "Original answer",
        "First regenerated answer.",
        "Second regenerated answer.",
    ]


def test_regenerate_rejects_conversation_without_user_message(
    db_session,
    monkeypatch,
) -> None:
    install_fake_generation(monkeypatch)

    conversation = create_test_conversation(db_session)

    with pytest.raises(
        ConversationValidationError,
        match="does not contain a user message",
    ):
        regenerate_conversation_answer(
            db_session,
            organization_id="organization-1",
            conversation_id=conversation.id,
            embedding_provider=FakeEmbeddingProvider(),
            search_store=FakeSearchStore(),
            answer_generator=FakeAnswerGenerator(),
        )


def test_regenerate_rejects_other_organization(
    db_session,
    monkeypatch,
) -> None:
    install_fake_generation(monkeypatch)

    conversation = create_test_conversation(
        db_session,
        organization_id="organization-1",
    )

    add_conversation_message(
        db_session,
        conversation=conversation,
        role="user",
        content="Private question",
    )

    with pytest.raises(ConversationNotFoundError):
        regenerate_conversation_answer(
            db_session,
            organization_id="organization-2",
            conversation_id=conversation.id,
            embedding_provider=FakeEmbeddingProvider(),
            search_store=FakeSearchStore(),
            answer_generator=FakeAnswerGenerator(),
        )


def test_regenerate_rejects_missing_conversation(
    db_session,
    monkeypatch,
) -> None:
    install_fake_generation(monkeypatch)

    with pytest.raises(ConversationNotFoundError):
        regenerate_conversation_answer(
            db_session,
            organization_id="organization-1",
            conversation_id="missing-conversation",
            embedding_provider=FakeEmbeddingProvider(),
            search_store=FakeSearchStore(),
            answer_generator=FakeAnswerGenerator(),
        )


@pytest.mark.parametrize(
    ("context_limit", "history_limit", "message"),
    [
        (
            0,
            20,
            "context limit must be at least 1",
        ),
        (
            MAX_REGENERATE_CONTEXT_LIMIT + 1,
            20,
            "context limit must not exceed",
        ),
        (
            10,
            0,
            "history limit must be at least 1",
        ),
        (
            10,
            MAX_REGENERATE_HISTORY_LIMIT + 1,
            "history limit must not exceed",
        ),
    ],
)
def test_regenerate_option_validation(
    context_limit: int,
    history_limit: int,
    message: str,
) -> None:
    with pytest.raises(
        ConversationValidationError,
        match=message,
    ):
        validate_regenerate_options(
            context_limit=context_limit,
            history_limit=history_limit,
        )


def test_regenerate_rejects_empty_conversation_id(
    db_session,
    monkeypatch,
) -> None:
    install_fake_generation(monkeypatch)

    with pytest.raises(
        ConversationValidationError,
        match="conversation_id must not be empty",
    ):
        regenerate_conversation_answer(
            db_session,
            organization_id="organization-1",
            conversation_id="   ",
            embedding_provider=FakeEmbeddingProvider(),
            search_store=FakeSearchStore(),
            answer_generator=FakeAnswerGenerator(),
        )
