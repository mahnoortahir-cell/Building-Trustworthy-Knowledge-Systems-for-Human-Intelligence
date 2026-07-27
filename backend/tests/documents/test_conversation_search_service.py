from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.documents.conversation_search_service import (
    MAX_SEARCH_LIMIT,
    normalize_conversation_search_query,
    search_document_conversations,
    validate_conversation_search_pagination,
)
from app.documents.conversation_service import (
    ConversationValidationError,
)


def test_normalize_search_query() -> None:
    result = normalize_conversation_search_query(
        "  Installing    NoorOS   "
    )

    assert result == "Installing NoorOS"


def test_search_query_rejects_empty_text() -> None:
    with pytest.raises(
        ConversationValidationError,
        match="must not be empty",
    ):
        normalize_conversation_search_query("   ")


def test_search_query_rejects_non_text_value() -> None:
    with pytest.raises(
        ConversationValidationError,
        match="must be text",
    ):
        normalize_conversation_search_query(
            123  # type: ignore[arg-type]
        )


def test_search_query_rejects_excessive_length() -> None:
    with pytest.raises(
        ConversationValidationError,
        match="must not exceed",
    ):
        normalize_conversation_search_query(
            "x" * 201
        )


@pytest.mark.parametrize(
    ("limit", "offset", "message"),
    [
        (
            0,
            0,
            "limit must be at least 1",
        ),
        (
            MAX_SEARCH_LIMIT + 1,
            0,
            "limit must not exceed",
        ),
        (
            20,
            -1,
            "offset must not be negative",
        ),
    ],
)
def test_invalid_pagination(
    limit: int,
    offset: int,
    message: str,
) -> None:
    with pytest.raises(
        ConversationValidationError,
        match=message,
    ):
        validate_conversation_search_pagination(
            limit=limit,
            offset=offset,
        )


def test_valid_pagination() -> None:
    validate_conversation_search_pagination(
        limit=20,
        offset=0,
    )


def test_search_returns_scalar_results() -> None:
    db = MagicMock()

    expected = [
        SimpleNamespace(
            id="conversation-1",
            organization_id="organization-1",
            title="Installing NoorOS",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    ]

    db.scalars.return_value.all.return_value = expected

    result = search_document_conversations(
        db,
        organization_id="organization-1",
        query="NoorOS",
    )

    assert result == expected
    db.scalars.assert_called_once_with(
        db.scalars.call_args.args[0]
    )


def test_search_supports_message_content_flag() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    result = search_document_conversations(
        db,
        organization_id="organization-1",
        query="Docker Compose",
        include_message_content=True,
        limit=10,
        offset=5,
    )

    assert result == []
    db.scalars.assert_called_once()


def test_search_validates_before_database_query() -> None:
    db = MagicMock()

    with pytest.raises(
        ConversationValidationError,
        match="must not be empty",
    ):
        search_document_conversations(
            db,
            organization_id="organization-1",
            query="   ",
        )

    db.scalars.assert_not_called()


def test_search_rejects_invalid_limit_before_query() -> None:
    db = MagicMock()

    with pytest.raises(
        ConversationValidationError,
        match="limit must not exceed",
    ):
        search_document_conversations(
            db,
            organization_id="organization-1",
            query="NoorOS",
            limit=101,
        )

    db.scalars.assert_not_called()
