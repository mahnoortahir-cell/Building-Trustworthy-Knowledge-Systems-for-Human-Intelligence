from uuid import uuid4

import pytest

from app.documents.retrieval import RetrievedChunk
from app.documents.retrieval_service import (
    RetrievalEmbeddingError,
    RetrievalValidationError,
    search_document_chunks,
)


class FakeEmbeddingProvider:
    model_name = "fake-model"
    dimensions = 3

    def __init__(self, embeddings: list[list[float]] | None = None) -> None:
        self.embeddings = embeddings or [[0.1, 0.2, 0.3]]
        self.received_texts: list[str] | None = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.received_texts = texts
        return self.embeddings


class FakeChunkSearchStore:
    def __init__(self, results: list[RetrievedChunk] | None = None) -> None:
        self.results = results or []
        self.received_query_embedding = None
        self.received_organization_id = None
        self.received_limit = None
        self.received_document_id = None
        self.received_document_version_id = None

    def search(
        self,
        db,
        *,
        query_embedding,
        organization_id,
        limit,
        document_id=None,
        document_version_id=None,
    ) -> list[RetrievedChunk]:
        self.received_query_embedding = query_embedding
        self.received_organization_id = organization_id
        self.received_limit = limit
        self.received_document_id = document_id
        self.received_document_version_id = document_version_id
        return self.results


def test_search_document_chunks_embeds_normalized_query_and_calls_store(
    db_session,
):
    document_id = "document-1"
    document_version_id = "version-1"

    expected_results = [
        RetrievedChunk(
            chunk_id="chunk-1",
            document_id=document_id,
            document_version_id=document_version_id,
            chunk_index=0,
            content="Relevant content",
            score=0.95,
        )
    ]

    provider = FakeEmbeddingProvider()
    store = FakeChunkSearchStore(expected_results)

    results = search_document_chunks(
        db_session,
        query="  What is NoorOS?  ",
        organization_id="organization-1",
        provider=provider,
        store=store,
        limit=3,
        document_id=document_id,
        document_version_id=document_version_id,
    )

    assert results == expected_results
    assert provider.received_texts == ["What is NoorOS?"]
    assert store.received_query_embedding == [0.1, 0.2, 0.3]
    assert store.received_organization_id == "organization-1"
    assert store.received_limit == 3
    assert store.received_document_id == document_id
    assert store.received_document_version_id == document_version_id


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_search_document_chunks_rejects_empty_query(db_session, query):
    provider = FakeEmbeddingProvider()
    store = FakeChunkSearchStore()

    with pytest.raises(
        RetrievalValidationError,
        match="Search query must not be empty",
    ):
        search_document_chunks(
            db_session,
            query=query,
            organization_id="organization-1",
            provider=provider,
            store=store,
        )


@pytest.mark.parametrize("limit", [0, -1])
def test_search_document_chunks_rejects_limit_below_one(db_session, limit):
    provider = FakeEmbeddingProvider()
    store = FakeChunkSearchStore()

    with pytest.raises(
        RetrievalValidationError,
        match="Search limit must be at least 1",
    ):
        search_document_chunks(
            db_session,
            query="NoorOS",
            organization_id="organization-1",
            provider=provider,
            store=store,
            limit=limit,
        )


def test_search_document_chunks_rejects_limit_above_one_hundred(db_session):
    provider = FakeEmbeddingProvider()
    store = FakeChunkSearchStore()

    with pytest.raises(
        RetrievalValidationError,
        match="Search limit must not exceed 100",
    ):
        search_document_chunks(
            db_session,
            query="NoorOS",
            organization_id="organization-1",
            provider=provider,
            store=store,
            limit=101,
        )


def test_search_document_chunks_rejects_multiple_query_embeddings(db_session):
    provider = FakeEmbeddingProvider(
        embeddings=[
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ]
    )
    store = FakeChunkSearchStore()

    with pytest.raises(
        RetrievalEmbeddingError,
        match="exactly one query embedding",
    ):
        search_document_chunks(
            db_session,
            query="NoorOS",
            organization_id="organization-1",
            provider=provider,
            store=store,
        )


def test_search_document_chunks_rejects_wrong_embedding_dimensions(db_session):
    provider = FakeEmbeddingProvider(
        embeddings=[[0.1, 0.2]]
    )
    store = FakeChunkSearchStore()

    with pytest.raises(
        RetrievalEmbeddingError,
        match="dimensions do not match",
    ):
        search_document_chunks(
            db_session,
            query="NoorOS",
            organization_id="organization-1",
            provider=provider,
            store=store,
        )