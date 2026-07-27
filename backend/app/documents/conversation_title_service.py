from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.documents.conversation_title_generator import (
    ConversationTitleGenerationError,
    ConversationTitleGenerator,
    generate_fallback_conversation_title,
)
from app.documents.llm_provider import BaseLLMProvider
from app.models.document_conversation import DocumentConversation


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def conversation_needs_automatic_title(
    conversation: DocumentConversation,
) -> bool:
    """
    Return True only when the conversation has no meaningful title.

    User-created or manually renamed titles are never overwritten.
    """

    title = conversation.title

    if title is None:
        return True

    return not title.strip()


def _generate_title(
    *,
    provider: BaseLLMProvider,
    user_message: str,
    assistant_message: str,
) -> str:
    """
    Generate an AI title with a deterministic fallback.

    The deterministic development provider intentionally uses the fallback
    because its normal response contains the complete prompt rather than a
    genuine generated title.
    """

    if provider.model_name == "deterministic-llm":
        return generate_fallback_conversation_title(
            user_message,
        )

    try:
        result = ConversationTitleGenerator(
            provider=provider,
        ).generate(
            user_message=user_message,
            assistant_message=assistant_message,
        )

        return result.title

    except ConversationTitleGenerationError:
        return generate_fallback_conversation_title(
            user_message,
        )


def assign_automatic_conversation_title(
    db: Session,
    *,
    conversation: DocumentConversation,
    provider: BaseLLMProvider,
    user_message: str,
    assistant_message: str,
) -> str | None:
    """
    Assign a title to an untitled conversation without committing.

    The calling answer endpoint owns the transaction. This means the title,
    user message and assistant message are committed together.

    Returns the assigned title, or None when the conversation already had a
    title.
    """

    if not conversation_needs_automatic_title(
        conversation
    ):
        return None

    title = _generate_title(
        provider=provider,
        user_message=user_message,
        assistant_message=assistant_message,
    )

    conversation.title = title
    conversation.updated_at = _utc_now()

    db.add(conversation)
    db.flush()

    return title
