"""Taking payment for bookings.

Every way of paying is a PaymentMethod (see base.py), so the rest of
StageDoor can take a payment, work out its fee, and describe it to the
customer, without knowing which way the customer chose to pay - or which
company takes the money. Each company's library is used in exactly one
module: the adapter that translates it.

The API keys come from environment variables, with test keys to fall back
on while we develop.
"""

import os

from stagedoor.exceptions import UnknownPaymentMethodError
from stagedoor.payments.bank_transfer import BankTransferPayment
from stagedoor.payments.base import PaymentMethod
from stagedoor.payments.paypal import PayPalPayment
from stagedoor.payments.stripe import StripeCardPayment
from stagedoor.payments.wrappers import (
    LoggingPaymentMethod,
    RetryingPaymentMethod,
)

PAYMENT_METHODS: dict[str, PaymentMethod] = {
    "card": LoggingPaymentMethod(
        RetryingPaymentMethod(
            StripeCardPayment(
                api_key=os.environ.get("STRIPE_API_KEY", "sk_test_stagedoor"),
            ),
        ),
        "Stripe charge",
    ),
    "paypal": LoggingPaymentMethod(
        PayPalPayment(
            client_id=os.environ.get("PAYPAL_CLIENT_ID", "stagedoor-sandbox"),
            secret=os.environ.get("PAYPAL_SECRET", "sandbox-secret"),
        ),
        "PayPal charge",
    ),
    "bank_transfer": BankTransferPayment(),
}


def get_payment_method(name: str) -> PaymentMethod:
    """The payment method a customer chose, by name."""
    try:
        return PAYMENT_METHODS[name]
    except KeyError:
        raise UnknownPaymentMethodError(name) from None
