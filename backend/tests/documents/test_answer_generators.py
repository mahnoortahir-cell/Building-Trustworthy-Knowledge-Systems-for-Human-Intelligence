import pytest

from app.documents.answer_generators import (
    DeterministicAnswerGenerator,
)
from app.documents.retrieval import RetrievedChunk


def make_chunk(
    *,
    chunk_id: str = "chunk-1",
    content: str = "Sample document content.",
    score: float = 0.9,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="document-1",
        document_version_id="version-1",
        chunk_index=0,
        content=content,
        score=score,
    )


def test_generate_answer_uses_retrieved_content():
    generator = DeterministicAnswerGenerator()

    result = generator.generate_answer(
        question="What is the document about?",
        context_chunks=[
            make_chunk(
                content=(
                    "The thesis studies semantic document retrieval."
                )
            )
        ],
    )

    assert result == (
        "Based on the selected documents:\n\n"
        "The thesis studies semantic document retrieval."
    )


def test_generate_answer_normalizes_whitespace():
    generator = DeterministicAnswerGenerator()

    result = generator.generate_answer(
        question="What is discussed?",
        context_chunks=[
            make_chunk(
                content=(
                    "Semantic   retrieval\n"
                    "uses embeddings\tand vector search."
                )
            )
        ],
    )

    assert result == (
        "Based on the selected documents:\n\n"
        "Semantic retrieval uses embeddings and vector search."
    )


def test_generate_answer_respects_max_chunks():
    generator = DeterministicAnswerGenerator(max_chunks=2)

    result = generator.generate_answer(
        question="Summarize the document.",
        context_chunks=[
            make_chunk(
                chunk_id="chunk-1",
                content="First passage.",
            ),
            make_chunk(
                chunk_id="chunk-2",
                content="Second passage.",
            ),
            make_chunk(
                chunk_id="chunk-3",
                content="Third passage.",
            ),
        ],
    )

    assert "First passage." in result
    assert "Second passage." in result
    assert "Third passage." not in result


def test_generate_answer_truncates_long_content():
    generator = DeterministicAnswerGenerator(
        max_characters_per_chunk=10,
    )

    result = generator.generate_answer(
        question="What is discussed?",
        context_chunks=[
            make_chunk(content="1234567890ABCDEFGHIJ")
        ],
    )

    assert result == (
        "Based on the selected documents:\n\n"
        "1234567890..."
    )


def test_generate_answer_ignores_blank_chunks():
    generator = DeterministicAnswerGenerator()

    result = generator.generate_answer(
        question="What is discussed?",
        context_chunks=[
            make_chunk(
                chunk_id="chunk-1",
                content="   ",
            ),
            make_chunk(
                chunk_id="chunk-2",
                content="Useful information.",
            ),
        ],
    )

    assert result == (
        "Based on the selected documents:\n\n"
        "Useful information."
    )


def test_generate_answer_returns_empty_for_no_chunks():
    generator = DeterministicAnswerGenerator()

    result = generator.generate_answer(
        question="What is discussed?",
        context_chunks=[],
    )

    assert result == ""


def test_generate_answer_returns_empty_when_all_chunks_are_blank():
    generator = DeterministicAnswerGenerator()

    result = generator.generate_answer(
        question="What is discussed?",
        context_chunks=[
            make_chunk(content="   "),
            make_chunk(content="\n\t"),
        ],
    )

    assert result == ""


@pytest.mark.parametrize("max_chunks", [0, -1])
def test_constructor_rejects_invalid_max_chunks(max_chunks):
    with pytest.raises(
        ValueError,
        match="max_chunks must be at least 1",
    ):
        DeterministicAnswerGenerator(
            max_chunks=max_chunks,
        )


@pytest.mark.parametrize(
    "max_characters_per_chunk",
    [0, -1],
)
def test_constructor_rejects_invalid_character_limit(
    max_characters_per_chunk,
):
    with pytest.raises(
        ValueError,
        match=(
            "max_characters_per_chunk must be at least 1"
        ),
    ):
        DeterministicAnswerGenerator(
            max_characters_per_chunk=(
                max_characters_per_chunk
            ),
        )