"""Taking payment for bookings.

We take payment by card through Stripe, through PayPal, and by bank
transfer. The API keys come from environment variables, with test keys to
fall back on while we develop.
"""

import os
from decimal import ROUND_HALF_UP, Decimal

import fakepaypal
import fakestripe

from stagedoor.exceptions import (
    MissingPaymentTokenError,
    UnknownPaymentMethodError,
)
from stagedoor.pricing import PENNY


def take_payment(
    method: str, amount: Decimal, booking_id: str, token: str | None
) -> str:
    """Take ``amount`` from the customer, and return the payment reference."""
    if method == "card":
        if token is None:
            raise MissingPaymentTokenError(method)
        fakestripe.api_key = os.environ.get(
            "STRIPE_API_KEY", "sk_test_stagedoor"
        )
        intent = fakestripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency="gbp",
            payment_method=token,
        )
        return intent.id
    elif method == "paypal":
        if token is None:
            raise MissingPaymentTokenError(method)
        client = fakepaypal.PayPalClient(
            client_id=os.environ.get("PAYPAL_CLIENT_ID", "stagedoor-sandbox"),
            secret=os.environ.get("PAYPAL_SECRET", "sandbox-secret"),
        )
        result = client.create_order(
            {"amount": str(amount), "currency": "GBP", "payer": token}
        )
        return result["id"]
    elif method == "bank_transfer":
        # The customer pays us, quoting this reference.
        return f"SD-{booking_id.upper()}"
    raise UnknownPaymentMethodError(method)


def payment_fee(method: str, amount: Decimal) -> Decimal:
    """What the payment provider charges us for taking ``amount``."""
    if method == "card":
        percentage = (amount * Decimal("0.015")).quantize(PENNY, ROUND_HALF_UP)
        return percentage + Decimal("0.20")
    elif method == "paypal":
        percentage = (amount * Decimal("0.029")).quantize(PENNY, ROUND_HALF_UP)
        return percentage + Decimal("0.30")
    elif method == "bank_transfer":
        return Decimal("0.00")
    raise UnknownPaymentMethodError(method)
