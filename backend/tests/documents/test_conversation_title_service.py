from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.documents.conversation_title_service import (
    assign_automatic_conversation_title,
    conversation_needs_automatic_title,
)
from app.documents.llm_provider import BaseLLMProvider


class FakeProvider(BaseLLMProvider):
    def __init__(
        self,
        response: str = "Installing NoorOS on Ubuntu",
        *,
        model_name: str = "fake-title-model",
    ) -> None:
        self.response = response
        self._model_name = model_name
        self.generate_calls = 0

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        self.generate_calls += 1
        return self.response

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


def conversation(
    title: str | None,
) -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        updated_at=None,
    )


def test_none_title_requires_automatic_title() -> None:
    assert conversation_needs_automatic_title(
        conversation(None)
    ) is True


def test_blank_title_requires_automatic_title() -> None:
    assert conversation_needs_automatic_title(
        conversation("   ")
    ) is True


def test_existing_title_is_preserved() -> None:
    assert conversation_needs_automatic_title(
        conversation("Existing title")
    ) is False


def test_assigns_generated_title_without_committing() -> None:
    db = MagicMock()
    item = conversation(None)
    provider = FakeProvider(
        '"Installing NoorOS on Ubuntu."'
    )

    result = assign_automatic_conversation_title(
        db,
        conversation=item,  # type: ignore[arg-type]
        provider=provider,
        user_message="How do I install NoorOS?",
        assistant_message="Use the Ubuntu installation guide.",
    )

    assert result == "Installing NoorOS on Ubuntu"
    assert item.title == "Installing NoorOS on Ubuntu"
    assert item.updated_at is not None

    db.add.assert_called_once_with(item)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()

    assert provider.generate_calls == 1


def test_existing_title_is_never_overwritten() -> None:
    db = MagicMock()
    item = conversation("Custom user title")
    provider = FakeProvider()

    result = assign_automatic_conversation_title(
        db,
        conversation=item,  # type: ignore[arg-type]
        provider=provider,
        user_message="How do I install NoorOS?",
        assistant_message="Use the guide.",
    )

    assert result is None
    assert item.title == "Custom user title"

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()

    assert provider.generate_calls == 0


def test_deterministic_provider_uses_fallback_title() -> None:
    db = MagicMock()
    item = conversation(None)

    provider = FakeProvider(
        response="This response must not be used",
        model_name="deterministic-llm",
    )

    result = assign_automatic_conversation_title(
        db,
        conversation=item,  # type: ignore[arg-type]
        provider=provider,
        user_message=(
            "How can I install NoorOS on an Ubuntu "
            "server using Docker Compose?"
        ),
        assistant_message="Follow these instructions.",
    )

    assert result == (
        "How can I install NoorOS on an Ubuntu"
    )

    assert item.title == (
        "How can I install NoorOS on an Ubuntu"
    )

    assert provider.generate_calls == 0


def test_invalid_ai_output_uses_fallback_title() -> None:
    db = MagicMock()
    item = conversation(None)

    provider = FakeProvider(
        response="   ",
    )

    result = assign_automatic_conversation_title(
        db,
        conversation=item,  # type: ignore[arg-type]
        provider=provider,
        user_message="Explain NoorOS document search",
        assistant_message="NoorOS uses semantic retrieval.",
    )

    assert result == "Explain NoorOS document search"
    assert item.title == "Explain NoorOS document search"

    db.flush.assert_called_once_with()
