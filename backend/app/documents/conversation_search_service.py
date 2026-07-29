from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.documents.conversation_service import (
    ConversationValidationError,
)
from app.models.document_conversation import (
    DocumentConversation,
    DocumentConversationMessage,
)


DEFAULT_SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 100
MAX_SEARCH_QUERY_LENGTH = 200


def normalize_conversation_search_query(
    query: str,
) -> str:
    if not isinstance(query, str):
        raise ConversationValidationError(
            "Conversation search query must be text."
        )

    normalized_query = " ".join(query.split())

    if not normalized_query:
        raise ConversationValidationError(
            "Conversation search query must not be empty."
        )

    if len(normalized_query) > MAX_SEARCH_QUERY_LENGTH:
        raise ConversationValidationError(
            "Conversation search query must not exceed "
            f"{MAX_SEARCH_QUERY_LENGTH} characters."
        )

    return normalized_query


def validate_conversation_search_pagination(
    *,
    limit: int,
    offset: int,
) -> None:
    if limit < 1:
        raise ConversationValidationError(
            "Conversation search limit must be at least 1."
        )

    if limit > MAX_SEARCH_LIMIT:
        raise ConversationValidationError(
            "Conversation search limit must not exceed "
            f"{MAX_SEARCH_LIMIT}."
        )

    if offset < 0:
        raise ConversationValidationError(
            "Conversation search offset must not be negative."
        )

def search_document_conversations(
    db: Session,
    *,
    organization_id: str,
    query: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
    offset: int = 0,
    include_message_content: bool = False,
    archived: str = "false",
    deleted: str = "false",
) -> list[DocumentConversation]:
    """
    Search conversations belonging to one organisation.

    Archived conversations are excluded by default. The archived parameter
    accepts false, true, or all.
    """

    normalized_query = normalize_conversation_search_query(query)

    validate_conversation_search_pagination(
        limit=limit,
        offset=offset,
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

    escaped_query = (
        normalized_query
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )

    pattern = f"%{escaped_query}%"

    title_condition = func.lower(
        func.coalesce(
            DocumentConversation.title,
            "",
        )
    ).like(
        func.lower(pattern),
        escape="\\",
    )

    if include_message_content:
        matching_message_exists = (
            select(DocumentConversationMessage.id)
            .where(
                DocumentConversationMessage.conversation_id
                == DocumentConversation.id,
                func.lower(
                    DocumentConversationMessage.content
                ).like(
                    func.lower(pattern),
                    escape="\\",
                ),
            )
            .exists()
        )

        search_condition = or_(
            title_condition,
            matching_message_exists,
        )
    else:
        search_condition = title_condition

    statement = select(DocumentConversation).where(
        DocumentConversation.organization_id == organization_id,
        search_condition,
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
