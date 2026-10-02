from decimal import Decimal

import pytest

from stagedoor.adapters.payments.wrappers import RetryingPaymentMethod
from stagedoor.application.ports import PaymentResult
from stagedoor.domain.exceptions import (
    PaymentFailedError,
    PaymentUnavailableError,
)
from stagedoor.domain.models import Booking, PaymentStatus

AMOUNT = Decimal("63.00")


class FlakyPayment:
    """A payment method that is unavailable a number of times, then works."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> PaymentResult:
        self.calls += 1
        if self.calls <= self.failures:
            raise PaymentUnavailableError("Flaky")
        return PaymentResult(reference="ref-1", status=PaymentStatus.PAID)

    def refund(self, reference: str, amount: Decimal) -> None:
        pass

    def fee(self, amount: Decimal) -> Decimal:
        return Decimal("0.42")

    def describe(self, booking: Booking) -> str:
        return "Paid flakily."


def no_sleep(seconds: float) -> None:
    pass


def test_a_charge_is_tried_again_until_it_works() -> None:
    flaky = FlakyPayment(failures=2)
    retrying = RetryingPaymentMethod(flaky, attempts=3, sleep=no_sleep)

    assert retrying.charge(AMOUNT, "abc123", None).reference == "ref-1"
    assert flaky.calls == 3


def test_retrying_gives_up_after_the_last_attempt() -> None:
    flaky = FlakyPayment(failures=5)
    retrying = RetryingPaymentMethod(flaky, attempts=3, sleep=no_sleep)

    with pytest.raises(PaymentUnavailableError):
        retrying.charge(AMOUNT, "abc123", None)
    assert flaky.calls == 3


def test_a_declined_payment_is_never_tried_again() -> None:
    class Declined(FlakyPayment):
        def charge(
            self, amount: Decimal, booking_id: str, token: str | None
        ) -> PaymentResult:
            self.calls += 1
            raise PaymentFailedError("Your card was declined.")

    declined = Declined(failures=0)
    retrying = RetryingPaymentMethod(declined, sleep=no_sleep)

    with pytest.raises(PaymentFailedError):
        retrying.charge(AMOUNT, "abc123", None)
    assert declined.calls == 1


def test_the_waits_get_longer() -> None:
    waits: list[float] = []
    retrying = RetryingPaymentMethod(
        FlakyPayment(failures=2), attempts=3, sleep=waits.append
    )

    retrying.charge(AMOUNT, "abc123", None)

    assert waits == [0.5, 1.0]
