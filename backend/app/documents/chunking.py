from __future__ import annotations


DEFAULT_CHUNK_SIZE = 1_000
DEFAULT_CHUNK_OVERLAP = 150


def normalize_text(text: str) -> str:
    """
    Normalize extracted document text while preserving paragraph boundaries.
    """
    paragraphs = []

    for paragraph in text.splitlines():
        cleaned_paragraph = " ".join(paragraph.split())

        if cleaned_paragraph:
            paragraphs.append(cleaned_paragraph)

    return "\n\n".join(paragraphs)


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """
    Split text into overlapping character-based chunks.

    Paragraph boundaries are preferred where possible. Long paragraphs are
    split directly when they exceed the configured chunk size.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    normalized_text = normalize_text(text)

    if not normalized_text:
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(normalized_text)

    while start < text_length:
        end = min(start + chunk_size, text_length)

        if end < text_length:
            paragraph_break = normalized_text.rfind(
                "\n\n",
                start,
                end,
            )

            if paragraph_break > start:
                end = paragraph_break

        chunk = normalized_text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = end - chunk_overlap

        # Avoid beginning a chunk inside paragraph-separator whitespace.
        while (
            next_start < text_length
            and normalized_text[next_start].isspace()
        ):
            next_start += 1

        # Defensive protection against an accidental infinite loop.
        if next_start <= start:
            next_start = end

        start = next_start

    return chunks