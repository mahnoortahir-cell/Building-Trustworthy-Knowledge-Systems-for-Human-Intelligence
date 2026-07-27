from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.documents.conversation_types import (
    ConversationHistoryMessage,
    ConversationRole,
)
from app.models.document_conversation import (
    DocumentConversation,
    DocumentConversationMessage,
)


class ConversationNotFoundError(LookupError):
    """Raised when a conversation does not exist in the organisation."""


class ConversationValidationError(ValueError):
    """Raised when conversation input is invalid."""


class ConversationPersistenceError(RuntimeError):
    """Raised when conversation data cannot be stored."""


class ConversationConflictError(RuntimeError):
    """Raised when a conversation lifecycle action is not allowed."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_title(
    title: str | None,
) -> str | None:
    if title is None:
        return None

    normalized_title = " ".join(title.split())

    if not normalized_title:
        return None

    if len(normalized_title) > 255:
        raise ConversationValidationError(
            "Conversation title must not exceed 255 characters."
        )

    return normalized_title


def _normalize_message_content(
    content: str,
) -> str:
    normalized_content = content.strip()

    if not normalized_content:
        raise ConversationValidationError(
            "Conversation message must not be empty."
        )

    if len(normalized_content) > 100_000:
        raise ConversationValidationError(
            "Conversation message must not exceed 100000 characters."
        )

    return normalized_content


def _get_next_message_sequence(
    db: Session,
    *,
    conversation_id: str,
) -> int:
    """
    Lock the parent conversation and calculate the next message sequence.

    PostgreSQL honours the row lock, preventing concurrent requests from
    assigning the same sequence number to one conversation.
    """

    lock_statement = (
        select(DocumentConversation.id)
        .where(DocumentConversation.id == conversation_id)
        .with_for_update()
    )

    locked_conversation_id = db.scalar(lock_statement)

    if locked_conversation_id is None:
        raise ConversationNotFoundError(
            "Conversation was not found."
        )

    sequence_statement = select(
        func.coalesce(
            func.max(
                DocumentConversationMessage.sequence_number
            ),
            0,
        )
        + 1
    ).where(
        DocumentConversationMessage.conversation_id
        == conversation_id
    )

    next_sequence = db.scalar(sequence_statement)

    return int(next_sequence or 1)


def create_document_conversation(
    db: Session,
    *,
    organization_id: str,
    created_by_user_id: str,
    title: str | None = None,
    commit: bool = True,
) -> DocumentConversation:
    conversation = DocumentConversation(
        id=str(uuid4()),
        organization_id=organization_id,
        created_by_user_id=created_by_user_id,
        title=_normalize_title(title),
    )

    try:
        db.add(conversation)

        if commit:
            db.commit()
            db.refresh(conversation)
        else:
            db.flush()

    except SQLAlchemyError as exc:
        if commit:
            db.rollback()

        raise ConversationPersistenceError(
            "Unable to create the conversation."
        ) from exc

    return conversation


def get_document_conversation(
    db: Session,
    *,
    organization_id: str,
    conversation_id: str,
    include_messages: bool = False,
    include_deleted: bool = False,
) -> DocumentConversation:
    statement = select(DocumentConversation).where(
        DocumentConversation.id == conversation_id,
        DocumentConversation.organization_id == organization_id,
    )

    if include_messages:
        statement = statement.options(
            selectinload(DocumentConversation.messages)
        )

    if not include_deleted:
        statement = statement.where(
            DocumentConversation.is_deleted.is_(False)
        )

    conversation = db.scalar(statement)

    if conversation is None:
        raise ConversationNotFoundError(
            "Conversation was not found in this organization."
        )

    return conversation


def add_conversation_message(
    db: Session,
    *,
    conversation: DocumentConversation,
    role: ConversationRole,
    content: str,
    commit: bool = True,
) -> DocumentConversationMessage:
    if role not in {"user", "assistant"}:
        raise ConversationValidationError(
            "Message role must be either 'user' or 'assistant'."
        )

    normalized_content = _normalize_message_content(content)

    try:
        sequence_number = _get_next_message_sequence(
            db,
            conversation_id=conversation.id,
        )

        message = DocumentConversationMessage(
            id=str(uuid4()),
            conversation_id=conversation.id,
            sequence_number=sequence_number,
            role=role,
            content=normalized_content,
        )

        conversation.updated_at = _utc_now()

        db.add(message)
        db.add(conversation)

        if commit:
            db.commit()
            db.refresh(message)
            db.refresh(conversation)
        else:
            db.flush()

    except ConversationNotFoundError:
        if commit:
            db.rollback()

        raise

    except SQLAlchemyError as exc:
        if commit:
            db.rollback()

        raise ConversationPersistenceError(
            "Unable to save the conversation message."
        ) from exc

    return message


def list_conversation_messages(
    db: Session,
    *,
    conversation_id: str,
    organization_id: str | None = None,
    limit: int | None = None,
) -> list[DocumentConversationMessage]:
    """
    Return conversation messages ordered from oldest to newest.

    When organization_id is provided, the conversation is first validated
    against that organisation to prevent cross-organisation access.
    """

    if limit is not None and limit < 1:
        raise ConversationValidationError(
            "Message limit must be at least 1."
        )

    if limit is not None and limit > 500:
        raise ConversationValidationError(
            "Message limit must not exceed 500."
        )

    if organization_id is not None:
        conversation = get_document_conversation(
            db,
            organization_id=organization_id,
            conversation_id=conversation_id,
        )
        conversation_id = conversation.id

    if limit is None:
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

        return list(db.scalars(statement).all())

    statement = (
        select(DocumentConversationMessage)
        .where(
            DocumentConversationMessage.conversation_id
            == conversation_id
        )
        .order_by(
            DocumentConversationMessage.sequence_number.desc()
        )
        .limit(limit)
    )

    recent_messages = list(db.scalars(statement).all())
    recent_messages.reverse()

    return recent_messages


def get_conversation_history(
    db: Session,
    *,
    organization_id: str,
    conversation_id: str,
    limit: int = 20,
) -> list[ConversationHistoryMessage]:
    """
    Validate the conversation organisation and return recent messages.

    Messages are returned from oldest to newest.
    """

    messages = list_conversation_messages(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        limit=limit,
    )

    history: list[ConversationHistoryMessage] = []

    for message in messages:
        if message.role not in {"user", "assistant"}:
            continue

        history.append(
            ConversationHistoryMessage(
                role=message.role,
                content=message.content,
            )
        )

    return history


def list_document_conversations(
    db: Session,
    *,
    organization_id: str,
    limit: int = 50,
    offset: int = 0,
    archived: str = "false",
    deleted: str = "false",
) -> list[DocumentConversation]:
    """
    Return organisation-scoped conversations with archive filtering.

    archived=false returns active conversations.
    archived=true returns archived conversations.
    archived=all returns both active and archived conversations.
    """

    if limit < 1:
        raise ConversationValidationError(
            "Conversation limit must be at least 1."
        )

    if limit > 100:
        raise ConversationValidationError(
            "Conversation limit must not exceed 100."
        )

    if offset < 0:
        raise ConversationValidationError(
            "Conversation offset must not be negative."
        )

    archive_filter = archived.strip().lower()


    deleted_filter = deleted.strip().lower()

    if deleted_filter not in {"false", "true", "all"}:
        raise ConversationValidationError(
            "Deleted filter must be false, true, or all."
        )

    if archive_filter not in {"false", "true", "all"}:
        raise ConversationValidationError(
            "Archived filter must be false, true, or all."
        )

    statement = select(DocumentConversation).where(
        DocumentConversation.organization_id == organization_id
    )


    if deleted_filter == "false":
        statement = statement.where(
            DocumentConversation.is_deleted.is_(False)
        )
    elif deleted_filter == "true":
        statement = statement.where(
            DocumentConversation.is_deleted.is_(True)
        ).order_by(
            DocumentConversation.deleted_at.desc()
        )

    if archive_filter == "false":
        statement = statement.where(
            DocumentConversation.is_archived.is_(False)
        ).order_by(
            DocumentConversation.is_pinned.desc(),
            DocumentConversation.pinned_at.desc(),
            DocumentConversation.updated_at.desc(),
            DocumentConversation.created_at.desc(),
            DocumentConversation.id.desc(),
        )

    elif archive_filter == "true":
        statement = statement.where(
            DocumentConversation.is_archived.is_(True)
        ).order_by(
            DocumentConversation.archived_at.desc(),
            DocumentConversation.updated_at.desc(),
            DocumentConversation.created_at.desc(),
            DocumentConversation.id.desc(),
        )

    else:
        statement = statement.order_by(
            DocumentConversation.is_archived.asc(),
            DocumentConversation.is_pinned.desc(),
            DocumentConversation.pinned_at.desc(),
            DocumentConversation.archived_at.desc(),
            DocumentConversation.updated_at.desc(),
            DocumentConversation.created_at.desc(),
            DocumentConversation.id.desc(),
        )

    statement = statement.offset(offset).limit(limit)

    return list(db.scalars(statement).all())


def update_document_conversation(
    db: Session,
    *,
    organization_id: str,
    conversation_id: str,
    title: str | None,
) -> DocumentConversation:
    """
    Update the title of a conversation belonging to one organisation.

    The title is normalized using the same rules as conversation creation.
    Supplying null or a whitespace-only title clears the stored title.
    """

    conversation = get_document_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
    )

    normalized_title = _normalize_title(title)

    try:
        conversation.title = normalized_title
        conversation.updated_at = _utc_now()

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    except SQLAlchemyError as exc:
        db.rollback()

        raise ConversationPersistenceError(
            "Unable to update the conversation."
        ) from exc

    return conversation

def pin_document_conversation(
    db: Session,
    *,
    organization_id: str,
    conversation_id: str,
) -> DocumentConversation:
    """
    Pin a conversation belonging to one organisation.

    Repeated pin operations are idempotent. An already pinned
    conversation retains its original pinned timestamp.
    """

    conversation = get_document_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
    )

    if conversation.is_pinned:
        return conversation

    try:
        now = _utc_now()

        conversation.is_pinned = True
        conversation.pinned_at = now
        conversation.updated_at = now

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    except SQLAlchemyError as exc:
        db.rollback()

        raise ConversationPersistenceError(
            "Unable to pin the conversation."
        ) from exc

    return conversation


def unpin_document_conversation(
    db: Session,
    *,
    organization_id: str,
    conversation_id: str,
) -> DocumentConversation:
    """
    Unpin a conversation belonging to one organisation.

    Repeated unpin operations are idempotent.
    """

    conversation = get_document_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
    )

    if not conversation.is_pinned:
        return conversation

    try:
        now = _utc_now()

        conversation.is_pinned = False
        conversation.pinned_at = None
        conversation.updated_at = now

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    except SQLAlchemyError as exc:
        db.rollback()

        raise ConversationPersistenceError(
            "Unable to unpin the conversation."
        ) from exc

    return conversation


def archive_document_conversation(
    db: Session,
    *,
    organization_id: str,
    conversation_id: str,
) -> DocumentConversation:
    """
    Archive an organisation-scoped conversation.

    Repeated archive operations are idempotent and preserve the original
    archive timestamp.
    """

    conversation = get_document_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
    )

    if conversation.is_archived:
        return conversation

    try:
        now = _utc_now()

        conversation.is_archived = True
        conversation.archived_at = now
        conversation.updated_at = now

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    except SQLAlchemyError as exc:
        db.rollback()

        raise ConversationPersistenceError(
            "Unable to archive the conversation."
        ) from exc

    return conversation


def unarchive_document_conversation(
    db: Session,
    *,
    organization_id: str,
    conversation_id: str,
) -> DocumentConversation:
    """
    Restore an archived organisation-scoped conversation.

    Repeated unarchive operations are idempotent.
    """

    conversation = get_document_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
    )

    if not conversation.is_archived:
        return conversation

    try:
        now = _utc_now()

        conversation.is_archived = False
        conversation.archived_at = None
        conversation.updated_at = now

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    except SQLAlchemyError as exc:
        db.rollback()

        raise ConversationPersistenceError(
            "Unable to unarchive the conversation."
        ) from exc

    return conversation


def delete_document_conversation(
    db: Session,
    *,
    organization_id: str,
    conversation_id: str,
) -> None:
    """
    Soft-delete an organisation-scoped conversation.

    Repeated delete operations are idempotent and preserve the original
    deleted timestamp. Pin and archive metadata are intentionally preserved
    so restoring the conversation returns it to its previous lifecycle state.
    """

    conversation = get_document_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        include_deleted=True,
    )

    if conversation.is_deleted:
        return

    try:
        now = _utc_now()

        conversation.is_deleted = True
        conversation.deleted_at = now
        conversation.updated_at = now

        db.add(conversation)
        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()

        raise ConversationPersistenceError(
            "Unable to move the conversation to trash."
        ) from exc


def restore_document_conversation(
    db: Session,
    *,
    organization_id: str,
    conversation_id: str,
) -> DocumentConversation:
    """
    Restore an organisation-scoped conversation from trash.

    Repeated restore operations are idempotent.
    """

    conversation = get_document_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        include_deleted=True,
    )

    if not conversation.is_deleted:
        return conversation

    try:
        now = _utc_now()

        conversation.is_deleted = False
        conversation.deleted_at = None
        conversation.updated_at = now

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    except SQLAlchemyError as exc:
        db.rollback()

        raise ConversationPersistenceError(
            "Unable to restore the conversation."
        ) from exc

    return conversation


def permanently_delete_document_conversation(
    db: Session,
    *,
    organization_id: str,
    conversation_id: str,
) -> None:
    """
    Permanently remove a conversation that is already in trash.

    Conversation messages are deleted through the configured ORM and
    database cascade rules.
    """

    conversation = get_document_conversation(
        db,
        organization_id=organization_id,
        conversation_id=conversation_id,
        include_deleted=True,
    )

    if not conversation.is_deleted:
        raise ConversationConflictError(
            "Conversation must be moved to trash before permanent deletion."
        )

    try:
        db.delete(conversation)
        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()

        raise ConversationPersistenceError(
            "Unable to permanently delete the conversation."
        ) from exc
