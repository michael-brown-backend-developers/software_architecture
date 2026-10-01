from datetime import UTC, datetime
from decimal import Decimal

import fakestripe
import pytest

from stagedoor.exceptions import (
    MissingPaymentTokenError,
    PaymentFailedError,
    PaymentUnavailableError,
    UnknownPaymentMethodError,
)
from stagedoor.models import Booking, BookingStatus, Customer, PaymentStatus
from stagedoor.payments import get_payment_method
from stagedoor.payments.bank_transfer import BankTransferPayment
from stagedoor.payments.paypal import PayPalPayment
from stagedoor.payments.stripe import StripeCardPayment, to_pence

AMOUNT = Decimal("63.00")


@pytest.mark.parametrize(
    ("amount", "pence"),
    [
        (Decimal("80.53"), 8053),
        (Decimal("0.10"), 10),
        (Decimal("12.99"), 1299),
        (Decimal("100.00"), 10000),
    ],
)
def test_to_pence(amount: Decimal, pence: int) -> None:
    assert to_pence(amount) == pence


def test_paying_by_card() -> None:
    card = StripeCardPayment(api_key="sk_test")

    result = card.charge(AMOUNT, "abc123", "pm_card_visa")

    assert result.reference.startswith("pi_")
    assert result.status == PaymentStatus.PAID
    assert card.fee(AMOUNT) == Decimal("1.15")


def test_a_declined_card_says_why_in_our_words() -> None:
    card = StripeCardPayment(api_key="sk_test")

    with pytest.raises(PaymentFailedError, match="Your card was declined."):
        card.charge(AMOUNT, "abc123", "pm_card_declined")


def test_a_card_needs_a_token() -> None:
    with pytest.raises(MissingPaymentTokenError):
        StripeCardPayment(api_key="sk_test").charge(AMOUNT, "abc123", None)


def test_paying_with_paypal() -> None:
    paypal = PayPalPayment(client_id="id", secret="secret")

    result = paypal.charge(AMOUNT, "abc123", "payer_ok")

    assert result.reference.startswith("PAYID-")
    assert result.status == PaymentStatus.PAID
    assert paypal.fee(AMOUNT) == Decimal("2.13")


def test_a_declined_paypal_payment_is_a_failure_not_an_answer() -> None:
    paypal = PayPalPayment(client_id="id", secret="secret")

    with pytest.raises(PaymentFailedError, match="PayPal declined"):
        paypal.charge(AMOUNT, "abc123", "payer_declined")


def test_paying_by_bank_transfer() -> None:
    transfer = BankTransferPayment()

    result = transfer.charge(AMOUNT, "abc123", None)

    assert result.reference == "SD-ABC123"
    assert result.status == PaymentStatus.AWAITING_PAYMENT
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
        status=BookingStatus.AWAITING_PAYMENT,
        payment_fee=Decimal("0.00"),
        placed_at=datetime(2026, 9, 30, 9, 15, tzinfo=UTC),
    )

    description = BankTransferPayment().describe(booking)

    assert "Please pay £63.00" in description
    assert "quoting SD-ABC123" in description


def test_an_unknown_payment_method_is_rejected() -> None:
    with pytest.raises(UnknownPaymentMethodError):
        get_payment_method("cash", {})


def test_an_unreachable_stripe_is_unavailable_not_declined() -> None:
    fakestripe.simulate_outage = True

    with pytest.raises(PaymentUnavailableError):
        StripeCardPayment(api_key="sk_test").charge(
            AMOUNT, "abc123", "pm_card_visa"
        )


def test_charging_the_same_booking_twice_charges_once() -> None:
    card = StripeCardPayment(api_key="sk_test")

    first = card.charge(AMOUNT, "abc123", "pm_card_visa")
    second = card.charge(AMOUNT, "abc123", "pm_card_visa")

    assert first.reference == second.reference


def test_a_card_payment_can_be_refunded() -> None:
    card = StripeCardPayment(api_key="sk_test")
    payment = card.charge(AMOUNT, "abc123", "pm_card_visa")

    card.refund(payment.reference, AMOUNT)


def test_a_refund_while_stripe_is_unreachable_is_unavailable() -> None:
    fakestripe.simulate_outage = True

    with pytest.raises(PaymentUnavailableError):
        StripeCardPayment(api_key="sk_test").refund("pi_123", AMOUNT)


def test_a_paypal_payment_can_be_refunded() -> None:
    paypal = PayPalPayment(client_id="id", secret="secret")
    payment = paypal.charge(AMOUNT, "abc123", "payer_ok")

    paypal.refund(payment.reference, AMOUNT)
