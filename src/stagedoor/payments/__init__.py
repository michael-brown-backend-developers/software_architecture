"""Taking payment for bookings.

Every way of paying is a PaymentMethod (see base.py), so the rest of
StageDoor can take a payment, work out its fee, and describe it to the
customer, without knowing which way the customer chose to pay - or which
company takes the money. Each company's library is used in exactly one
module: the adapter that translates it.

Which ways of paying are switched on, and production's keys, come from
environment variables. Everywhere else uses test keys.
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

# Only production uses the real keys, and it must be given them. Everywhere
# else uses test keys, whatever is set, so staging can never charge a card.
LIVE = os.environ.get("STAGEDOOR_ENV") == "production"

# Which ways of paying are switched on, for example "card,bank_transfer".
ENABLED = os.environ.get(
    "STAGEDOOR_PAYMENT_METHODS", "card,paypal,bank_transfer"
).split(",")

PAYMENT_METHODS: dict[str, PaymentMethod] = {}
if "card" in ENABLED:
    PAYMENT_METHODS["card"] = LoggingPaymentMethod(
        RetryingPaymentMethod(
            StripeCardPayment(
                api_key=(
                    os.environ["STRIPE_API_KEY"]
                    if LIVE
                    else "sk_test_stagedoor"
                ),
            ),
        ),
        "Stripe charge",
    )
if "paypal" in ENABLED:
    PAYMENT_METHODS["paypal"] = LoggingPaymentMethod(
        PayPalPayment(
            client_id=(
                os.environ["PAYPAL_CLIENT_ID"] if LIVE else "stagedoor-sandbox"
            ),
            secret=os.environ["PAYPAL_SECRET"] if LIVE else "sandbox-secret",
        ),
        "PayPal charge",
    )
if "bank_transfer" in ENABLED:
    PAYMENT_METHODS["bank_transfer"] = BankTransferPayment()


def get_payment_method(name: str) -> PaymentMethod:
    """The payment method a customer chose, by name."""
    try:
        return PAYMENT_METHODS[name]
    except KeyError:
        raise UnknownPaymentMethodError(name) from None
