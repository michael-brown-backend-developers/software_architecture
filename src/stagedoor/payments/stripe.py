"""Paying by card, through Stripe.

This is the only module in StageDoor that knows Stripe exists. It turns
pounds into the pence Stripe wants, and Stripe's errors into ours.
"""

import logging
import time
from decimal import ROUND_HALF_UP, Decimal

import fakestripe

from stagedoor.exceptions import (
    MissingPaymentTokenError,
    PaymentFailedError,
    PaymentUnavailableError,
)
from stagedoor.models import Booking, PaymentStatus
from stagedoor.payments.base import PaymentResult, percentage

logger = logging.getLogger(__name__)


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
        # Stripe sometimes does not answer. Try three times, waiting longer
        # each time. The idempotency key means a retry can never charge the
        # customer twice, even if Stripe took the first one.
        for attempt in range(1, 4):
            started = time.perf_counter()
            try:
                intent = fakestripe.PaymentIntent.create(
                    amount=to_pence(amount),
                    currency="gbp",
                    payment_method=token,
                    idempotency_key=f"booking-{booking_id}",
                )
                break
            except fakestripe.error.CardError as error:
                raise PaymentFailedError(error.user_message) from error
            except fakestripe.error.APIConnectionError as error:
                if attempt == 3:
                    raise PaymentUnavailableError("Stripe") from error
                time.sleep(0.5 * 2**attempt)
            finally:
                elapsed = time.perf_counter() - started
                logger.info("Stripe charge took %.3fs", elapsed)
        return PaymentResult(reference=intent.id, status=PaymentStatus.PAID)

    def fee(self, amount: Decimal) -> Decimal:
        return percentage(amount, "0.015") + Decimal("0.20")

    def describe(self, booking: Booking) -> str:
        return "Paid by card."
