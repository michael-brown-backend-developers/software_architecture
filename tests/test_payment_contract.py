"""What every payment method must do, checked against each of them.

The fake in fakes.py is only useful while it behaves like the real thing.
These tests hold it to the same promises as the Stripe adapter, so that a
test that passes with the fake would pass with Stripe too.
"""

from decimal import Decimal

import pytest
from fakes import DECLINED, FakePaymentMethod

from stagedoor.exceptions import MissingPaymentTokenError, PaymentFailedError
from stagedoor.models import PaymentStatus
from stagedoor.payments.base import PaymentMethod
from stagedoor.payments.stripe import StripeCardPayment

AMOUNT = Decimal("64.00")


class Card:
    """A payment method, and a token it accepts and one it declines."""

    def __init__(
        self, method: PaymentMethod, good_token: str, declined_token: str
    ) -> None:
        self.method = method
        self.good_token = good_token
        self.declined_token = declined_token


@pytest.fixture(params=["fake", "stripe"])
def card(request: pytest.FixtureRequest) -> Card:
    if request.param == "fake":
        return Card(FakePaymentMethod(), "tok_ok", DECLINED)
    return Card(
        StripeCardPayment(api_key="sk_test"),
        "pm_card_visa",
        "pm_card_declined",
    )


def test_a_good_card_is_charged(card: Card) -> None:
    result = card.method.charge(AMOUNT, "abc123", card.good_token)

    assert result.status == PaymentStatus.PAID
    assert result.reference


def test_a_declined_card_says_why(card: Card) -> None:
    with pytest.raises(PaymentFailedError) as declined:
        card.method.charge(AMOUNT, "abc123", card.declined_token)

    assert str(declined.value)


def test_a_card_payment_needs_a_token(card: Card) -> None:
    with pytest.raises(MissingPaymentTokenError):
        card.method.charge(AMOUNT, "abc123", None)


def test_a_payment_can_be_refunded(card: Card) -> None:
    result = card.method.charge(AMOUNT, "abc123", card.good_token)

    card.method.refund(result.reference, AMOUNT)
