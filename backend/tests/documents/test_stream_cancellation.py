from datetime import timedelta

import pytest

from app.documents.stream_cancellation import (
    StreamCancellationRegistry,
    StreamNotFoundError,
    StreamOwnershipError,
)


def test_register_creates_active_stream() -> None:
    registry = StreamCancellationRegistry()

    state = registry.register(
        organization_id="organization-1",
        conversation_id="conversation-1",
    )

    assert state.stream_id
    assert state.organization_id == "organization-1"
    assert state.conversation_id == "conversation-1"
    assert state.is_active is True
    assert state.is_cancelled is False
    assert state.is_completed is False


def test_register_supports_one_off_stream() -> None:
    registry = StreamCancellationRegistry()

    state = registry.register(
        organization_id="organization-1",
    )

    assert state.conversation_id is None
    assert state.is_active is True


def test_register_accepts_explicit_stream_id() -> None:
    registry = StreamCancellationRegistry()

    state = registry.register(
        organization_id="organization-1",
        stream_id="stream-1",
    )

    assert state.stream_id == "stream-1"


def test_duplicate_stream_id_is_rejected() -> None:
    registry = StreamCancellationRegistry()

    registry.register(
        organization_id="organization-1",
        stream_id="stream-1",
    )

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        registry.register(
            organization_id="organization-1",
            stream_id="stream-1",
        )


def test_cancel_marks_stream_cancelled() -> None:
    registry = StreamCancellationRegistry()

    state = registry.register(
        organization_id="organization-1",
    )

    cancelled = registry.cancel(
        stream_id=state.stream_id,
        organization_id="organization-1",
    )

    assert cancelled.is_cancelled is True
    assert cancelled.is_active is False
    assert registry.is_cancelled(
        stream_id=state.stream_id,
        organization_id="organization-1",
    ) is True


def test_cancel_is_idempotent() -> None:
    registry = StreamCancellationRegistry()

    state = registry.register(
        organization_id="organization-1",
    )

    first = registry.cancel(
        stream_id=state.stream_id,
        organization_id="organization-1",
    )

    first_cancelled_at = first.cancelled_at

    second = registry.cancel(
        stream_id=state.stream_id,
        organization_id="organization-1",
    )

    assert second.cancelled_at == first_cancelled_at


def test_completed_stream_is_not_changed_to_cancelled() -> None:
    registry = StreamCancellationRegistry()

    state = registry.register(
        organization_id="organization-1",
    )

    completed = registry.mark_completed(
        stream_id=state.stream_id,
        organization_id="organization-1",
    )

    cancelled = registry.cancel(
        stream_id=state.stream_id,
        organization_id="organization-1",
    )

    assert completed.is_completed is True
    assert cancelled.is_completed is True
    assert cancelled.is_cancelled is False


def test_cancel_unknown_stream_raises_not_found() -> None:
    registry = StreamCancellationRegistry()

    with pytest.raises(
        StreamNotFoundError,
        match="not found",
    ):
        registry.cancel(
            stream_id="missing-stream",
            organization_id="organization-1",
        )


def test_stream_is_organization_scoped() -> None:
    registry = StreamCancellationRegistry()

    state = registry.register(
        organization_id="organization-1",
    )

    with pytest.raises(
        StreamOwnershipError,
        match="not found",
    ):
        registry.cancel(
            stream_id=state.stream_id,
            organization_id="organization-2",
        )


def test_mark_completed_marks_active_stream() -> None:
    registry = StreamCancellationRegistry()

    state = registry.register(
        organization_id="organization-1",
    )

    completed = registry.mark_completed(
        stream_id=state.stream_id,
        organization_id="organization-1",
    )

    assert completed.is_completed is True
    assert completed.is_active is False
    assert completed.is_cancelled is False


def test_cancelled_stream_is_not_changed_to_completed() -> None:
    registry = StreamCancellationRegistry()

    state = registry.register(
        organization_id="organization-1",
    )

    registry.cancel(
        stream_id=state.stream_id,
        organization_id="organization-1",
    )

    completed = registry.mark_completed(
        stream_id=state.stream_id,
        organization_id="organization-1",
    )

    assert completed.is_cancelled is True
    assert completed.is_completed is False


def test_remove_deletes_stream() -> None:
    registry = StreamCancellationRegistry()

    state = registry.register(
        organization_id="organization-1",
    )

    registry.remove(
        stream_id=state.stream_id,
        organization_id="organization-1",
    )

    with pytest.raises(StreamNotFoundError):
        registry.get(
            stream_id=state.stream_id,
            organization_id="organization-1",
        )


def test_cleanup_removes_expired_streams() -> None:
    registry = StreamCancellationRegistry(
        ttl_seconds=1,
    )

    state = registry.register(
        organization_id="organization-1",
    )

    state.created_at = state.created_at - timedelta(
        seconds=2
    )

    removed_count = registry.cleanup_expired()

    assert removed_count == 1

    with pytest.raises(StreamNotFoundError):
        registry.get(
            stream_id=state.stream_id,
            organization_id="organization-1",
        )


@pytest.mark.parametrize(
    "organization_id",
    [
        "",
        "   ",
    ],
)
def test_register_rejects_empty_organization_id(
    organization_id: str,
) -> None:
    registry = StreamCancellationRegistry()

    with pytest.raises(
        ValueError,
        match="organization_id must not be empty",
    ):
        registry.register(
            organization_id=organization_id,
        )


def test_register_rejects_empty_conversation_id() -> None:
    registry = StreamCancellationRegistry()

    with pytest.raises(
        ValueError,
        match="conversation_id must not be empty",
    ):
        registry.register(
            organization_id="organization-1",
            conversation_id="   ",
        )


def test_registry_rejects_invalid_ttl() -> None:
    with pytest.raises(
        ValueError,
        match="TTL must be at least 1",
    ):
        StreamCancellationRegistry(
            ttl_seconds=0,
        )


def test_clear_removes_all_streams() -> None:
    registry = StreamCancellationRegistry()

    first = registry.register(
        organization_id="organization-1",
    )

    second = registry.register(
        organization_id="organization-1",
    )

    registry.clear()

    for stream_id in [
        first.stream_id,
        second.stream_id,
    ]:
        with pytest.raises(StreamNotFoundError):
            registry.get(
                stream_id=stream_id,
                organization_id="organization-1",
            )
