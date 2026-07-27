import pytest

from app.documents.conversation_memory import (
    ConversationMemoryValidationError,
    build_conversation_context,
)
from app.documents.conversation_types import (
    ConversationHistoryMessage,
)


def message(
    role: str,
    content: str,
) -> ConversationHistoryMessage:
    return ConversationHistoryMessage(
        role=role,
        content=content,
    )


def test_empty_history_returns_empty_context() -> None:
    result = build_conversation_context([])

    assert result == []


def test_single_message_is_preserved() -> None:
    history = [
        message("user", "What is NoorOS?"),
    ]

    result = build_conversation_context(history)

    assert len(result) == 1
    assert result[0].role == "user"
    assert result[0].content == "What is NoorOS?"


def test_surrounding_whitespace_is_normalized() -> None:
    history = [
        message("user", "   What is NoorOS?   "),
        message("assistant", "   NoorOS is a platform.   "),
    ]

    result = build_conversation_context(history)

    assert [item.content for item in result] == [
        "What is NoorOS?",
        "NoorOS is a platform.",
    ]


def test_chronological_order_is_preserved() -> None:
    history = [
        message("user", "Question one"),
        message("assistant", "Answer one"),
        message("user", "Question two"),
        message("assistant", "Answer two"),
    ]

    result = build_conversation_context(history)

    assert [item.content for item in result] == [
        "Question one",
        "Answer one",
        "Question two",
        "Answer two",
    ]


def test_message_limit_keeps_newest_messages() -> None:
    history = [
        message("user", "Message one"),
        message("assistant", "Message two"),
        message("user", "Message three"),
        message("assistant", "Message four"),
    ]

    result = build_conversation_context(
        history,
        max_messages=2,
    )

    assert [item.content for item in result] == [
        "Message three",
        "Message four",
    ]


def test_character_budget_keeps_newest_complete_messages() -> None:
    history = [
        message("user", "11111"),
        message("assistant", "22222"),
        message("user", "33333"),
    ]

    result = build_conversation_context(
        history,
        max_characters=10,
    )

    assert [item.content for item in result] == [
        "22222",
        "33333",
    ]

    assert sum(len(item.content) for item in result) <= 10


def test_latest_oversized_message_is_truncated() -> None:
    history = [
        message("user", "abcdefghij"),
    ]

    result = build_conversation_context(
        history,
        max_characters=4,
    )

    assert len(result) == 1
    assert result[0].role == "user"
    assert result[0].content == "abcd"


def test_consecutive_duplicates_are_removed() -> None:
    history = [
        message("user", "Same question"),
        message("user", "Same question"),
        message("assistant", "Same answer"),
        message("assistant", "Same answer"),
    ]

    result = build_conversation_context(history)

    assert [(item.role, item.content) for item in result] == [
        ("user", "Same question"),
        ("assistant", "Same answer"),
    ]


def test_same_content_with_different_roles_is_not_removed() -> None:
    history = [
        message("user", "Shared content"),
        message("assistant", "Shared content"),
    ]

    result = build_conversation_context(history)

    assert len(result) == 2


def test_non_consecutive_duplicates_are_not_removed() -> None:
    history = [
        message("user", "Repeat"),
        message("assistant", "Response"),
        message("user", "Repeat"),
    ]

    result = build_conversation_context(history)

    assert len(result) == 3


def test_unsupported_role_is_rejected() -> None:
    history = [
        message("system", "Unsupported"),
    ]

    with pytest.raises(
        ConversationMemoryValidationError,
        match="unsupported role",
    ):
        build_conversation_context(history)


def test_empty_message_is_rejected() -> None:
    history = [
        message("user", "   "),
    ]

    with pytest.raises(
        ConversationMemoryValidationError,
        match="empty message",
    ):
        build_conversation_context(history)


@pytest.mark.parametrize(
    ("max_messages", "expected_message"),
    [
        (0, "at least 1"),
        (101, "must not exceed 100"),
    ],
)
def test_invalid_message_limit_is_rejected(
    max_messages: int,
    expected_message: str,
) -> None:
    with pytest.raises(
        ConversationMemoryValidationError,
        match=expected_message,
    ):
        build_conversation_context(
            [],
            max_messages=max_messages,
        )


@pytest.mark.parametrize(
    ("max_characters", "expected_message"),
    [
        (0, "at least 1"),
        (100_001, "must not exceed 100000"),
    ],
)
def test_invalid_character_budget_is_rejected(
    max_characters: int,
    expected_message: str,
) -> None:
    with pytest.raises(
        ConversationMemoryValidationError,
        match=expected_message,
    ):
        build_conversation_context(
            [],
            max_characters=max_characters,
        )


def test_original_history_is_not_mutated() -> None:
    history = [
        message("user", "   Original question   "),
        message("assistant", "Original answer"),
    ]

    original_first_content = history[0].content
    original_second_content = history[1].content

    result = build_conversation_context(history)

    assert history[0].content == original_first_content
    assert history[1].content == original_second_content

    assert result is not history
    assert result[0] is not history[0]
    assert result[1] is not history[1]


def test_message_limit_is_applied_before_character_budget() -> None:
    history = [
        message("user", "old-message"),
        message("assistant", "new-one"),
        message("user", "new-two"),
    ]

    result = build_conversation_context(
        history,
        max_messages=2,
        max_characters=14,
    )

    assert [item.content for item in result] == [
        "new-one",
        "new-two",
    ]
