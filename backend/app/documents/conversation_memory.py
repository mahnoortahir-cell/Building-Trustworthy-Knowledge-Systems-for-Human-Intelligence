from collections.abc import Sequence

from app.documents.conversation_types import (
    ConversationHistoryMessage,
)


DEFAULT_MAX_MESSAGES = 20
DEFAULT_MAX_CHARACTERS = 12_000


class ConversationMemoryValidationError(ValueError):
    """Raised when conversation-memory input is invalid."""


def _validate_limits(
    *,
    max_messages: int,
    max_characters: int,
) -> None:
    if max_messages < 1:
        raise ConversationMemoryValidationError(
            "Conversation memory max_messages must be at least 1."
        )

    if max_messages > 100:
        raise ConversationMemoryValidationError(
            "Conversation memory max_messages must not exceed 100."
        )

    if max_characters < 1:
        raise ConversationMemoryValidationError(
            "Conversation memory max_characters must be at least 1."
        )

    if max_characters > 100_000:
        raise ConversationMemoryValidationError(
            "Conversation memory max_characters must not exceed 100000."
        )


def _normalize_history(
    history: Sequence[ConversationHistoryMessage],
) -> list[ConversationHistoryMessage]:
    """
    Validate and normalize conversation history.

    A new list and new message objects are returned so the caller's input is
    never mutated.
    """

    normalized_history: list[ConversationHistoryMessage] = []

    for message in history:
        if message.role not in {"user", "assistant"}:
            raise ConversationMemoryValidationError(
                "Conversation history contains an unsupported role."
            )

        if not isinstance(message.content, str):
            raise ConversationMemoryValidationError(
                "Conversation history contains non-text content."
            )

        normalized_content = message.content.strip()

        if not normalized_content:
            raise ConversationMemoryValidationError(
                "Conversation history contains an empty message."
            )

        normalized_message = ConversationHistoryMessage(
            role=message.role,
            content=normalized_content,
        )

        if normalized_history:
            previous_message = normalized_history[-1]

            if (
                previous_message.role == normalized_message.role
                and previous_message.content == normalized_message.content
            ):
                continue

        normalized_history.append(normalized_message)

    return normalized_history


def _apply_message_limit(
    history: Sequence[ConversationHistoryMessage],
    *,
    max_messages: int,
) -> list[ConversationHistoryMessage]:
    if len(history) <= max_messages:
        return list(history)

    return list(history[-max_messages:])


def _apply_character_budget(
    history: Sequence[ConversationHistoryMessage],
    *,
    max_characters: int,
) -> list[ConversationHistoryMessage]:
    """
    Keep the newest messages that fit inside the character budget.

    Messages are selected newest-first and returned in chronological order.
    When the newest message alone exceeds the budget, a bounded version of
    that newest message is retained instead of returning an empty context.
    """

    selected_reversed: list[ConversationHistoryMessage] = []
    used_characters = 0

    for message in reversed(history):
        message_length = len(message.content)
        remaining_characters = max_characters - used_characters

        if remaining_characters <= 0:
            break

        if message_length <= remaining_characters:
            selected_reversed.append(
                ConversationHistoryMessage(
                    role=message.role,
                    content=message.content,
                )
            )
            used_characters += message_length
            continue

        if not selected_reversed:
            selected_reversed.append(
                ConversationHistoryMessage(
                    role=message.role,
                    content=message.content[:remaining_characters],
                )
            )

        break

    selected_reversed.reverse()
    return selected_reversed


def build_conversation_context(
    history: Sequence[ConversationHistoryMessage],
    *,
    max_messages: int = DEFAULT_MAX_MESSAGES,
    max_characters: int = DEFAULT_MAX_CHARACTERS,
) -> list[ConversationHistoryMessage]:
    """
    Build bounded, deterministic conversation context for RAG generation.

    The builder:
    - validates message roles and content;
    - normalizes surrounding whitespace;
    - removes consecutive duplicate messages;
    - keeps the newest messages within the configured message limit;
    - enforces a total character budget;
    - preserves chronological ordering;
    - never mutates the original history.
    """

    _validate_limits(
        max_messages=max_messages,
        max_characters=max_characters,
    )

    normalized_history = _normalize_history(history)

    message_bounded_history = _apply_message_limit(
        normalized_history,
        max_messages=max_messages,
    )

    return _apply_character_budget(
        message_bounded_history,
        max_characters=max_characters,
    )
