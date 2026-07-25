from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.documents.retrieval import DatabaseChunkSearchStore


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class RecordingSession:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed_statement = None

    def execute(self, statement):
        self.executed_statement = statement
        return FakeResult(self.rows)


def compile_postgresql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"render_postcompile": True},
        )
    )


def test_database_store_maps_ranked_rows_to_retrieved_chunks():
    session = RecordingSession(
        rows=[
            SimpleNamespace(
                id="chunk-1",
                document_id="document-1",
                document_version_id="version-1",
                chunk_index=0,
                text="Most relevant content",
                distance=0.10,
            ),
            SimpleNamespace(
                id="chunk-2",
                document_id="document-1",
                document_version_id="version-1",
                chunk_index=1,
                text="Less relevant content",
                distance=0.35,
            ),
        ]
    )

    store = DatabaseChunkSearchStore()

    results = store.search(
        session,
        query_embedding=[0.1] * 8,
        organization_id="organization-1",
        limit=2,
    )

    assert len(results) == 2

    assert results[0].chunk_id == "chunk-1"
    assert results[0].document_id == "document-1"
    assert results[0].document_version_id == "version-1"
    assert results[0].chunk_index == 0
    assert results[0].content == "Most relevant content"
    assert results[0].score == pytest.approx(0.90)

    assert results[1].chunk_id == "chunk-2"
    assert results[1].content == "Less relevant content"
    assert results[1].score == pytest.approx(0.65)


def test_database_store_builds_cosine_distance_query():
    session = RecordingSession()
    store = DatabaseChunkSearchStore()

    store.search(
        session,
        query_embedding=[0.1] * 8,
        organization_id="organization-1",
        limit=5,
    )

    sql = compile_postgresql(session.executed_statement)

    assert "document_chunks.embedding <=>" in sql
    assert "document_chunks.embedding IS NOT NULL" in sql
    assert "document_chunks.embedding_status" in sql
    assert "documents.organization_id" in sql
    assert "ORDER BY" in sql
    assert "LIMIT" in sql


def test_database_store_applies_document_and_version_filters():
    session = RecordingSession()
    store = DatabaseChunkSearchStore()

    store.search(
        session,
        query_embedding=[0.2] * 8,
        organization_id="organization-1",
        limit=3,
        document_id="document-123",
        document_version_id="version-456",
    )

    statement = session.executed_statement
    sql = compile_postgresql(statement)
    params = statement.compile(
        dialect=postgresql.dialect()
    ).params

    assert "documents.organization_id" in sql
    assert "document_versions.document_id" in sql
    assert "document_chunks.document_version_id" in sql

    assert "organization-1" in params.values()
    assert "document-123" in params.values()
    assert "version-456" in params.values()