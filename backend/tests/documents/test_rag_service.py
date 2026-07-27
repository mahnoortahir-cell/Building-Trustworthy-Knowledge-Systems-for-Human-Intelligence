import pytest

from app.documents.retrieval import RetrievedChunk
from app.documents.rag_service import (
    RagGenerationError,
    RagValidationError,
    generate_document_answer,
)
from collections.abc import Sequence

from app.documents.conversation_types import (
    ConversationHistoryMessage,
)


class FakeEmbeddingProvider:
    model_name = "fake-embedding-model"
    dimensions = 3

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeChunkSearchStore:
    def __init__(self, results: list[RetrievedChunk] | None = None) -> None:
        self.results = results or []
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
        self.received_organization_id = organization_id
        self.received_limit = limit
        self.received_document_id = document_id
        self.received_document_version_id = document_version_id
        return self.results




class FakeAnswerGenerator:
    model_name = "fake-answer-model"

    def __init__(self, answer: str = "Generated answer") -> None:
        self.answer = answer
        self.received_question: str | None = None
        self.received_chunks = None
        self.received_history: list[
            ConversationHistoryMessage
        ] = []

    def generate_answer(
        self,
        *,
        question: str,
        context_chunks,
        conversation_history: Sequence[
            ConversationHistoryMessage
        ] = (),
    ) -> str:
        self.received_question = question
        self.received_chunks = list(context_chunks)
        self.received_history = list(conversation_history)

        return self.answer


def make_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="chunk-1",
        document_id="document-1",
        document_version_id="version-1",
        chunk_index=2,
        content="NoorOS uses semantic retrieval over document chunks.",
        score=0.91,
    )


def test_generate_document_answer_returns_answer_and_citations(db_session):
    chunk = make_chunk()
    search_store = FakeChunkSearchStore([chunk])
    answer_generator = FakeAnswerGenerator(
        answer="NoorOS searches semantically relevant document chunks."
    )

    result = generate_document_answer(
        db_session,
        question="  How does NoorOS search documents?  ",
        organization_id="organization-1",
        embedding_provider=FakeEmbeddingProvider(),
        search_store=search_store,
        answer_generator=answer_generator,
        limit=4,
        document_id="document-1",
        document_version_id="version-1",
    )

    assert result.answer == (
        "NoorOS searches semantically relevant document chunks."
    )

    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "chunk-1"
    assert result.citations[0].document_id == "document-1"
    assert result.citations[0].document_version_id == "version-1"
    assert result.citations[0].chunk_index == 2
    assert result.citations[0].content == chunk.content
    assert result.citations[0].score == 0.91

    assert answer_generator.received_question == (
        "How does NoorOS search documents?"
    )
    assert answer_generator.received_chunks == [chunk]

    assert search_store.received_organization_id == "organization-1"
    assert search_store.received_limit == 4
    assert search_store.received_document_id == "document-1"
    assert search_store.received_document_version_id == "version-1"


@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_generate_document_answer_rejects_blank_question(
    db_session,
    question,
):
    with pytest.raises(
        RagValidationError,
        match="Question must not be empty",
    ):
        generate_document_answer(
            db_session,
            question=question,
            organization_id="organization-1",
            embedding_provider=FakeEmbeddingProvider(),
            search_store=FakeChunkSearchStore(),
            answer_generator=FakeAnswerGenerator(),
        )


@pytest.mark.parametrize("limit", [0, -1])
def test_generate_document_answer_rejects_limit_below_one(
    db_session,
    limit,
):
    with pytest.raises(
        RagValidationError,
        match="Context limit must be at least 1",
    ):
        generate_document_answer(
            db_session,
            question="What is NoorOS?",
            organization_id="organization-1",
            embedding_provider=FakeEmbeddingProvider(),
            search_store=FakeChunkSearchStore(),
            answer_generator=FakeAnswerGenerator(),
            limit=limit,
        )


def test_generate_document_answer_rejects_limit_above_twenty(
    db_session,
):
    with pytest.raises(
        RagValidationError,
        match="Context limit must not exceed 20",
    ):
        generate_document_answer(
            db_session,
            question="What is NoorOS?",
            organization_id="organization-1",
            embedding_provider=FakeEmbeddingProvider(),
            search_store=FakeChunkSearchStore(),
            answer_generator=FakeAnswerGenerator(),
            limit=21,
        )


def test_generate_document_answer_returns_fallback_when_no_chunks(
    db_session,
):
    result = generate_document_answer(
        db_session,
        question="What is NoorOS?",
        organization_id="organization-1",
        embedding_provider=FakeEmbeddingProvider(),
        search_store=FakeChunkSearchStore(results=[]),
        answer_generator=FakeAnswerGenerator(),
    )

    assert result.answer == (
        "I could not find enough relevant information "
        "in the selected documents."
    )
    assert result.citations == []


def test_generate_document_answer_rejects_empty_generated_answer(
    db_session,
):
    with pytest.raises(
        RagGenerationError,
        match="Answer generator returned an empty answer",
    ):
        generate_document_answer(
            db_session,
            question="What is NoorOS?",
            organization_id="organization-1",
            embedding_provider=FakeEmbeddingProvider(),
            search_store=FakeChunkSearchStore([make_chunk()]),
            answer_generator=FakeAnswerGenerator(answer="   "),
        )