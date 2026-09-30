from decimal import Decimal

import fakestripe
import pytest

from stagedoor.exceptions import (
    MissingPaymentTokenError,
    UnknownPaymentMethodError,
)
from stagedoor.payments import payment_fee, take_payment


def test_paying_by_card() -> None:
    reference = take_payment(
        "card", Decimal("63.00"), "abc123", "pm_card_visa"
    )

    assert reference.startswith("pi_")


def test_a_declined_card_raises_stripes_own_error() -> None:
    with pytest.raises(fakestripe.error.CardError):
        take_payment("card", Decimal("63.00"), "abc123", "pm_card_declined")


def test_paying_with_paypal() -> None:
    reference = take_payment("paypal", Decimal("63.00"), "abc123", "payer_ok")

    assert reference.startswith("PAYID-")


def test_paying_by_bank_transfer() -> None:
    reference = take_payment("bank_transfer", Decimal("63.00"), "abc123", None)

    assert reference == "SD-ABC123"


def test_a_card_needs_a_token() -> None:
    with pytest.raises(MissingPaymentTokenError):
        take_payment("card", Decimal("63.00"), "abc123", None)


def test_an_unknown_payment_method_is_rejected() -> None:
    with pytest.raises(UnknownPaymentMethodError):
        take_payment("cash", Decimal("63.00"), "abc123", None)


@pytest.mark.parametrize(
    ("method", "fee"),
    [
        ("card", Decimal("1.15")),
        ("paypal", Decimal("2.13")),
        ("bank_transfer", Decimal("0.00")),
    ],
)
def test_payment_fees(method: str, fee: Decimal) -> None:
    assert payment_fee(method, Decimal("63.00")) == fee
