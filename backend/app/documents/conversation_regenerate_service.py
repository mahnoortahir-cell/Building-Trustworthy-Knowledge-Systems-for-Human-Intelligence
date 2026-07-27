from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.documents.conversation_service import (
    ConversationPersistenceError,
    ConversationValidationError,
    add_conversation_message,
    get_document_conversation,
    list_conversation_messages,
)
from app.documents.conversation_types import (
    ConversationHistoryMessage,
)
from app.documents.rag_service import (
    generate_document_answer,
)
from app.models.document_conversation import (
    DocumentConversationMessage,
)


DEFAULT_REGENERATE_CONTEXT_LIMIT = 10
MAX_REGENERATE_CONTEXT_LIMIT = 20
DEFAULT_REGENERATE_HISTORY_LIMIT = 20
MAX_REGENERATE_HISTORY_LIMIT = 100


@dataclass(frozen=True)
class RegeneratedConversationAnswer:
    """
    Result returned after successfully regenerating an answer.
    """

    answer: str
    citations: list[Any]
    conversation_id: str
    assistant_message_id: str
    source_user_message_id: str


def validate_regenerate_options(
    *,
    context_limit: int,
    history_limit: int,
) -> None:
    if context_limit < 1:
        raise ConversationValidationError(
            "Regenerate context limit must be at least 1."
        )

    if context_limit > MAX_REGENERATE_CONTEXT_LIMIT:
        raise ConversationValidationError(
            "Regenerate context limit must not exceed "
            f"{MAX_REGENERATE_CONTEXT_LIMIT}."
        )

    if history_limit < 1:
        raise ConversationValidationError(
            "Regenerate history limit must be at least 1."
        )

    if history_limit > MAX_REGENERATE_HISTORY_LIMIT:
        raise ConversationValidationError(
            "Regenerate history limit must not exceed "
            f"{MAX_REGENERATE_HISTORY_LIMIT}."
        )


def _find_latest_user_message(
    messages: list[DocumentConversationMessage],
) -> tuple[int, DocumentConversationMessage]:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]

        if message.role == "user":
            return index, message

    raise ConversationValidationError(
        "Conversation does not contain a user message to regenerate."
    )


def _build_regeneration_history(
    messages: list[DocumentConversationMessage],
    *,
    latest_user_index: int,
    history_limit: int,
) -> list[ConversationHistoryMessage]:
    """
    Build history from messages before the latest user message.

    The previous assistant response after that user message is deliberately
    excluded so regeneration produces a fresh response instead of treating
    the old response as conversation context.
    """

    previous_messages = messages[:latest_user_index]

    if len(previous_messages) > history_limit:
        previous_messages = previous_messages[-history_limit:]

    history: list[ConversationHistoryMessage] = []

    for message in previous_messages:
        if message.role not in {"user", "assistant"}:
            continue

        history.append(
            ConversationHistoryMessage(
                role=message.role,
                content=message.content,
            )
        )

    return history


def regenerate_conversation_answer(
    db: Session,
    *,
    organization_id: str,
    conversation_id: str,
    embedding_provider: Any,
    search_store: Any,
    answer_generator: Any,
    context_limit: int = DEFAULT_REGENERATE_CONTEXT_LIMIT,
    history_limit: int = DEFAULT_REGENERATE_HISTORY_LIMIT,
    document_id: str | None = None,
    document_version_id: str | None = None,
) -> RegeneratedConversationAnswer:
    """
    Regenerate an answer for the latest user message in a conversation.

    Behaviour:
    - validates organisation ownership;
    - finds the most recent user message;
    - excludes the old assistant answer from RAG history;
    - generates a fresh grounded answer;
    - appends a new assistant message;
    - keeps the old assistant message unchanged.
    """

    validate_regenerate_options(
        context_limit=context_limit,
        history_limit=history_limit,
    )

    normalized_conversation_id = conversation_id.strip()

    if not normalized_conversation_id:
        raise ConversationValidationError(
            "conversation_id must not be empty."
        )

    conversation = get_document_conversation(
        db,
        organization_id=organization_id,
        conversation_id=normalized_conversation_id,
    )

    messages = list_conversation_messages(
        db,
        organization_id=organization_id,
        conversation_id=conversation.id,
    )

    latest_user_index, latest_user_message = (
        _find_latest_user_message(messages)
    )

    conversation_history = _build_regeneration_history(
        messages,
        latest_user_index=latest_user_index,
        history_limit=history_limit,
    )

    try:
        result = generate_document_answer(
            db,
            question=latest_user_message.content,
            organization_id=organization_id,
            embedding_provider=embedding_provider,
            search_store=search_store,
            answer_generator=answer_generator,
            limit=context_limit,
            document_id=document_id,
            document_version_id=document_version_id,
            conversation_history=conversation_history,
        )

        assistant_message = add_conversation_message(
            db,
            conversation=conversation,
            role="assistant",
            content=result.answer,
            commit=False,
        )

        db.commit()
        db.refresh(assistant_message)
        db.refresh(conversation)

    except ConversationValidationError:
        db.rollback()
        raise

    except SQLAlchemyError as exc:
        db.rollback()

        raise ConversationPersistenceError(
            "Could not save the regenerated assistant response."
        ) from exc

    except Exception:
        db.rollback()
        raise

    return RegeneratedConversationAnswer(
        answer=result.answer,
        citations=list(result.citations),
        conversation_id=conversation.id,
        assistant_message_id=assistant_message.id,
        source_user_message_id=latest_user_message.id,
    )
