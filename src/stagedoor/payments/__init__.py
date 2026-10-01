"""Taking payment for bookings.

Every way of paying is a PaymentMethod (see base.py), so the rest of
StageDoor can take a payment, work out its fee, and describe it to the
customer, without knowing which way the customer chose to pay - or which
company takes the money. Each company's library is used in exactly one
module: the adapter that translates it.

create_payment_method() is the one place that knows how each way of paying
is built, from the settings.
"""

import time
from collections.abc import Callable, Mapping

from stagedoor.exceptions import UnknownPaymentMethodError
from stagedoor.payments.bank_transfer import BankTransferPayment
from stagedoor.payments.base import PaymentMethod
from stagedoor.payments.paypal import PayPalPayment
from stagedoor.payments.stripe import StripeCardPayment
from stagedoor.payments.wrappers import (
    LoggingPaymentMethod,
    RetryingPaymentMethod,
)
from stagedoor.settings import Settings


def create_payment_method(
    name: str,
    settings: Settings,
    sleep: Callable[[float], None] = time.sleep,
) -> PaymentMethod:
    """Build the payment method called ``name``, ready to use.

    ``sleep`` is how a payment method waits before it tries again.
    """
    match name:
        case "card":
            return LoggingPaymentMethod(
                RetryingPaymentMethod(
                    StripeCardPayment(settings.stripe_api_key), sleep=sleep
                ),
                "Stripe charge",
            )
        case "paypal":
            return LoggingPaymentMethod(
                PayPalPayment(
                    settings.paypal_client_id, settings.paypal_secret
                ),
                "PayPal charge",
            )
        case "bank_transfer":
            return BankTransferPayment()
    raise UnknownPaymentMethodError(name)


def get_payment_method(
    name: str, payment_methods: Mapping[str, PaymentMethod]
) -> PaymentMethod:
    """The payment method a customer chose, by name, if it is switched on."""
    try:
        return payment_methods[name]
    except KeyError:
        raise UnknownPaymentMethodError(name) from None
