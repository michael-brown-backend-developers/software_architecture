"""StageDoor's own ports, kept in memory.

These are real adapters, as much as the ones for PostgreSQL: they keep the
same promises, checked by the same contract tests. They forget everything
when the program stops, which makes them right for the tests, and for
trying StageDoor out without a database.
"""

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Self
from uuid import uuid4

from stagedoor.application.ports import Message
from stagedoor.domain.capacity import CAPACITY, places_wanted
from stagedoor.domain.exceptions import (
    BookingNotFoundError,
    NotEnoughPlacesError,
)
from stagedoor.domain.models import Booking, BookingLine


class InMemoryBookingRepository:
    """Bookings, kept in a dictionary for as long as the test runs.

    It hands out copies, as a database would, so a test cannot change a
    booking without saving it.
    """

    def __init__(self) -> None:
        self.bookings: dict[str, Booking] = {}

    def add(self, booking: Booking) -> None:
        self.bookings[booking.id] = replace(booking)

    def get(self, booking_id: str) -> Booking:
        try:
            return replace(self.bookings[booking_id])
        except KeyError:
            raise BookingNotFoundError(booking_id) from None

    def save(self, booking: Booking) -> None:
        self.bookings[booking.id] = replace(booking)


class InMemoryPlaceRepository:
    """The places left for every performance, in a dictionary."""

    def __init__(self) -> None:
        self.left: dict[str, int] = dict(CAPACITY)

    def take(self, lines: Sequence[BookingLine]) -> None:
        wanted = places_wanted(lines)
        for performance, quantity in wanted.items():
            available = self.left.get(performance, 0)
            if available < quantity:
                raise NotEnoughPlacesError(performance, quantity, available)
        for performance, quantity in wanted.items():
            self.left[performance] -= quantity

    def give_back(self, lines: Sequence[BookingLine]) -> None:
        for performance, quantity in places_wanted(lines).items():
            self.left[performance] += quantity


@dataclass
class OutboxEntry:
    """An event in the in-memory outbox, and how far it has got."""

    event: object
    due_at: datetime = datetime.min.replace(tzinfo=UTC)
    attempts: int = 0
    status: str = "pending"
    last_error: str | None = None
    handled: set[str] = field(default_factory=set)


class InMemoryOutbox:
    """Events waiting to be handled, in a dictionary, in the order added."""

    def __init__(self) -> None:
        self.entries: dict[str, OutboxEntry] = {}

    def add(self, event: object) -> None:
        self.entries[uuid4().hex] = OutboxEntry(event)

    def next_due(self, now: datetime) -> Message | None:
        for message_id, entry in self.entries.items():
            if entry.status == "pending" and entry.due_at <= now:
                return Message(
                    id=message_id,
                    event=entry.event,
                    attempts=entry.attempts,
                    handled=frozenset(entry.handled),
                )
        return None

    def handled(self, message_id: str, handler: str) -> None:
        self.entries[message_id].handled.add(handler)

    def done(self, message_id: str) -> None:
        self.entries[message_id].status = "done"

    def failed(
        self, message_id: str, error: str, retry_at: datetime | None
    ) -> None:
        entry = self.entries[message_id]
        entry.attempts += 1
        entry.last_error = error
        if retry_at is None:
            entry.status = "dead"
        else:
            entry.due_at = retry_at


class InMemoryUnitOfWork:
    """A transaction over the in-memory repositories.

    It remembers what they held when it started, or last committed, and
    puts that back unless it is committed.
    """

    def __init__(
        self,
        bookings: InMemoryBookingRepository | None = None,
        places: InMemoryPlaceRepository | None = None,
    ) -> None:
        self.bookings = bookings or InMemoryBookingRepository()
        self.places = places or InMemoryPlaceRepository()
        self.outbox = InMemoryOutbox()

    def __enter__(self) -> Self:
        self.commit()
        return self

    def __exit__(self, *exc: object) -> None:
        self.rollback()

    def commit(self) -> None:
        self._kept = (
            dict(self.bookings.bookings),
            dict(self.places.left),
            deepcopy(self.outbox.entries),
        )

    def rollback(self) -> None:
        bookings, left, entries = self._kept
        self.bookings.bookings.clear()
        self.bookings.bookings.update(bookings)
        self.places.left.clear()
        self.places.left.update(left)
        self.outbox.entries.clear()
        self.outbox.entries.update(deepcopy(entries))
