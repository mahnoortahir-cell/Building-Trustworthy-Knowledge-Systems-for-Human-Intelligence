from pydantic import BaseModel, Field


class DocumentAnswerRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
        examples=["What is this document about?"],
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
    )
    document_id: str | None = None
    document_version_id: str | None = None


class AnswerCitationResponse(BaseModel):
    chunk_id: str
    document_id: str
    document_version_id: str
    chunk_index: int
    content: str
    score: float


class DocumentAnswerResponse(BaseModel):
    answer: str
    citations: list[AnswerCitationResponse]