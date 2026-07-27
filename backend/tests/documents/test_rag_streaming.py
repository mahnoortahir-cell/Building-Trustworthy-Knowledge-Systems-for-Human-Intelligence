from collections.abc import Iterator, Sequence
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.documents.conversation_types import (
    ConversationHistoryMessage,
)
from app.documents.llm_answer_generator import (
    LLMAnswerGenerator,
)
from app.documents.llm_provider import BaseLLMProvider
from app.documents.rag_service import (
    INSUFFICIENT_CONTEXT_ANSWER,
    RagGenerationError,
    RagValidationError,
    generate_document_answer_stream,
)


class FakeStreamingProvider(BaseLLMProvider):
    def __init__(
        self,
        chunks: list[object],
    ) -> None:
        self.chunks = chunks

    @property
    def model_name(self) -> str:
        return "fake-streaming-provider"

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return "".join(
            chunk
            for chunk in self.chunks
            if isinstance(chunk, str)
        )

    def stream(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> Iterator[str]:
        for chunk in self.chunks:
            yield chunk  # type: ignore[misc]


class FakeStreamingAnswerGenerator:
    def __init__(
        self,
        chunks: list[object],
    ) -> None:
        self.chunks = chunks
        self.received_history: Sequence[
            ConversationHistoryMessage
        ] | None = None
        self.received_chunks: Sequence[object] | None = None

    def stream_answer(
        self,
        *,
        question: str,
        context_chunks: Sequence[object],
        conversation_history: Sequence[
            ConversationHistoryMessage
        ] = (),
    ) -> Iterator[str]:
        self.received_history = conversation_history
        self.received_chunks = context_chunks

        for chunk in self.chunks:
            yield chunk  # type: ignore[misc]


def retrieved_chunk(
    *,
    chunk_id: str = "chunk-1",
    content: str = "NoorOS is a document platform.",
    score: float = 0.95,
) -> object:
    return SimpleNamespace(
        chunk_id=chunk_id,
        document_id="document-1",
        document_version_id="version-1",
        chunk_index=0,
        content=content,
        score=score,
    )


def patch_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    chunks: list[object],
) -> None:
    monkeypatch.setattr(
        "app.documents.rag_service.search_document_chunks",
        MagicMock(return_value=chunks),
    )


def call_stream_service(
    *,
    answer_generator: object,
) -> object:
    return generate_document_answer_stream(
        MagicMock(),
        question="What is NoorOS?",
        organization_id="organization-1",
        embedding_provider=MagicMock(),
        search_store=MagicMock(),
        answer_generator=answer_generator,
    )


def test_llm_answer_generator_reconstructs_stream() -> None:
    provider = FakeStreamingProvider(
        ["Noor", "OS", " answer"]
    )
    generator = LLMAnswerGenerator(provider=provider)

    chunks = list(
        generator.stream_answer(
            question="What is NoorOS?",
            context_chunks=[retrieved_chunk()],
        )
    )

    assert chunks == ["Noor", "OS", " answer"]
    assert "".join(chunks) == "NoorOS answer"


def test_llm_answer_generator_ignores_empty_chunks() -> None:
    provider = FakeStreamingProvider(
        ["Noor", "", "OS"]
    )
    generator = LLMAnswerGenerator(provider=provider)

    assert list(
        generator.stream_answer(
            question="What is NoorOS?",
            context_chunks=[retrieved_chunk()],
        )
    ) == ["Noor", "OS"]


def test_llm_answer_generator_rejects_non_text_chunk() -> None:
    provider = FakeStreamingProvider(
        ["valid", 123]
    )
    generator = LLMAnswerGenerator(provider=provider)

    with pytest.raises(
        TypeError,
        match="non-text chunk",
    ):
        list(
            generator.stream_answer(
                question="What is NoorOS?",
                context_chunks=[retrieved_chunk()],
            )
        )


def test_llm_answer_generator_rejects_empty_stream() -> None:
    provider = FakeStreamingProvider(
        ["", ""]
    )
    generator = LLMAnswerGenerator(provider=provider)

    with pytest.raises(
        ValueError,
        match="empty streamed answer",
    ):
        list(
            generator.stream_answer(
                question="What is NoorOS?",
                context_chunks=[retrieved_chunk()],
            )
        )


