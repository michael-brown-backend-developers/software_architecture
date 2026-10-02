"""Everything StageDoor's application needs from the world outside it.

Each of these is a port: a Protocol, in StageDoor's own words, that an
adapter plugs into. The application depends on these, and on the domain,
and on nothing else of ours. Which adapter plugs into each port is decided
in bootstrap.py.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol, Self

from stagedoor.domain.exceptions import UnknownPaymentMethodError
from stagedoor.domain.models import Booking, BookingLine, PaymentStatus

# Taking payment.


@dataclass(frozen=True)
class PaymentResult:
    """What happened when we took a payment."""

    reference: str
    status: PaymentStatus


class PaymentMethod(Protocol):
    """A way for a customer to pay."""

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> PaymentResult:
        """Take ``amount`` from the customer.

        Raise PaymentFailedError, with a reason the customer can read, if
        the payment does not go through.
        """
        ...

    def refund(self, reference: str, amount: Decimal) -> None:
        """Give back ``amount`` of the payment with this ``reference``."""
        ...

    def fee(self, amount: Decimal) -> Decimal:
        """What the provider charges us for taking ``amount``."""
        ...

    def describe(self, booking: Booking) -> str:
        """Tell the customer, in their confirmation, how they paid."""
        ...


def get_payment_method(
    name: str, payment_methods: Mapping[str, PaymentMethod]
) -> PaymentMethod:
    """The payment method a customer chose, by name, if it is switched on."""
    try:
        return payment_methods[name]
    except KeyError:
        raise UnknownPaymentMethodError(name) from None


# Issuing tickets.


@dataclass(frozen=True)
class FulfilmentResult:
    """What issuing a booking's tickets produced."""

    hold_references: tuple[str, ...]
    wallet_pass: str | None
    tracking_number: str | None
    invoice_number: str


class Fulfilment(Protocol):
    """Everything that happens to a booking once it is paid for."""

    def fulfil(self, booking: Booking) -> FulfilmentResult:
        """Hold the seats, get the tickets out, and invoice the booking.

        Raise FulfilmentError if the tickets cannot be issued.
        """
        ...

    def release(self, booking: Booking) -> None:
        """Give a cancelled booking's seats back to the venue."""
        ...


# Telling customers.


class Mailer(Protocol):
    """Sends customers their email."""

    def send_confirmation(
        self, booking: Booking, payment_method: PaymentMethod
    ) -> None:
        """Send the customer a confirmation of their booking."""
        ...


# Keeping bookings, places and events.


class BookingRepository(Protocol):
    """Every booking StageDoor has made."""

    def add(self, booking: Booking) -> None:
        """Keep a new booking."""
        ...

    def get(self, booking_id: str) -> Booking:
        """The booking with this ID. Raise BookingNotFoundError if none."""
        ...

    def save(self, booking: Booking) -> None:
        """Keep the changes to a booking that was already added."""
        ...


class PlaceRepository(Protocol):
    """The places left for every performance."""

    def take(self, lines: Sequence[BookingLine]) -> None:
        """Take the places off sale.

        Raise NotEnoughPlacesError if any performance does not have room.
        """
        ...

    def give_back(self, lines: Sequence[BookingLine]) -> None:
        """Put the places back on sale."""
        ...


@dataclass(frozen=True)
class Message:
    """An event in the outbox, and how far its handling has got."""

    id: str
    event: object
    attempts: int
    handled: frozenset[str]


class Outbox(Protocol):
    """Events waiting to be handled.

    An event goes in in the same transaction as the change it describes, so
    it is kept if, and only if, the change is.
    """

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


class UnitOfWork(Protocol):
    """One transaction's worth of changes to bookings, places and events.

    Nothing is kept until commit() is called. Leave the with block without
    committing, and every change is undone.
    """

    @property
    def bookings(self) -> BookingRepository: ...

    @property
    def places(self) -> PlaceRepository: ...

    @property
    def outbox(self) -> Outbox: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, *exc: object) -> None:
        """Undo anything that was not committed."""
        ...

    def commit(self) -> None:
        """Keep every change made so far."""
        ...

    def rollback(self) -> None:
        """Undo every change since the last commit."""
        ...
