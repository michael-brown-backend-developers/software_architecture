"""Events that must be handled, kept until they have been.

An event goes into the outbox in the same transaction as the change it
describes, so it is kept if, and only if, the change is. A worker - another
process - handles it afterwards, and tries again later if a handler fails.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Message:
    """An event in the outbox, and how far its handling has got."""

    id: str
    event: object
    attempts: int
    handled: frozenset[str]


class Outbox(Protocol):
    """Events waiting to be handled."""

    def add(self, event: object) -> None:
        """Keep an event, to be handled once this transaction commits."""
        ...

    def next_due(self, now: datetime) -> Message | None:
        """Claim the next message due by ``now``, or None if none is.

        No other worker can claim it until this transaction ends.
        """
        ...

    def handled(self, message_id: str, handler: str) -> None:
        """Record that ``handler`` has handled this message."""
        ...

    def done(self, message_id: str) -> None:
        """Every handler has handled this message."""
        ...

    def failed(
        self, message_id: str, error: str, retry_at: datetime | None
    ) -> None:
        """A handler failed. Try again at ``retry_at``, or, if None, never."""
        ...