def test_streaming_rag_returns_chunks_and_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_retrieval(
        monkeypatch,
        [retrieved_chunk()],
    )

    generator = FakeStreamingAnswerGenerator(
        ["Noor", "OS"]
    )

    result = call_stream_service(
        answer_generator=generator,
    )

    assert list(result.answer_chunks) == ["Noor", "OS"]
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "chunk-1"
    assert result.citations[0].content == (
        "NoorOS is a document platform."
    )


def test_streaming_rag_deduplicates_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_retrieval(
        monkeypatch,
        [
            retrieved_chunk(
                chunk_id="chunk-1",
                content="Same content",
            ),
            retrieved_chunk(
                chunk_id="chunk-2",
                content="  same   CONTENT  ",
            ),
        ],
    )

    generator = FakeStreamingAnswerGenerator(
        ["Answer"]
    )

    result = call_stream_service(
        answer_generator=generator,
    )

    assert list(result.answer_chunks) == ["Answer"]
    assert len(result.citations) == 1
    assert generator.received_chunks is not None
    assert len(generator.received_chunks) == 1


def test_streaming_rag_returns_fallback_without_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_retrieval(monkeypatch, [])

    generator = FakeStreamingAnswerGenerator(
        ["This must not be used"]
    )

    result = call_stream_service(
        answer_generator=generator,
    )

    assert list(result.answer_chunks) == [
        INSUFFICIENT_CONTEXT_ANSWER
    ]
    assert result.citations == []
    assert generator.received_chunks is None


def test_streaming_rag_wraps_generator_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_retrieval(
        monkeypatch,
        [retrieved_chunk()],
    )

    class FailingGenerator:
        def stream_answer(
            self,
            *,
            question: str,
            context_chunks: Sequence[object],
            conversation_history: Sequence[
                ConversationHistoryMessage
            ] = (),
        ) -> Iterator[str]:
            yield "partial"
            raise RuntimeError("provider failed")

    result = call_stream_service(
        answer_generator=FailingGenerator(),
    )

    stream = result.answer_chunks

    assert next(stream) == "partial"

    with pytest.raises(
        RagGenerationError,
        match="Failed to generate a streamed document answer",
    ):
        next(stream)


def test_streaming_rag_rejects_invalid_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_retrieval(
        monkeypatch,
        [retrieved_chunk()],
    )

    generator = FakeStreamingAnswerGenerator(
        ["Answer", 123]
    )

    result = call_stream_service(
        answer_generator=generator,
    )

    with pytest.raises(
        RagGenerationError,
        match="invalid response",
    ):
        list(result.answer_chunks)


def test_streaming_rag_rejects_empty_generated_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_retrieval(
        monkeypatch,
        [retrieved_chunk()],
    )

    generator = FakeStreamingAnswerGenerator(
        ["", ""]
    )

    result = call_stream_service(
        answer_generator=generator,
    )

    with pytest.raises(
        RagGenerationError,
        match="empty streamed answer",
    ):
        list(result.answer_chunks)


def test_streaming_rag_uses_prepared_conversation_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_retrieval(
        monkeypatch,
        [retrieved_chunk()],
    )

    generator = FakeStreamingAnswerGenerator(
        ["Answer"]
    )

    history = [
        ConversationHistoryMessage(
            role="user",
            content="   Previous question   ",
        ),
        ConversationHistoryMessage(
            role="assistant",
            content="Previous answer",
        ),
    ]

    result = generate_document_answer_stream(
        MagicMock(),
        question="Follow-up question",
        organization_id="organization-1",
        embedding_provider=MagicMock(),
        search_store=MagicMock(),
        answer_generator=generator,
        conversation_history=history,
    )

    assert list(result.answer_chunks) == ["Answer"]

    assert generator.received_history is not None
    assert [
        item.content
        for item in generator.received_history
    ] == [
        "Previous question",
        "Previous answer",
    ]


def test_streaming_rag_validates_question_before_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieval_mock = MagicMock()

    monkeypatch.setattr(
        "app.documents.rag_service.search_document_chunks",
        retrieval_mock,
    )

    with pytest.raises(
        RagValidationError,
        match="Question must not be empty",
    ):
        generate_document_answer_stream(
            MagicMock(),
            question="   ",
            organization_id="organization-1",
            embedding_provider=MagicMock(),
            search_store=MagicMock(),
            answer_generator=FakeStreamingAnswerGenerator(
                ["Answer"]
            ),
        )

    retrieval_mock.assert_not_called()
