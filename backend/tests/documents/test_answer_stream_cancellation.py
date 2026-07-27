import json
from collections.abc import Iterator

from app.documents.answer_streaming import (
    stream_answer_sse_events,
)


def parse_sse_event(
    encoded: str,
) -> tuple[str, dict[str, object]]:
    event_name = ""
    data = ""

    for line in encoded.strip().splitlines():
        if line.startswith("event: "):
            event_name = line.removeprefix("event: ")

        elif line.startswith("data: "):
            data = line.removeprefix("data: ")

    return event_name, json.loads(data)


def test_stream_id_is_added_to_start_event() -> None:
    events = list(
        stream_answer_sse_events(
            answer_chunks=iter(["Answer"]),
            citations=[],
            conversation_id="conversation-1",
            complete_answer=lambda answer: "message-1",
            stream_id="stream-1",
        )
    )

    event_name, payload = parse_sse_event(
        events[0]
    )

    assert event_name == "start"
    assert payload == {
        "conversation_id": "conversation-1",
        "stream_id": "stream-1",
    }


def test_existing_start_payload_is_preserved_without_stream_id() -> None:
    events = list(
        stream_answer_sse_events(
            answer_chunks=iter(["Answer"]),
            citations=[],
            conversation_id="conversation-1",
            complete_answer=lambda answer: "message-1",
        )
    )

    event_name, payload = parse_sse_event(
        events[0]
    )

    assert event_name == "start"
    assert payload == {
        "conversation_id": "conversation-1",
    }


def test_cancel_before_generation_stops_stream() -> None:
    completion_called = False
    cancellation_callback_called = False

    def complete_answer(
        answer: str,
    ) -> str:
        nonlocal completion_called
        completion_called = True
        return "message-1"

    def cancel_answer() -> None:
        nonlocal cancellation_callback_called
        cancellation_callback_called = True

    events = list(
        stream_answer_sse_events(
            answer_chunks=iter(["Must not emit"]),
            citations=[],
            conversation_id="conversation-1",
            complete_answer=complete_answer,
            stream_id="stream-1",
            is_cancelled=lambda: True,
            cancel_answer=cancel_answer,
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
        "cancelled",
    ]

    assert parsed[-1][1] == {
        "stream_id": "stream-1",
        "conversation_id": "conversation-1",
        "answer": "",
    }

    assert completion_called is False
    assert cancellation_callback_called is True


def test_cancel_after_first_token_does_not_complete() -> None:
    completion_called = False
    cancellation_callback_count = 0
    checks = 0

    def is_cancelled() -> bool:
        nonlocal checks
        checks += 1

        # Checks occur:
        # 1. after start
        # 2. after citations
        # 3. before first chunk
        # 4. after first token
        return checks >= 4

    def complete_answer(
        answer: str,
    ) -> str:
        nonlocal completion_called
        completion_called = True
        return "message-1"

    def cancel_answer() -> None:
        nonlocal cancellation_callback_count
        cancellation_callback_count += 1

    events = list(
        stream_answer_sse_events(
            answer_chunks=iter(
                [
                    "First",
                    "Second",
                ]
            ),
            citations=[],
            conversation_id="conversation-1",
            complete_answer=complete_answer,
            stream_id="stream-1",
            is_cancelled=is_cancelled,
            cancel_answer=cancel_answer,
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
        "cancelled",
    ]

    assert parsed[2][1] == {
        "text": "First",
    }

    assert parsed[3][1] == {
        "stream_id": "stream-1",
        "conversation_id": "conversation-1",
        "answer": "First",
    }

    assert completion_called is False
    assert cancellation_callback_count == 1


def test_cancelled_stream_closes_underlying_iterator() -> None:
    closed = False

    def chunks() -> Iterator[str]:
        nonlocal closed

        try:
            yield "First"
            yield "Second"
        finally:
            closed = True

    checks = 0

    def is_cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 4

    events = list(
        stream_answer_sse_events(
            answer_chunks=chunks(),
            citations=[],
            conversation_id=None,
            complete_answer=lambda answer: None,
            stream_id="stream-1",
            is_cancelled=is_cancelled,
        )
    )

    assert parse_sse_event(
        events[-1]
    )[0] == "cancelled"

    assert closed is True


def test_normal_stream_still_completes() -> None:
    completed_answers: list[str] = []

    events = list(
        stream_answer_sse_events(
            answer_chunks=iter(
                [
                    "Noor",
                    "OS",
                ]
            ),
            citations=[],
            conversation_id="conversation-1",
            complete_answer=lambda answer: (
                completed_answers.append(answer)
                or "message-1"
            ),
            stream_id="stream-1",
            is_cancelled=lambda: False,
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

    assert parsed[-1][1] == {
        "conversation_id": "conversation-1",
        "assistant_message_id": "message-1",
        "answer": "NoorOS",
    }

    assert completed_answers == [
        "NoorOS",
    ]


def test_cancel_callback_runs_only_once() -> None:
    cancellation_callback_count = 0

    def cancel_answer() -> None:
        nonlocal cancellation_callback_count
        cancellation_callback_count += 1

    events = list(
        stream_answer_sse_events(
            answer_chunks=iter(["Answer"]),
            citations=[],
            conversation_id=None,
            complete_answer=lambda answer: None,
            stream_id="stream-1",
            is_cancelled=lambda: True,
            cancel_answer=cancel_answer,
        )
    )

    assert parse_sse_event(
        events[-1]
    )[0] == "cancelled"

    assert cancellation_callback_count == 1
