"""Simple, honest stand-ins for StageDoor's own collaborators.

Each one behaves like the real thing in the ways a test cares about, and
keeps a record of what was asked of it, so a test can check what happened
rather than how.
"""

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Self
from uuid import uuid4

from stagedoor.capacity import CAPACITY, places_wanted
from stagedoor.exceptions import (
    BookingNotFoundError,
    MissingPaymentTokenError,
    NotEnoughPlacesError,
    PaymentFailedError,
)
from stagedoor.models import Booking, BookingLine, PaymentStatus
from stagedoor.outbox import Message
from stagedoor.payments.base import PaymentResult

DECLINED = "declined"


class FakePaymentMethod:
    """A way of paying that keeps a ledger, and declines one token."""

    def __init__(self) -> None:
        self.charges: list[tuple[str, Decimal]] = []
        self.refunds: list[tuple[str, Decimal]] = []

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> PaymentResult:
        if token is None:
            raise MissingPaymentTokenError("fake")
        if token == DECLINED:
            raise PaymentFailedError("The fake card was declined.")
        self.charges.append((booking_id, amount))
        return PaymentResult(
            reference=f"fake-{booking_id}", status=PaymentStatus.PAID
        )

    def refund(self, reference: str, amount: Decimal) -> None:
        self.refunds.append((reference, amount))

    def fee(self, amount: Decimal) -> Decimal:
        return Decimal("0.00")

    def describe(self, booking: Booking) -> str:
        return "Paid with a fake."


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


class FailingRepository(InMemoryBookingRepository):
    """A repository whose database has run out of room."""

    def add(self, booking: Booking) -> None:
        raise OSError("No space left on device")


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


def mail_about(booking_id: str, folder: Path) -> str:
    """The email about a booking that the stand-in provider delivered.

    Empty if there is none.
    """
    for path in sorted(folder.glob("msg_*.txt")):
        text = path.read_text(encoding="utf-8")
        if f"Subject: Your StageDoor booking {booking_id}\n" in text:
            return text
    return ""


def no_sleep(seconds: float) -> None:
    """Wait for no time at all."""
