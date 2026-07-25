from __future__ import annotations

import hashlib
import math
from typing import Protocol


class EmbeddingProviderError(Exception):
    """Raised when an embedding provider cannot generate embeddings."""


class EmbeddingProvider(Protocol):
    """
    Contract that every embedding provider must follow.

    Later, OpenAI, local models, or another provider can implement
    this interface without changing the document processing service.
    """

    @property
    def model_name(self) -> str:
        ...

    @property
    def dimensions(self) -> int:
        ...

    def embed_texts(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        ...


class DeterministicEmbeddingProvider:
    """
    Development and testing provider.

    This does not create meaningful semantic embeddings. It creates
    predictable vectors so the embedding pipeline can be tested without
    external APIs, API keys, network calls, or usage charges.
    """

    def __init__(
        self,
        dimensions: int = 8,
    ) -> None:
        if dimensions <= 0:
            raise ValueError(
                "Embedding dimensions must be greater than zero."
            )

        self._dimensions = dimensions

    @property
    def model_name(self) -> str:
        return "deterministic-test-embedding"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_texts(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        embeddings: list[list[float]] = []

        for text in texts:
            if not text or not text.strip():
                raise EmbeddingProviderError(
                    "Cannot generate an embedding for blank text."
                )

            embeddings.append(
                self._create_embedding(text)
            )

        return embeddings

    def _create_embedding(
        self,
        text: str,
    ) -> list[float]:
        values: list[float] = []
        counter = 0

        while len(values) < self._dimensions:
            digest = hashlib.sha256(
                f"{counter}:{text}".encode("utf-8")
            ).digest()

            for byte in digest:
                normalised_value = (byte / 127.5) - 1.0
                values.append(normalised_value)

                if len(values) == self._dimensions:
                    break

            counter += 1

        magnitude = math.sqrt(
            sum(value * value for value in values)
        )

        if magnitude == 0:
            raise EmbeddingProviderError(
                "Generated embedding has zero magnitude."
            )

        return [
            value / magnitude
            for value in values
        ]



def get_embedding_provider() -> EmbeddingProvider:
    return DeterministicEmbeddingProvider(
        dimensions=8,
    )