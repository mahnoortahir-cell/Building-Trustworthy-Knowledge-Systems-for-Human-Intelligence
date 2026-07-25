import math

import pytest

from app.documents.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProviderError,
)


def test_provider_returns_empty_list_for_empty_input() -> None:
    provider = DeterministicEmbeddingProvider()

    result = provider.embed_texts([])

    assert result == []


def test_provider_returns_expected_vector_dimensions() -> None:
    provider = DeterministicEmbeddingProvider(
        dimensions=12
    )

    embeddings = provider.embed_texts(
        ["NoorOS trustworthy knowledge system"]
    )

    assert len(embeddings) == 1
    assert len(embeddings[0]) == 12


def test_provider_is_deterministic() -> None:
    provider = DeterministicEmbeddingProvider()

    first_result = provider.embed_texts(
        ["The same document chunk"]
    )

    second_result = provider.embed_texts(
        ["The same document chunk"]
    )

    assert first_result == second_result


def test_different_text_produces_different_embeddings() -> None:
    provider = DeterministicEmbeddingProvider()

    embeddings = provider.embed_texts(
        [
            "First document chunk",
            "Second document chunk",
        ]
    )

    assert embeddings[0] != embeddings[1]


def test_embeddings_are_normalised() -> None:
    provider = DeterministicEmbeddingProvider(
        dimensions=16
    )

    embedding = provider.embed_texts(
        ["Normalised document embedding"]
    )[0]

    magnitude = math.sqrt(
        sum(value * value for value in embedding)
    )

    assert magnitude == pytest.approx(
        1.0,
        abs=1e-9,
    )


def test_provider_rejects_blank_text() -> None:
    provider = DeterministicEmbeddingProvider()

    with pytest.raises(
        EmbeddingProviderError,
        match="blank text",
    ):
        provider.embed_texts(["   "])


def test_provider_rejects_invalid_dimensions() -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        DeterministicEmbeddingProvider(
            dimensions=0
        )