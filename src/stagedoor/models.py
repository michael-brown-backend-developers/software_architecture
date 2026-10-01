"""The things StageDoor talks about: what we sell, customers, and bookings."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar

from stagedoor.exceptions import IllegalTransitionError


class ItemKind(StrEnum):
    """What kind of thing an item is. VAT depends on it."""

    TICKET = "ticket"
    PROGRAMME = "programme"
    MERCH = "merch"


class PaymentStatus(StrEnum):
    """Whether the customer's money has arrived."""

    PAID = "paid"
    AWAITING_PAYMENT = "awaiting_payment"


class BookingStatus(StrEnum):
    """Where a booking has got to."""

    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


@dataclass(frozen=True)
class Item:
    """Something we sell. The price includes VAT.

    A ticket is for a ``performance``; anything else has no performance.
    """

    code: str
    name: str
    price: Decimal
    kind: ItemKind
    weight_grams: int
    performance: str | None = None


@dataclass(frozen=True)
class Address:
    """Where to post things. ``country`` is a two-letter code, like GB."""

    line1: str
    city: str
    postcode: str
    country: str


@dataclass(frozen=True)
class Customer:
    """Somebody booking with us. Only posted tickets need an address."""

    name: str
    email: str
    address: Address | None = None


@dataclass(frozen=True)
class BookingLine:
    """One item on a booking, priced as it was when the booking was made."""

    code: str
    name: str
    kind: ItemKind
    performance: str | None
    unit_price: Decimal
    quantity: int

    @property
    def line_total(self) -> Decimal:
        """The unit price multiplied by the quantity."""
        return self.unit_price * self.quantity


@dataclass
class Booking:
    """A customer's booking.

    ``total`` is ``subtotal`` minus ``discount``, plus ``delivery_fee``.
    ``vat`` is the VAT included in ``total``, not added to it. ``status``
    changes as the booking is paid for, used, or cancelled.
    """

    id: str
    customer: Customer
    lines: tuple[BookingLine, ...]
    discount_code: str | None
    subtotal: Decimal
    discount: Decimal
    delivery: str
    delivery_fee: Decimal
    total: Decimal
    vat: Decimal
    payment_method: str
    payment_reference: str
    status: BookingStatus
    payment_fee: Decimal
    placed_at: datetime
    hold_references: tuple[str, ...] = ()
    wallet_pass: str | None = None
    tracking_number: str | None = None
    invoice_number: str | None = None

    @property
    def state(self) -> BookingState:
        """What this booking can do, in the status it is in."""
        return STATES[self.status]

    def mark_paid(self) -> None:
        """The customer's money has arrived."""
        self.state.mark_paid(self)

    def check_in(self) -> None:
        """The customer is at the door."""
        self.state.check_in(self)

    def cancel(self) -> None:
        """Call the booking off. A paid booking is refunded."""
        self.state.cancel(self)


class BookingState:
    """What a booking can do in one status.

    Each status has a state, which decides what each action does to a
    booking in that status. Unless a state says otherwise, it refuses.
    """

    status: ClassVar[BookingStatus]

    def mark_paid(self, booking: Booking) -> None:
        self._refuse(booking, BookingStatus.PAID)

    def check_in(self, booking: Booking) -> None:
        self._refuse(booking, BookingStatus.CHECKED_IN)

    def cancel(self, booking: Booking) -> None:
        self._refuse(booking, BookingStatus.CANCELLED)

    def _refuse(self, booking: Booking, wanted: BookingStatus) -> None:
        raise IllegalTransitionError(booking.id, self.status, wanted)


class AwaitingPayment(BookingState):
    status = BookingStatus.AWAITING_PAYMENT

    def mark_paid(self, booking: Booking) -> None:
        booking.status = BookingStatus.PAID

    def cancel(self, booking: Booking) -> None:
        booking.status = BookingStatus.CANCELLED


class Paid(BookingState):
    status = BookingStatus.PAID

    def check_in(self, booking: Booking) -> None:
        booking.status = BookingStatus.CHECKED_IN

    def cancel(self, booking: Booking) -> None:
        booking.status = BookingStatus.REFUNDED


class CheckedIn(BookingState):
    status = BookingStatus.CHECKED_IN


class Cancelled(BookingState):
    status = BookingStatus.CANCELLED


class Refunded(BookingState):
    status = BookingStatus.REFUNDED


# The state for each status. A booking stores its status, not its state.
STATES: dict[BookingStatus, BookingState] = {
    state.status: state
    for state in [
        AwaitingPayment(),
        Paid(),
        CheckedIn(),
        Cancelled(),
        Refunded(),
    ]
}
