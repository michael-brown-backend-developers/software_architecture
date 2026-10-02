"""Paying by bank transfer, quoting a reference we give the customer.

No money changes hands when the booking is made, so the payment is
awaiting payment until the customer's transfer arrives.
"""

from decimal import Decimal

from stagedoor.application.ports import PaymentResult
from stagedoor.domain.models import Booking, PaymentStatus


class BankTransferPayment:
    """Paying by bank transfer."""

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> PaymentResult:
        return PaymentResult(
            reference=f"SD-{booking_id.upper()}",
            status=PaymentStatus.AWAITING_PAYMENT,
        )

    def refund(self, reference: str, amount: Decimal) -> None:
        # Finance pay the money back by hand, quoting the same reference.
        pass

    def fee(self, amount: Decimal) -> Decimal:
        return Decimal("0.00")

    def describe(self, booking: Booking) -> str:
        return (
            f"Please pay £{booking.total} by bank transfer to sort code "
            f"12-34-56, account 12345678, quoting {booking.payment_reference}."
        )
