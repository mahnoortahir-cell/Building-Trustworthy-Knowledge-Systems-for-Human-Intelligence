from pydantic import BaseModel, Field


class DocumentAnswerRequest(BaseModel):
    """
    Request used to ask a grounded question about uploaded documents.

    conversation_id is optional so the endpoint can still support:
    - one-off document questions;
    - persistent conversation-aware questions.
    """

    question: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="Question to answer using uploaded document content.",
    )

    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of relevant document chunks to retrieve.",
    )

    document_id: str | None = Field(
        default=None,
        description="Optional document to restrict retrieval to.",
    )

    document_version_id: str | None = Field(
        default=None,
        description="Optional document version to restrict retrieval to.",
    )

    conversation_id: str | None = Field(
        default=None,
        description=(
            "Optional saved conversation. When supplied, previous messages "
            "are used as conversation history and the new exchange is saved."
        ),
    )


class AnswerCitationResponse(BaseModel):
    """Document chunk used as evidence for an answer."""

    chunk_id: str
    document_id: str
    document_version_id: str
    chunk_index: int
    content: str
    score: float


class DocumentAnswerResponse(BaseModel):
    """Grounded answer returned by the document question endpoint."""

    conversation_id: str | None = Field(
        default=None,
        description=(
            "Conversation containing the saved exchange. It is null for "
            "one-off questions that were not attached to a conversation."
        ),
    )

    answer: str

    citations: list[AnswerCitationResponse] = Field(
        default_factory=list,
    )
