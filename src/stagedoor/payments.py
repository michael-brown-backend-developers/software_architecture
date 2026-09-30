"""Taking payment for bookings.

Every way of paying is a class with the same three methods, so the rest of
StageDoor can take a payment, work out its fee, and describe it to the
customer, without knowing which way the customer chose to pay.

The API keys come from environment variables, with test keys to fall back
on while we develop.
"""

import os
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

import fakepaypal
import fakestripe

from stagedoor.exceptions import (
    MissingPaymentTokenError,
    UnknownPaymentMethodError,
)
from stagedoor.models import Booking
from stagedoor.pricing import PENNY


class PaymentMethod(Protocol):
    """A way for a customer to pay."""

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> str | dict[str, str]:
        """Take ``amount`` from the customer.

        Return the payment reference, or for PayPal, the whole of PayPal's
        answer, so that the booking can see whether the payment went through.
        """
        ...

    def fee(self, amount: Decimal) -> Decimal:
        """What the provider charges us for taking ``amount``."""
        ...

    def describe(self, booking: Booking) -> str:
        """Tell the customer, in their confirmation, how they paid."""
        ...


def _percentage(amount: Decimal, rate: str) -> Decimal:
    return (amount * Decimal(rate)).quantize(PENNY, ROUND_HALF_UP)


class CardPayment:
    """Paying by card, through Stripe."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> str:
        if token is None:
            raise MissingPaymentTokenError("card")
        fakestripe.api_key = self.api_key
        intent = fakestripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency="gbp",
            payment_method=token,
        )
        return intent.id

    def fee(self, amount: Decimal) -> Decimal:
        return _percentage(amount, "0.015") + Decimal("0.20")

    def describe(self, booking: Booking) -> str:
        return "Paid by card."


class PayPalPayment:
    """Paying with PayPal."""

    def __init__(self, client_id: str, secret: str) -> None:
        self.client = fakepaypal.PayPalClient(
            client_id=client_id, secret=secret
        )

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> dict[str, str]:
        if token is None:
            raise MissingPaymentTokenError("paypal")
        return self.client.create_order(
            {"amount": str(amount), "currency": "GBP", "payer": token}
        )

    def fee(self, amount: Decimal) -> Decimal:
        return _percentage(amount, "0.029") + Decimal("0.30")

    def describe(self, booking: Booking) -> str:
        return "Paid with PayPal."


class BankTransferPayment:
    """Paying by bank transfer, quoting a reference we give the customer."""

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> str:
        return f"SD-{booking_id.upper()}"

    def fee(self, amount: Decimal) -> Decimal:
        return Decimal("0.00")

    def describe(self, booking: Booking) -> str:
        return (
            f"Please pay £{booking.total} by bank transfer to sort code "
            f"12-34-56, account 12345678, quoting {booking.payment_reference}."
        )


PAYMENT_METHODS: dict[str, PaymentMethod] = {
    "card": CardPayment(
        api_key=os.environ.get("STRIPE_API_KEY", "sk_test_stagedoor"),
    ),
    "paypal": PayPalPayment(
        client_id=os.environ.get("PAYPAL_CLIENT_ID", "stagedoor-sandbox"),
        secret=os.environ.get("PAYPAL_SECRET", "sandbox-secret"),
    ),
    "bank_transfer": BankTransferPayment(),
}


def get_payment_method(name: str) -> PaymentMethod:
    """The payment method a customer chose, by name."""
    try:
        return PAYMENT_METHODS[name]
    except KeyError:
        raise UnknownPaymentMethodError(name) from None
