from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import uuid4


DEFAULT_STREAM_TTL_SECONDS = 3600


class StreamNotFoundError(LookupError):
    """Raised when a stream is not registered or has expired."""


class StreamOwnershipError(LookupError):
    """
    Raised when a stream does not belong to the requested organisation.

    It intentionally behaves like a not-found error so callers do not expose
    cross-organisation stream existence.
    """


@dataclass(slots=True)
class StreamCancellationState:
    stream_id: str
    organization_id: str
    conversation_id: str | None
    created_at: datetime
    cancelled_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled_at is not None

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    @property
    def is_active(self) -> bool:
        return not self.is_cancelled and not self.is_completed


class StreamCancellationRegistry:
    """
    Thread-safe in-memory registry for active answer streams.

    This implementation is suitable for a single backend process. A future
    production hardening phase can replace it with Redis while preserving the
    same public interface.
    """

    def __init__(
        self,
        *,
        ttl_seconds: int = DEFAULT_STREAM_TTL_SECONDS,
    ) -> None:
        if ttl_seconds < 1:
            raise ValueError(
                "Stream cancellation TTL must be at least 1 second."
            )

        self._ttl = timedelta(seconds=ttl_seconds)
        self._states: dict[str, StreamCancellationState] = {}
        self._lock = RLock()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    def _is_expired(
        self,
        state: StreamCancellationState,
        *,
        now: datetime,
    ) -> bool:
        reference_time = (
            state.completed_at
            or state.cancelled_at
            or state.created_at
        )

        return now - reference_time >= self._ttl

    def _remove_expired_locked(
        self,
        *,
        now: datetime,
    ) -> int:
        expired_ids = [
            stream_id
            for stream_id, state in self._states.items()
            if self._is_expired(state, now=now)
        ]

        for stream_id in expired_ids:
            self._states.pop(stream_id, None)

        return len(expired_ids)

    def cleanup_expired(self) -> int:
        with self._lock:
            return self._remove_expired_locked(
                now=self._utc_now(),
            )

    def register(
        self,
        *,
        organization_id: str,
        conversation_id: str | None = None,
        stream_id: str | None = None,
    ) -> StreamCancellationState:
        normalized_organization_id = organization_id.strip()

        if not normalized_organization_id:
            raise ValueError(
                "organization_id must not be empty."
            )

        normalized_conversation_id = (
            conversation_id.strip()
            if conversation_id is not None
            else None
        )

        if conversation_id is not None and not normalized_conversation_id:
            raise ValueError(
                "conversation_id must not be empty when supplied."
            )

        normalized_stream_id = (
            stream_id.strip()
            if stream_id is not None
            else str(uuid4())
        )

        if not normalized_stream_id:
            raise ValueError(
                "stream_id must not be empty."
            )

        with self._lock:
            now = self._utc_now()
            self._remove_expired_locked(now=now)

            if normalized_stream_id in self._states:
                raise ValueError(
                    "A stream with this stream_id is already registered."
                )

            state = StreamCancellationState(
                stream_id=normalized_stream_id,
                organization_id=normalized_organization_id,
                conversation_id=normalized_conversation_id,
                created_at=now,
            )

            self._states[state.stream_id] = state

            return state

    def get(
        self,
        *,
        stream_id: str,
        organization_id: str,
    ) -> StreamCancellationState:
        normalized_stream_id = stream_id.strip()
        normalized_organization_id = organization_id.strip()

        if not normalized_stream_id:
            raise StreamNotFoundError(
                "Answer stream was not found."
            )

        if not normalized_organization_id:
            raise StreamNotFoundError(
                "Answer stream was not found."
            )

        with self._lock:
            now = self._utc_now()
            self._remove_expired_locked(now=now)

            state = self._states.get(normalized_stream_id)

            if state is None:
                raise StreamNotFoundError(
                    "Answer stream was not found."
                )

            if state.organization_id != normalized_organization_id:
                raise StreamOwnershipError(
                    "Answer stream was not found."
                )

            return state

    def cancel(
        self,
        *,
        stream_id: str,
        organization_id: str,
    ) -> StreamCancellationState:
        with self._lock:
            state = self.get(
                stream_id=stream_id,
                organization_id=organization_id,
            )

            # Cancellation is intentionally idempotent.
            if state.cancelled_at is None and state.completed_at is None:
                state.cancelled_at = self._utc_now()

            return state

    def mark_completed(
        self,
        *,
        stream_id: str,
        organization_id: str,
    ) -> StreamCancellationState:
        with self._lock:
            state = self.get(
                stream_id=stream_id,
                organization_id=organization_id,
            )

            if state.completed_at is None and state.cancelled_at is None:
                state.completed_at = self._utc_now()

            return state

    def is_cancelled(
        self,
        *,
        stream_id: str,
        organization_id: str,
    ) -> bool:
        state = self.get(
            stream_id=stream_id,
            organization_id=organization_id,
        )

        return state.is_cancelled

    def remove(
        self,
        *,
        stream_id: str,
        organization_id: str,
    ) -> None:
        with self._lock:
            self.get(
                stream_id=stream_id,
                organization_id=organization_id,
            )

            self._states.pop(stream_id.strip(), None)

    def clear(self) -> None:
        """
        Clear all states.

        Intended mainly for tests and controlled application shutdown.
        """

        with self._lock:
            self._states.clear()


stream_cancellation_registry = StreamCancellationRegistry()
