from pydantic import BaseModel, Field


class SemanticSearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=2_000,
        description="Natural-language query used to search document chunks.",
    )

    limit: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Maximum number of matching chunks to return.",
    )

    document_id: str | None = Field(
        default=None,
        description="Optionally restrict search to one document.",
    )

    document_version_id: str | None = Field(
        default=None,
        description="Optionally restrict search to one document version.",
    )


class RetrievedChunkResponse(BaseModel):
    chunk_id: str
    document_id: str
    document_version_id: str
    chunk_index: int
    content: str
    score: float


class SemanticSearchResponse(BaseModel):
    query: str
    result_count: int
    results: list[RetrievedChunkResponse]