import json
from collections.abc import Iterator

import pytest

from app.documents.answer_streaming import (
    citation_to_payload,
    encode_sse,
    stream_answer_sse_events,
)
from app.documents.rag import AnswerCitation


def citation() -> AnswerCitation:
    return AnswerCitation(
        chunk_id="chunk-1",
        document_id="document-1",
        document_version_id="version-1",
        chunk_index=2,
        content="NoorOS is a document platform.",
        score=0.97,
    )


def parse_sse_event(
    encoded_event: str,
) -> tuple[str, dict[str, object]]:
    lines = encoded_event.strip().splitlines()

    event_name = lines[0].removeprefix("event: ")
    data = json.loads(
        lines[1].removeprefix("data: ")
    )

    return event_name, data


def test_encode_sse_creates_valid_event() -> None:
    encoded = encode_sse(
        "token",
        {
            "text": "NoorOS",
        },
    )

    assert encoded.endswith("\n\n")

    event_name, data = parse_sse_event(encoded)

    assert event_name == "token"
    assert data == {
        "text": "NoorOS",
    }


def test_encode_sse_preserves_unicode() -> None:
    encoded = encode_sse(
        "token",
        {
            "text": "نور",
        },
    )

    assert "نور" in encoded
    assert "\\u" not in encoded


@pytest.mark.parametrize(
    "event_name",
    [
        "",
        "   ",
        "invalid\nevent",
        "invalid\revent",
    ],
)
def test_encode_sse_rejects_invalid_event_name(
    event_name: str,
) -> None:
    with pytest.raises(ValueError):
        encode_sse(
            event_name,
            {
                "value": "test",
            },
        )


def test_citation_to_payload() -> None:
    payload = citation_to_payload(citation())

    assert payload == {
        "chunk_id": "chunk-1",
        "document_id": "document-1",
        "document_version_id": "version-1",
        "chunk_index": 2,
        "content": "NoorOS is a document platform.",
        "score": 0.97,
    }


def test_stream_answer_sse_event_order() -> None:
    completed_answers: list[str] = []

    def complete_answer(
        answer: str,
    ) -> str:
        completed_answers.append(answer)
        return "message-1"

    events = list(
        stream_answer_sse_events(
            answer_chunks=iter(
                [
                    "Noor",
                    "OS",
                ]
            ),
            citations=[citation()],
            conversation_id="conversation-1",
            complete_answer=complete_answer,
        )
    )

    parsed = [
        parse_sse_event(event)
        for event in events
    ]

    assert [
        event_name
        for event_name, _ in parsed
    ] == [
        "start",
        "citations",
        "token",
        "token",
        "complete",
    ]

    assert parsed[0][1] == {
        "conversation_id": "conversation-1",
    }

    assert parsed[1][1]["citations"] == [
        citation_to_payload(citation())
    ]

    assert parsed[2][1] == {
        "text": "Noor",
    }

    assert parsed[3][1] == {
        "text": "OS",
    }

    assert parsed[4][1] == {
        "conversation_id": "conversation-1",
        "assistant_message_id": "message-1",
        "answer": "NoorOS",
    }

    assert completed_answers == [
        "NoorOS",
    ]


def test_completion_callback_runs_after_stream_finishes() -> None:
    execution_order: list[str] = []

    def chunks() -> Iterator[str]:
        execution_order.append("chunk-one")
        yield "One"

        execution_order.append("chunk-two")
        yield "Two"

    def complete_answer(
        answer: str,
    ) -> str:
        execution_order.append(
            f"complete:{answer}"
        )
        return "message-1"

    list(
        stream_answer_sse_events(
            answer_chunks=chunks(),
            citations=[],
            conversation_id="conversation-1",
            complete_answer=complete_answer,
        )
    )

    assert execution_order == [
        "chunk-one",
        "chunk-two",
        "complete:OneTwo",
    ]


def test_empty_chunks_are_ignored() -> None:
    completed_answers: list[str] = []

    events = list(
        stream_answer_sse_events(
            answer_chunks=iter(
                [
                    "",
                    "Answer",
                    "",
                ]
            ),
            citations=[],
            conversation_id=None,
            complete_answer=lambda answer: (
                completed_answers.append(answer)
                or None
            ),
        )
    )

    parsed = [
        parse_sse_event(event)
        for event in events
    ]

    assert [
        event_name
        for event_name, _ in parsed
    ] == [
        "start",
        "citations",
        "token",
        "complete",
    ]

    assert completed_answers == [
        "Answer",
    ]


def test_empty_stream_does_not_call_completion() -> None:
    completion_called = False

    def complete_answer(
        answer: str,
    ) -> None:
        nonlocal completion_called
        completion_called = True

    generator = stream_answer_sse_events(
        answer_chunks=iter(
            [
                "",
                "",
            ]
        ),
        citations=[],
        conversation_id=None,
        complete_answer=complete_answer,
    )

    with pytest.raises(
        ValueError,
        match="empty response",
    ):
        list(generator)

    assert completion_called is False


def test_invalid_chunk_does_not_call_completion() -> None:
    completion_called = False

    def complete_answer(
        answer: str,
    ) -> None:
        nonlocal completion_called
        completion_called = True

    generator = stream_answer_sse_events(
        answer_chunks=iter(
            [
                "partial",
                123,
            ]
        ),  # type: ignore[arg-type]
        citations=[],
        conversation_id=None,
        complete_answer=complete_answer,
    )

    with pytest.raises(
        TypeError,
        match="non-text chunk",
    ):
        list(generator)

    assert completion_called is False


def test_one_off_stream_has_null_message_metadata() -> None:
    events = list(
        stream_answer_sse_events(
            answer_chunks=iter(["Answer"]),
            citations=[],
            conversation_id=None,
            complete_answer=lambda answer: None,
        )
    )

    complete_event = parse_sse_event(
        events[-1]
    )

    assert complete_event == (
        "complete",
        {
            "conversation_id": None,
            "assistant_message_id": None,
            "answer": "Answer",
        },
    )
