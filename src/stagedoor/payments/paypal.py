"""Paying with PayPal.

This is the only module in StageDoor that knows PayPal exists. PayPal
answers with a dictionary, even when a payment fails, so this is where a
failure becomes a PaymentFailedError.
"""

from decimal import Decimal

import fakepaypal

from stagedoor.exceptions import MissingPaymentTokenError, PaymentFailedError
from stagedoor.models import Booking, PaymentStatus
from stagedoor.payments.base import PaymentResult, percentage


class PayPalPayment:
    """Paying with PayPal."""

    def __init__(self, client_id: str, secret: str) -> None:
        self.client = fakepaypal.PayPalClient(
            client_id=client_id, secret=secret
        )

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> PaymentResult:
        if token is None:
            raise MissingPaymentTokenError("paypal")
        answer = self.client.create_order(
            {"amount": str(amount), "currency": "GBP", "payer": token}
        )
        if answer["status"] != "COMPLETED":
            raise PaymentFailedError("PayPal declined the payment.")
        return PaymentResult(reference=answer["id"], status=PaymentStatus.PAID)

    def fee(self, amount: Decimal) -> Decimal:
        return percentage(amount, "0.029") + Decimal("0.30")

    def describe(self, booking: Booking) -> str:
        return "Paid with PayPal."
