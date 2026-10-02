"""The things StageDoor talks about: what we sell, customers, and bookings."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

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


# Every status a booking can move to, from each status it can be in.
ALLOWED_TRANSITIONS: dict[BookingStatus, frozenset[BookingStatus]] = {
    BookingStatus.AWAITING_PAYMENT: frozenset(
        {BookingStatus.PAID, BookingStatus.CANCELLED}
    ),
    BookingStatus.PAID: frozenset(
        {BookingStatus.CHECKED_IN, BookingStatus.REFUNDED}
    ),
    BookingStatus.CHECKED_IN: frozenset(),
    BookingStatus.CANCELLED: frozenset(),
    BookingStatus.REFUNDED: frozenset(),
}


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
    ``payment_reference`` is empty until the payment has been taken.
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

    def mark_paid(self) -> None:
        """The customer's money has arrived."""
        self._move_to(BookingStatus.PAID)

    def check_in(self) -> None:
        """The customer is at the door."""
        self._move_to(BookingStatus.CHECKED_IN)

    def cancel(self) -> None:
        """Call the booking off. A paid booking is refunded."""
        match self.status:
            case BookingStatus.PAID:
                self._move_to(BookingStatus.REFUNDED)
            case _:
                self._move_to(BookingStatus.CANCELLED)

    def _move_to(self, status: BookingStatus) -> None:
        if status not in ALLOWED_TRANSITIONS[self.status]:
            raise IllegalTransitionError(self.id, self.status, status)
        self.status = status
