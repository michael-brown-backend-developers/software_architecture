from datetime import UTC, datetime
from decimal import Decimal

import fakestripe
import pytest

from stagedoor.exceptions import (
    MissingPaymentTokenError,
    UnknownPaymentMethodError,
)
from stagedoor.models import Booking, Customer
from stagedoor.payments import (
    BankTransferPayment,
    CardPayment,
    PayPalPayment,
    get_payment_method,
)

AMOUNT = Decimal("63.00")


def test_paying_by_card() -> None:
    card = CardPayment(api_key="sk_test")

    assert card.charge(AMOUNT, "abc123", "pm_card_visa").startswith("pi_")
    assert card.fee(AMOUNT) == Decimal("1.15")


def test_a_declined_card_raises_stripes_own_error() -> None:
    card = CardPayment(api_key="sk_test")

    with pytest.raises(fakestripe.error.CardError):
        card.charge(AMOUNT, "abc123", "pm_card_declined")


def test_a_card_needs_a_token() -> None:
    with pytest.raises(MissingPaymentTokenError):
        CardPayment(api_key="sk_test").charge(AMOUNT, "abc123", None)


def test_paying_with_paypal() -> None:
    paypal = PayPalPayment(client_id="id", secret="secret")

    assert paypal.charge(AMOUNT, "abc123", "payer_ok")["status"] == "COMPLETED"
    assert paypal.fee(AMOUNT) == Decimal("2.13")


def test_paying_by_bank_transfer() -> None:
    transfer = BankTransferPayment()

    assert transfer.charge(AMOUNT, "abc123", None) == "SD-ABC123"
    assert transfer.fee(AMOUNT) == Decimal("0.00")


def test_a_bank_transfer_tells_the_customer_how_to_pay(ada: Customer) -> None:
    booking = Booking(
        id="abc123",
        customer=ada,
        lines=(),
        discount_code=None,
        subtotal=AMOUNT,
        discount=Decimal("0.00"),
        delivery="e_ticket",
        delivery_fee=Decimal("0.00"),
        total=AMOUNT,
        vat=Decimal("0.00"),
        payment_method="bank_transfer",
        payment_reference="SD-ABC123",
        payment_fee=Decimal("0.00"),
        placed_at=datetime(2026, 9, 30, 9, 15, tzinfo=UTC),
    )

    description = BankTransferPayment().describe(booking)

    assert "Please pay £63.00" in description
    assert "quoting SD-ABC123" in description


def test_an_unknown_payment_method_is_rejected() -> None:
    with pytest.raises(UnknownPaymentMethodError):
        get_payment_method("cash")
