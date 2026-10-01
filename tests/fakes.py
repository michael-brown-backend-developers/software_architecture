"""Simple, honest stand-ins for StageDoor's own collaborators.

Each one behaves like the real thing in the ways a test cares about, and
keeps a record of what was asked of it, so a test can check what happened
rather than how.
"""

from decimal import Decimal
from pathlib import Path

from stagedoor.exceptions import MissingPaymentTokenError, PaymentFailedError
from stagedoor.models import Booking, PaymentStatus
from stagedoor.payments.base import PaymentResult
from stagedoor.storage import BookingStore

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


class FailingStore(BookingStore):
    """A booking store on a disk that is full."""

    def __init__(self) -> None:
        super().__init__(Path("nowhere"))

    def save(self, booking: Booking) -> None:
        raise OSError("No space left on device")


def no_sleep(seconds: float) -> None:
    """Wait for no time at all."""
