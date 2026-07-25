import pytest

from app.documents.chunking import chunk_text, normalize_text


def test_normalize_text_removes_extra_whitespace() -> None:
    text = """
    First    paragraph with extra spaces.

    Second paragraph
    with additional text.
    """

    result = normalize_text(text)

    assert result == (
        "First paragraph with extra spaces.\n\n"
        "Second paragraph\n\n"
        "with additional text."
    )


def test_chunk_text_returns_empty_list_for_blank_text() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\n   ") == []


def test_short_text_returns_one_chunk() -> None:
    text = "This document contains a short paragraph."

    chunks = chunk_text(
        text,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert chunks == [text]


def test_long_text_is_split_into_multiple_chunks() -> None:
    text = "A" * 250

    chunks = chunk_text(
        text,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) == 3
    assert all(len(chunk) <= 100 for chunk in chunks)


def test_chunks_include_overlap() -> None:
    text = "".join(str(index % 10) for index in range(200))

    chunks = chunk_text(
        text,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert chunks[0][-20:] == chunks[1][:20]


def test_chunking_prefers_paragraph_boundaries() -> None:
    first_paragraph = "A" * 60
    second_paragraph = "B" * 60

    text = f"{first_paragraph}\n\n{second_paragraph}"

    chunks = chunk_text(
        text,
        chunk_size=100,
        chunk_overlap=10,
    )

    assert chunks[0] == first_paragraph
    assert second_paragraph in chunks[-1]


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap", "expected_message"),
    [
        (0, 0, "chunk_size must be greater than zero"),
        (-1, 0, "chunk_size must be greater than zero"),
        (100, -1, "chunk_overlap cannot be negative"),
        (100, 100, "chunk_overlap must be smaller than chunk_size"),
        (100, 150, "chunk_overlap must be smaller than chunk_size"),
    ],
)
def test_invalid_chunk_settings_raise_value_error(
    chunk_size: int,
    chunk_overlap: int,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        chunk_text(
            "Test text",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )