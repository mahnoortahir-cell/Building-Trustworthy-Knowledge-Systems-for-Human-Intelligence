from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(
        default=None,
        max_length=255,
    )


class ConversationUpdateRequest(BaseModel):
    """
    Request payload for updating a conversation.

    The field is required, but its value may be null. This distinction allows
    clients to explicitly clear a conversation title while rejecting an empty
    PATCH payload.
    """

    title: str | None = Field(
        max_length=255,
    )


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    created_by_user_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationDetailResponse(ConversationResponse):
    messages: list[ConversationMessageResponse]


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    count: int

class ConversationRegenerateRequest(BaseModel):
    context_limit: int = Field(
        default=10,
        ge=1,
        le=20,
    )
    history_limit: int = Field(
        default=20,
        ge=1,
        le=100,
    )
    document_id: str | None = None
    document_version_id: str | None = None


class ConversationRegenerateResponse(BaseModel):
    answer: str
    citations: list
    conversation_id: str
    assistant_message_id: str
    source_user_message_id: str

