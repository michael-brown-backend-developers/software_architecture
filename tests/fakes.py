"""Simple, honest stand-ins for StageDoor's own collaborators.

Each one behaves like the real thing in the ways a test cares about, and
keeps a record of what was asked of it, so a test can check what happened
rather than how. The in-memory repositories, outbox and unit of work are
adapters in their own right, in stagedoor.adapters.in_memory.
"""

from decimal import Decimal
from pathlib import Path

from stagedoor.adapters.in_memory import InMemoryBookingRepository
from stagedoor.application.ports import PaymentResult
from stagedoor.domain.exceptions import (
    MissingPaymentTokenError,
    PaymentFailedError,
)
from stagedoor.domain.models import Booking, PaymentStatus

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


class FailingRepository(InMemoryBookingRepository):
    """A repository whose database has run out of room."""

    def add(self, booking: Booking) -> None:
        raise OSError("No space left on device")


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
