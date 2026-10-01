"""A stand-in for Stripe's Python library.

StageDoor needs a card payment provider whose API never changes and never
needs a network connection, so this package imitates the general shape of
Stripe's: a module-level API key, amounts in pence, and errors raised as
exceptions. It is not Stripe, and it only does what the book needs.

Some payment methods behave differently, so that failures can be tested:

    pm_card_visa                a card that always works
    pm_card_declined            raises error.CardError
    pm_card_insufficient_funds  raises error.CardError

Set ``simulate_outage`` to True and every call raises
error.APIConnectionError, as if Stripe could not be reached. Set it to a
number instead, and only that many calls fail before Stripe recovers.
"""

from dataclasses import dataclass
from uuid import uuid4

from fakestripe import error

__all__ = ["PaymentIntent", "Refund", "api_key", "error", "simulate_outage"]

api_key: str | None = None
simulate_outage: bool | int = False

_DECLINES = {
    "pm_card_declined": ("Your card was declined.", "card_declined"),
    "pm_card_insufficient_funds": (
        "Your card has insufficient funds.",
        "insufficient_funds",
    ),
}

_by_idempotency_key: dict[str, PaymentIntent] = {}


def _outage() -> bool:
    """Whether this call should fail. A number counts down to recovery."""
    global simulate_outage
    if simulate_outage is True:
        return True
    if simulate_outage:
        simulate_outage -= 1
        return True
    return False


def _connect() -> None:
    if _outage():
        raise error.APIConnectionError("Could not connect to Stripe.")
    if not api_key:
        raise error.AuthenticationError("No API key provided.")


@dataclass
class PaymentIntent:
    """A request to take a payment, and what became of it."""

    id: str
    amount: int
    currency: str
    payment_method: str
    status: str

    @classmethod
    def create(
        cls,
        *,
        amount: int,
        currency: str,
        payment_method: str,
        idempotency_key: str | None = None,
    ) -> PaymentIntent:
        """Charge ``amount``, in the smallest unit of ``currency``."""
        _connect()
        if idempotency_key in _by_idempotency_key:
            return _by_idempotency_key[idempotency_key]
        if payment_method in _DECLINES:
            message, code = _DECLINES[payment_method]
            raise error.CardError(message, code=code)

        intent = cls(
            id=f"pi_{uuid4().hex[:24]}",
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            status="succeeded",
        )
        if idempotency_key is not None:
            _by_idempotency_key[idempotency_key] = intent
        return intent


@dataclass
class Refund:
    """Money given back against a PaymentIntent."""

    id: str
    payment_intent: str
    amount: int | None
    status: str

    @classmethod
    def create(
        cls, *, payment_intent: str, amount: int | None = None
    ) -> Refund:
        """Refund all of a payment, or ``amount`` of it."""
        _connect()
        return cls(
            id=f"re_{uuid4().hex[:24]}",
            payment_intent=payment_intent,
            amount=amount,
            status="succeeded",
        )
