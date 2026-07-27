from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.documents.deterministic_llm import (
    DeterministicLLMProvider,
)
from app.documents.llm_provider import BaseLLMProvider
from app.documents.openai_llm import OpenAILLMProvider


class GenerateOnlyProvider(BaseLLMProvider):
    @property
    def model_name(self) -> str:
        return "generate-only"

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return f"{system_prompt}|{user_prompt}"


class InvalidGenerateProvider(BaseLLMProvider):
    @property
    def model_name(self) -> str:
        return "invalid"

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return None  # type: ignore[return-value]


class EmptyGenerateProvider(BaseLLMProvider):
    @property
    def model_name(self) -> str:
        return "empty"

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return ""


class FakeResponseStream:
    def __init__(
        self,
        events: list[object],
    ) -> None:
        self.events = events
        self.final_response_requested = False

    def __enter__(self) -> "FakeResponseStream":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None

    def __iter__(self) -> Iterator[object]:
        return iter(self.events)

    def get_final_response(self) -> object:
        self.final_response_requested = True
        return SimpleNamespace(output_text="complete")


def build_openai_provider_without_initialising_client(
    fake_stream: FakeResponseStream,
) -> OpenAILLMProvider:
    provider = object.__new__(OpenAILLMProvider)
    provider._model_name = "test-model"

    responses = MagicMock()
    responses.stream.return_value = fake_stream

    provider.client = SimpleNamespace(
        responses=responses,
    )

    return provider


def test_base_stream_falls_back_to_generate() -> None:
    provider = GenerateOnlyProvider()

    chunks = list(
        provider.stream(
            system_prompt="system",
            user_prompt="user",
        )
    )

    assert chunks == ["system|user"]


def test_base_stream_rejects_non_text_response() -> None:
    provider = InvalidGenerateProvider()

    with pytest.raises(
        TypeError,
        match="non-text response",
    ):
        list(
            provider.stream(
                system_prompt="system",
                user_prompt="user",
            )
        )


def test_base_stream_rejects_empty_response() -> None:
    provider = EmptyGenerateProvider()

    with pytest.raises(
        ValueError,
        match="empty response",
    ):
        list(
            provider.stream(
                system_prompt="system",
                user_prompt="user",
            )
        )


def test_deterministic_stream_reconstructs_complete_response() -> None:
    provider = DeterministicLLMProvider()

    expected = provider.generate(
        system_prompt="system",
        user_prompt="Explain NoorOS.",
    )

    chunks = list(
        provider.stream(
            system_prompt="system",
            user_prompt="Explain NoorOS.",
        )
    )

    assert len(chunks) > 1
    assert "".join(chunks) == expected
    assert all(chunks)


def test_deterministic_stream_uses_bounded_chunks() -> None:
    provider = DeterministicLLMProvider()

    chunks = list(
        provider.stream(
            system_prompt="system",
            user_prompt="x" * 200,
        )
    )

    assert all(
        len(chunk) <= provider.STREAM_CHUNK_SIZE
        for chunk in chunks
    )


def test_openai_stream_yields_only_text_delta_events() -> None:
    fake_stream = FakeResponseStream(
        [
            SimpleNamespace(
                type="response.created",
            ),
            SimpleNamespace(
                type="response.output_text.delta",
                delta="Noor",
            ),
            SimpleNamespace(
                type="response.output_text.delta",
                delta="OS",
            ),
            SimpleNamespace(
                type="response.completed",
            ),
        ]
    )

    provider = build_openai_provider_without_initialising_client(
        fake_stream
    )

    chunks = list(
        provider.stream(
            system_prompt="system prompt",
            user_prompt="user prompt",
        )
    )

    assert chunks == ["Noor", "OS"]
    assert fake_stream.final_response_requested is True

    provider.client.responses.stream.assert_called_once_with(
        model="test-model",
        instructions="system prompt",
        input="user prompt",
    )


def test_openai_stream_ignores_empty_deltas() -> None:
    fake_stream = FakeResponseStream(
        [
            SimpleNamespace(
                type="response.output_text.delta",
                delta="",
            ),
            SimpleNamespace(
                type="response.output_text.delta",
                delta=None,
            ),
            SimpleNamespace(
                type="response.output_text.delta",
                delta="Answer",
            ),
        ]
    )

    provider = build_openai_provider_without_initialising_client(
        fake_stream
    )

    result = "".join(
        provider.stream(
            system_prompt="system",
            user_prompt="user",
        )
    )

    assert result == "Answer"


def test_openai_stream_rejects_empty_stream() -> None:
    fake_stream = FakeResponseStream(
        [
            SimpleNamespace(
                type="response.created",
            ),
            SimpleNamespace(
                type="response.completed",
            ),
        ]
    )

    provider = build_openai_provider_without_initialising_client(
        fake_stream
    )

    with pytest.raises(
        RuntimeError,
        match="empty streamed response",
    ):
        list(
            provider.stream(
                system_prompt="system",
                user_prompt="user",
            )
        )


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        ("text", "text"),
        ("", ""),
        (None, ""),
        (123, ""),
    ],
)
def test_extract_text_delta(
    delta: object,
    expected: str,
) -> None:
    event = SimpleNamespace(delta=delta)

    assert (
        OpenAILLMProvider._extract_text_delta(event)
        == expected
    )
