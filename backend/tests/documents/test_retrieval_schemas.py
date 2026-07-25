import pytest
from pydantic import ValidationError

from app.documents.retrieval_schemas import (
    RetrievedChunkResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
)


def test_semantic_search_request_uses_default_limit():
    request = SemanticSearchRequest(query="What is NoorOS?")

    assert request.query == "What is NoorOS?"
    assert request.limit == 5
    assert request.document_id is None
    assert request.document_version_id is None


def test_semantic_search_request_accepts_filters():
    request = SemanticSearchRequest(
        query="Find authentication details",
        limit=10,
        document_id="document-123",
        document_version_id="version-456",
    )

    assert request.limit == 10
    assert request.document_id == "document-123"
    assert request.document_version_id == "version-456"


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_semantic_search_request_rejects_invalid_limit(limit):
    with pytest.raises(ValidationError):
        SemanticSearchRequest(
            query="NoorOS",
            limit=limit,
        )


def test_semantic_search_request_rejects_empty_query():
    with pytest.raises(ValidationError):
        SemanticSearchRequest(query="")


def test_semantic_search_request_rejects_query_over_two_thousand_characters():
    with pytest.raises(ValidationError):
        SemanticSearchRequest(query="x" * 2_001)


def test_semantic_search_response_serializes_results():
    result = RetrievedChunkResponse(
        chunk_id="chunk-1",
        document_id="document-1",
        document_version_id="version-1",
        chunk_index=2,
        content="Relevant NoorOS content",
        score=0.92,
    )

    response = SemanticSearchResponse(
        query="What is NoorOS?",
        result_count=1,
        results=[result],
    )

    payload = response.model_dump()

    assert payload == {
        "query": "What is NoorOS?",
        "result_count": 1,
        "results": [
            {
                "chunk_id": "chunk-1",
                "document_id": "document-1",
                "document_version_id": "version-1",
                "chunk_index": 2,
                "content": "Relevant NoorOS content",
                "score": 0.92,
            }
        ],
    }