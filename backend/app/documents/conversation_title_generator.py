import re
from dataclasses import dataclass

from app.documents.llm_provider import BaseLLMProvider


CONVERSATION_TITLE_SYSTEM_PROMPT = """
You generate concise titles for document conversations.

Rules:
- Return only the title.
- Use 3 to 8 words.
- Do not use quotation marks.
- Do not end with punctuation.
- Do not use markdown.
- Describe the user's main topic accurately.
- Do not invent information.
""".strip()


DEFAULT_CONVERSATION_TITLE = "New Conversation"
MAX_TITLE_LENGTH = 100


class ConversationTitleGenerationError(RuntimeError):
    """Raised when a conversation title cannot be generated."""


@dataclass(frozen=True, slots=True)
class GeneratedConversationTitle:
    title: str
    model_name: str


def _normalize_source_text(
    value: str,
    *,
    field_name: str,
    max_length: int = 10_000,
) -> str:
    if not isinstance(value, str):
        raise ConversationTitleGenerationError(
            f"{field_name} must be text."
        )

    normalized = " ".join(value.split())

    if not normalized:
        raise ConversationTitleGenerationError(
            f"{field_name} must not be empty."
        )

    if len(normalized) > max_length:
        normalized = normalized[:max_length].rstrip()

    return normalized


def _strip_wrapping_characters(
    value: str,
) -> str:
    value = value.strip()

    wrapping_pairs = (
        ('"', '"'),
        ("'", "'"),
        ("`", "`"),
        ("“", "”"),
        ("‘", "’"),
    )

    changed = True

    while changed and len(value) >= 2:
        changed = False

        for opening, closing in wrapping_pairs:
            if value.startswith(opening) and value.endswith(closing):
                value = value[
                    len(opening) : len(value) - len(closing)
                ].strip()
                changed = True
                break

    return value


def normalize_conversation_title(
    raw_title: str,
    *,
    max_length: int = MAX_TITLE_LENGTH,
) -> str:
    """
    Convert provider output into a safe, concise conversation title.
    """

    if not isinstance(raw_title, str):
        raise ConversationTitleGenerationError(
            "The title provider returned a non-text response."
        )

    if max_length < 1:
        raise ConversationTitleGenerationError(
            "Title maximum length must be at least 1."
        )

    title = raw_title.strip()

    if not title:
        raise ConversationTitleGenerationError(
            "The title provider returned an empty response."
        )

    # Prefer the first non-empty line when a provider adds explanation.
    title = next(
        (
            line.strip()
            for line in title.splitlines()
            if line.strip()
        ),
        "",
    )

    title = re.sub(
        r"^\s*(?:title|conversation title)\s*:\s*",
        "",
        title,
        flags=re.IGNORECASE,
    )

    title = _strip_wrapping_characters(title)

    # Remove common markdown prefixes.
    title = re.sub(
        r"^\s{0,3}(?:#{1,6}|[-*•])\s+",
        "",
        title,
    )

    title = " ".join(title.split())

    # Remove trailing punctuation while preserving meaningful internal marks.
    title = title.rstrip(" \t\r\n.!?,;:")

    if len(title) > max_length:
        title = title[:max_length].rstrip()

        # Avoid ending halfway through a word where possible.
        if " " in title:
            shortened = title.rsplit(" ", 1)[0].rstrip()

            if shortened:
                title = shortened

        title = title.rstrip(" \t\r\n.!?,;:")

    if not title:
        raise ConversationTitleGenerationError(
            "The generated conversation title is invalid."
        )

    return title


def build_conversation_title_prompt(
    *,
    user_message: str,
    assistant_message: str | None = None,
) -> str:
    normalized_user_message = _normalize_source_text(
        user_message,
        field_name="User message",
    )

    sections = [
        "Create a concise title for this conversation.",
        "",
        "User message:",
        normalized_user_message,
    ]

    if assistant_message is not None:
        normalized_assistant_message = _normalize_source_text(
            assistant_message,
            field_name="Assistant message",
        )

        sections.extend(
            [
                "",
                "Assistant response:",
                normalized_assistant_message,
            ]
        )

    sections.extend(
        [
            "",
            "Return only the title.",
        ]
    )

    return "\n".join(sections)


class ConversationTitleGenerator:
    """
    Generate concise conversation titles through the configured LLM provider.
    """

    def __init__(
        self,
        *,
        provider: BaseLLMProvider,
    ) -> None:
        self.provider = provider
        self.model_name = provider.model_name

    def generate(
        self,
        *,
        user_message: str,
        assistant_message: str | None = None,
    ) -> GeneratedConversationTitle:
        prompt = build_conversation_title_prompt(
            user_message=user_message,
            assistant_message=assistant_message,
        )

        try:
            raw_title = self.provider.generate(
                system_prompt=CONVERSATION_TITLE_SYSTEM_PROMPT,
                user_prompt=prompt,
            )
        except Exception as exc:
            raise ConversationTitleGenerationError(
                "The conversation title provider failed."
            ) from exc

        title = normalize_conversation_title(
            raw_title,
        )

        return GeneratedConversationTitle(
            title=title,
            model_name=self.model_name,
        )


def generate_fallback_conversation_title(
    user_message: str,
    *,
    max_words: int = 8,
    max_length: int = MAX_TITLE_LENGTH,
) -> str:
    """
    Produce a deterministic title when AI title generation is unavailable.
    """

    normalized_message = _normalize_source_text(
        user_message,
        field_name="User message",
    )

    if max_words < 1:
        raise ConversationTitleGenerationError(
            "Fallback title max_words must be at least 1."
        )

    words = normalized_message.split()[:max_words]
    title = " ".join(words)

    title = normalize_conversation_title(
        title,
        max_length=max_length,
    )

    return title or DEFAULT_CONVERSATION_TITLE
