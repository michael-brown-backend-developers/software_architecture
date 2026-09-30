"""What StageDoor needs from a way of paying, in StageDoor's own words.

This is the socket every payment provider plugs into. StageDoor owns it:
amounts are Decimal pounds, a failed payment is a PaymentFailedError, and a
payment that has not arrived yet can say so. Each provider's adapter
translates its own library into these terms, so nothing outside the adapter
ever sees the library.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from stagedoor.models import Booking, PaymentStatus
from stagedoor.pricing import PENNY


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

    def fee(self, amount: Decimal) -> Decimal:
        """What the provider charges us for taking ``amount``."""
        ...

    def describe(self, booking: Booking) -> str:
        """Tell the customer, in their confirmation, how they paid."""
        ...


def percentage(amount: Decimal, rate: str) -> Decimal:
    """``rate`` of ``amount``, to the nearest penny."""
    return (amount * Decimal(rate)).quantize(PENNY, ROUND_HALF_UP)
