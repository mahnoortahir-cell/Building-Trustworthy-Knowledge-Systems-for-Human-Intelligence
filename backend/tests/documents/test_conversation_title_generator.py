from collections.abc import Iterator

import pytest

from app.documents.conversation_title_generator import (
    CONVERSATION_TITLE_SYSTEM_PROMPT,
    ConversationTitleGenerationError,
    ConversationTitleGenerator,
    build_conversation_title_prompt,
    generate_fallback_conversation_title,
    normalize_conversation_title,
)
from app.documents.llm_provider import BaseLLMProvider


class FakeTitleProvider(BaseLLMProvider):
    def __init__(
        self,
        response: object = "Installing NoorOS on Ubuntu",
        *,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, str]] = []

    @property
    def model_name(self) -> str:
        return "fake-title-model"

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
        )

        if self.error is not None:
            raise self.error

        return self.response  # type: ignore[return-value]

    def stream(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> Iterator[str]:
        yield self.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )


def test_build_prompt_contains_user_message() -> None:
    prompt = build_conversation_title_prompt(
        user_message="How do I install NoorOS?",
    )

    assert "How do I install NoorOS?" in prompt
    assert "Assistant response:" not in prompt
    assert prompt.endswith("Return only the title.")


def test_build_prompt_contains_assistant_message() -> None:
    prompt = build_conversation_title_prompt(
        user_message="How do I install NoorOS?",
        assistant_message="Use the installation guide.",
    )

    assert "How do I install NoorOS?" in prompt
    assert "Use the installation guide." in prompt
    assert "Assistant response:" in prompt


def test_build_prompt_normalizes_whitespace() -> None:
    prompt = build_conversation_title_prompt(
        user_message="  How   do I install   NoorOS?  ",
    )

    assert "How do I install NoorOS?" in prompt


def test_build_prompt_rejects_empty_user_message() -> None:
    with pytest.raises(
        ConversationTitleGenerationError,
        match="User message must not be empty",
    ):
        build_conversation_title_prompt(
            user_message="   ",
        )


@pytest.mark.parametrize(
    ("raw_title", "expected"),
    [
        (
            "Installing NoorOS on Ubuntu",
            "Installing NoorOS on Ubuntu",
        ),
        (
            '"Installing NoorOS on Ubuntu"',
            "Installing NoorOS on Ubuntu",
        ),
        (
            "“Installing NoorOS on Ubuntu”",
            "Installing NoorOS on Ubuntu",
        ),
        (
            "Title: Installing NoorOS on Ubuntu",
            "Installing NoorOS on Ubuntu",
        ),
        (
            "Conversation Title: Installing NoorOS",
            "Installing NoorOS",
        ),
        (
            "# Installing NoorOS",
            "Installing NoorOS",
        ),
        (
            "- Installing NoorOS",
            "Installing NoorOS",
        ),
        (
            "Installing NoorOS.",
            "Installing NoorOS",
        ),
        (
            "  Installing   NoorOS   ",
            "Installing NoorOS",
        ),
        (
            "Installing NoorOS\nThis is an explanation.",
            "Installing NoorOS",
        ),
    ],
)
def test_normalize_conversation_title(
    raw_title: str,
    expected: str,
) -> None:
    assert normalize_conversation_title(
        raw_title
    ) == expected


def test_normalize_title_enforces_maximum_length() -> None:
    result = normalize_conversation_title(
        "A very long generated conversation title about NoorOS installation",
        max_length=30,
    )

    assert len(result) <= 30
    assert result == "A very long generated"


def test_normalize_title_rejects_empty_response() -> None:
    with pytest.raises(
        ConversationTitleGenerationError,
        match="empty response",
    ):
        normalize_conversation_title("   ")


def test_normalize_title_rejects_non_text_response() -> None:
    with pytest.raises(
        ConversationTitleGenerationError,
        match="non-text response",
    ):
        normalize_conversation_title(
            123  # type: ignore[arg-type]
        )


def test_generator_calls_provider() -> None:
    provider = FakeTitleProvider(
        '"Installing NoorOS on Ubuntu."'
    )

    generator = ConversationTitleGenerator(
        provider=provider,
    )

    result = generator.generate(
        user_message="How do I install NoorOS?",
        assistant_message="Follow the Ubuntu installation steps.",
    )

    assert result.title == "Installing NoorOS on Ubuntu"
    assert result.model_name == "fake-title-model"

    assert len(provider.calls) == 1

    call = provider.calls[0]

    assert (
        call["system_prompt"]
        == CONVERSATION_TITLE_SYSTEM_PROMPT
    )
    assert "How do I install NoorOS?" in call["user_prompt"]
    assert (
        "Follow the Ubuntu installation steps."
        in call["user_prompt"]
    )


def test_generator_rejects_provider_failure() -> None:
    provider = FakeTitleProvider(
        error=RuntimeError("provider unavailable"),
    )

    generator = ConversationTitleGenerator(
        provider=provider,
    )

    with pytest.raises(
        ConversationTitleGenerationError,
        match="provider failed",
    ):
        generator.generate(
            user_message="How do I install NoorOS?",
        )


def test_generator_rejects_invalid_provider_output() -> None:
    provider = FakeTitleProvider(
        response=123,
    )

    generator = ConversationTitleGenerator(
        provider=provider,
    )

    with pytest.raises(
        ConversationTitleGenerationError,
        match="non-text response",
    ):
        generator.generate(
            user_message="How do I install NoorOS?",
        )


def test_fallback_title_uses_first_eight_words() -> None:
    result = generate_fallback_conversation_title(
        (
            "How can I install NoorOS on an Ubuntu "
            "server using Docker Compose?"
        )
    )

    assert result == (
        "How can I install NoorOS on an Ubuntu"
    )


def test_fallback_title_normalizes_whitespace() -> None:
    result = generate_fallback_conversation_title(
        "  Install   NoorOS   using   Docker  ",
    )

    assert result == "Install NoorOS using Docker"


def test_fallback_title_rejects_empty_message() -> None:
    with pytest.raises(
        ConversationTitleGenerationError,
        match="User message must not be empty",
    ):
        generate_fallback_conversation_title("   ")


def test_fallback_title_rejects_invalid_word_limit() -> None:
    with pytest.raises(
        ConversationTitleGenerationError,
        match="max_words must be at least 1",
    ):
        generate_fallback_conversation_title(
            "Install NoorOS",
            max_words=0,
        )
