from collections.abc import Sequence
from typing import cast

import pytest

from app.documents.conversation_types import (
    ConversationHistoryMessage,
)
from app.documents.rag import AnswerGenerator
from app.documents.rag_service import (
    RagGenerationError,
    RagValidationError,
    generate_document_answer,
)
from app.documents.retrieval import RetrievedChunk


class RecordingAnswerGenerator:
    model_name = "recording-answer-generator"

    def __init__(self) -> None:
        self.received_question: str | None = None
        self.received_chunks: list[RetrievedChunk] = []
        self.received_history: list[
            ConversationHistoryMessage
        ] = []

    def generate_answer(
        self,
        *,
        question: str,
        context_chunks: Sequence[RetrievedChunk],
        conversation_history: Sequence[
            ConversationHistoryMessage
        ] = (),
    ) -> str:
        self.received_question = question
        self.received_chunks = list(context_chunks)
        self.received_history = list(conversation_history)

        return "A grounded test answer."


class EmptyAnswerGenerator:
    model_name = "empty-answer-generator"

    def generate_answer(
        self,
        *,
        question: str,
        context_chunks: Sequence[RetrievedChunk],
        conversation_history: Sequence[
            ConversationHistoryMessage
        ] = (),
    ) -> str:
        del question
        del context_chunks
        del conversation_history

        return "   "


def make_chunk(
    *,
    chunk_id: str,
    content: str,
    score: float = 0.95,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="document-1",
        document_version_id="version-1",
        chunk_index=0,
        content=content,
        score=score,
    )


def test_rag_passes_conversation_history_to_generator(
    monkeypatch,
) -> None:
    chunks = [
        make_chunk(
            chunk_id="chunk-1",
            content="The study used a qualitative methodology.",
        )
    ]

    monkeypatch.setattr(
        "app.documents.rag_service.search_document_chunks",
        lambda *args, **kwargs: chunks,
    )

    history = [
        ConversationHistoryMessage(
            role="user",
            content="What methodology was used?",
        ),
        ConversationHistoryMessage(
            role="assistant",
            content="A qualitative methodology was used.",
        ),
    ]

    generator = RecordingAnswerGenerator()

    result = generate_document_answer(
        cast(object, None),
        question="Why was it selected?",
        organization_id="organization-1",
        embedding_provider=cast(object, None),
        search_store=cast(object, None),
        answer_generator=cast(
            AnswerGenerator,
            generator,
        ),
        conversation_history=history,
    )

    assert result.answer == "A grounded test answer."
    assert generator.received_question == "Why was it selected?"
    assert generator.received_history == history
    assert generator.received_chunks == chunks
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "chunk-1"


def test_rag_removes_duplicate_chunk_content(
    monkeypatch,
) -> None:
    chunks = [
        make_chunk(
            chunk_id="chunk-1",
            content="The study used qualitative analysis.",
            score=0.99,
        ),
        make_chunk(
            chunk_id="chunk-2",
            content="  THE study used qualitative analysis. ",
            score=0.80,
        ),
    ]

    monkeypatch.setattr(
        "app.documents.rag_service.search_document_chunks",
        lambda *args, **kwargs: chunks,
    )

    generator = RecordingAnswerGenerator()

    result = generate_document_answer(
        cast(object, None),
        question="What analysis was used?",
        organization_id="organization-1",
        embedding_provider=cast(object, None),
        search_store=cast(object, None),
        answer_generator=cast(
            AnswerGenerator,
            generator,
        ),
    )

    assert len(generator.received_chunks) == 1
    assert generator.received_chunks[0].chunk_id == "chunk-1"
    assert len(result.citations) == 1


def test_rag_rejects_empty_question() -> None:
    with pytest.raises(
        RagValidationError,
        match="Question must not be empty",
    ):
        generate_document_answer(
            cast(object, None),
            question="   ",
            organization_id="organization-1",
            embedding_provider=cast(object, None),
            search_store=cast(object, None),
            answer_generator=cast(object, None),
        )


def test_rag_rejects_invalid_history_role() -> None:
    invalid_history = [
        cast(
            ConversationHistoryMessage,
            ConversationHistoryMessage(
                role="user",
                content="Valid content",
            ),
        )
    ]

    object.__setattr__(
        invalid_history[0],
        "role",
        "system",
    )

    with pytest.raises(
        RagValidationError,
        match="unsupported role",
    ):
        generate_document_answer(
            cast(object, None),
            question="What does the document say?",
            organization_id="organization-1",
            embedding_provider=cast(object, None),
            search_store=cast(object, None),
            answer_generator=cast(object, None),
            conversation_history=invalid_history,
        )


def test_rag_rejects_empty_generated_answer(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.documents.rag_service.search_document_chunks",
        lambda *args, **kwargs: [
            make_chunk(
                chunk_id="chunk-1",
                content="Relevant document information.",
            )
        ],
    )

    with pytest.raises(
        RagGenerationError,
        match="empty answer",
    ):
        generate_document_answer(
            cast(object, None),
            question="What does the document say?",
            organization_id="organization-1",
            embedding_provider=cast(object, None),
            search_store=cast(object, None),
            answer_generator=EmptyAnswerGenerator(),
        )


def test_rag_returns_fallback_when_no_chunks(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.documents.rag_service.search_document_chunks",
        lambda *args, **kwargs: [],
    )

    result = generate_document_answer(
        cast(object, None),
        question="What does the document say?",
        organization_id="organization-1",
        embedding_provider=cast(object, None),
        search_store=cast(object, None),
        answer_generator=cast(object, None),
    )

    assert result.citations == []
    assert "could not find enough relevant information" in (
        result.answer.lower()
    )
