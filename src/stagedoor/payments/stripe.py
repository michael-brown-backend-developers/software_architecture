"""Paying by card, through Stripe.

This is the only module in StageDoor that knows Stripe exists. It turns
pounds into the pence Stripe wants, and Stripe's errors into ours.
"""

from decimal import ROUND_HALF_UP, Decimal

import fakestripe

from stagedoor.exceptions import (
    MissingPaymentTokenError,
    PaymentFailedError,
    PaymentUnavailableError,
)
from stagedoor.models import Booking, PaymentStatus
from stagedoor.payments.base import PaymentResult, percentage


def to_pence(amount: Decimal) -> int:
    """Stripe wants amounts in the smallest unit of the currency."""
    return int((amount * 100).to_integral_value(ROUND_HALF_UP))


class StripeCardPayment:
    """Paying by card, through Stripe."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> PaymentResult:
        if token is None:
            raise MissingPaymentTokenError("card")
        fakestripe.api_key = self.api_key
        try:
            intent = fakestripe.PaymentIntent.create(
                amount=to_pence(amount),
                currency="gbp",
                payment_method=token,
                # The same key for every attempt, so that a retry can never
                # charge the customer twice.
                idempotency_key=f"booking-{booking_id}",
            )
        except fakestripe.error.CardError as error:
            raise PaymentFailedError(error.user_message) from error
        except fakestripe.error.APIConnectionError as error:
            raise PaymentUnavailableError("Stripe") from error
        return PaymentResult(reference=intent.id, status=PaymentStatus.PAID)

    def refund(self, reference: str, amount: Decimal) -> None:
        fakestripe.api_key = self.api_key
        try:
            fakestripe.Refund.create(
                payment_intent=reference, amount=to_pence(amount)
            )
        except fakestripe.error.APIConnectionError as error:
            raise PaymentUnavailableError("Stripe") from error

    def fee(self, amount: Decimal) -> Decimal:
        return percentage(amount, "0.015") + Decimal("0.20")

    def describe(self, booking: Booking) -> str:
        return "Paid by card."
