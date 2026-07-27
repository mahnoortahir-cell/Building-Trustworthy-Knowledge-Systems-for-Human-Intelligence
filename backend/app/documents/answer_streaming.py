import json
from collections.abc import Callable, Iterator, Sequence
from typing import Any

from app.documents.rag import AnswerCitation


def encode_sse(
    event: str,
    data: dict[str, Any],
) -> str:
    """
    Encode one Server-Sent Events message.

    Compact JSON keeps streaming payloads small. ensure_ascii=False preserves
    multilingual NoorOS output.
    """

    normalized_event = event.strip()

    if not normalized_event:
        raise ValueError("SSE event name must not be empty.")

    if "\n" in normalized_event or "\r" in normalized_event:
        raise ValueError(
            "SSE event name must not contain line breaks."
        )

    payload = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return f"event: {normalized_event}\ndata: {payload}\n\n"


def citation_to_payload(
    citation: AnswerCitation,
) -> dict[str, Any]:
    return {
        "chunk_id": citation.chunk_id,
        "document_id": citation.document_id,
        "document_version_id": citation.document_version_id,
        "chunk_index": citation.chunk_index,
        "content": citation.content,
        "score": citation.score,
    }


def _close_answer_chunks(
    answer_chunks: Iterator[str],
) -> None:
    close = getattr(answer_chunks, "close", None)

    if callable(close):
        close()


def stream_answer_sse_events(
    *,
    answer_chunks: Iterator[str],
    citations: Sequence[AnswerCitation],
    conversation_id: str | None,
    complete_answer: Callable[[str], str | None],
    stream_id: str | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    cancel_answer: Callable[[], None] | None = None,
) -> Iterator[str]:
    """
    Convert an answer stream into structured SSE events.

    complete_answer is called only after the provider stream finishes
    successfully. It is never called when generation is cancelled.
    """

    cancellation_check = is_cancelled or (lambda: False)
    cancellation_callback_called = False
    complete_text_parts: list[str] = []

    def emit_cancelled() -> str:
        nonlocal cancellation_callback_called

        try:
            _close_answer_chunks(answer_chunks)
        finally:
            if (
                cancel_answer is not None
                and not cancellation_callback_called
            ):
                cancellation_callback_called = True
                cancel_answer()

        return encode_sse(
            "cancelled",
            {
                "stream_id": stream_id,
                "conversation_id": conversation_id,
                "answer": "".join(complete_text_parts),
            },
        )

    start_payload: dict[str, Any] = {
        "conversation_id": conversation_id,
    }

    if stream_id is not None:
        start_payload["stream_id"] = stream_id

    yield encode_sse(
        "start",
        start_payload,
    )

    if cancellation_check():
        yield emit_cancelled()
        return

    yield encode_sse(
        "citations",
        {
            "citations": [
                citation_to_payload(citation)
                for citation in citations
            ],
        },
    )

    if cancellation_check():
        yield emit_cancelled()
        return

    for chunk in answer_chunks:
        if cancellation_check():
            yield emit_cancelled()
            return

        if not isinstance(chunk, str):
            raise TypeError(
                "The answer stream produced a non-text chunk."
            )

        if not chunk:
            continue

        complete_text_parts.append(chunk)

        yield encode_sse(
            "token",
            {
                "text": chunk,
            },
        )

        if cancellation_check():
            yield emit_cancelled()
            return

    if cancellation_check():
        yield emit_cancelled()
        return

    complete_text = "".join(complete_text_parts).strip()

    if not complete_text:
        raise ValueError(
            "The answer stream produced an empty response."
        )

    # Final boundary before message persistence.
    if cancellation_check():
        yield emit_cancelled()
        return

    assistant_message_id = complete_answer(complete_text)

    yield encode_sse(
        "complete",
        {
            "conversation_id": conversation_id,
            "assistant_message_id": assistant_message_id,
            "answer": complete_text,
        },
    )
