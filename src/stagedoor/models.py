"""The things StageDoor talks about: what we sell, customers, and bookings."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class ItemKind(StrEnum):
    """What kind of thing an item is. VAT depends on it."""

    TICKET = "ticket"
    PROGRAMME = "programme"
    MERCH = "merch"


class PaymentStatus(StrEnum):
    """Whether the customer's money has arrived."""

    PAID = "paid"
    AWAITING_PAYMENT = "awaiting_payment"


@dataclass(frozen=True)
class Item:
    """Something we sell. The price includes VAT.

    A ticket is for a ``performance``; anything else has no performance.
    """

    code: str
    name: str
    price: Decimal
    kind: ItemKind
    performance: str | None = None


@dataclass(frozen=True)
class Customer:
    """Somebody booking with us."""

    name: str
    email: str


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


@dataclass(frozen=True)
class Booking:
    """A customer's booking.

    ``total`` is ``subtotal`` minus ``discount``, plus ``delivery_fee``.
    ``vat`` is the VAT included in ``total``, not added to it.
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
    payment_status: PaymentStatus
    payment_fee: Decimal
    placed_at: datetime
