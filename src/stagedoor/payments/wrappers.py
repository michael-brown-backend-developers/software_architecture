"""Payment methods that add something to another payment method.

Each wrapper is a PaymentMethod that holds another PaymentMethod, passes
every call on to it, and adds one thing of its own. Because they all have
the same shape, they can be wrapped around each other, in any order.
"""

import time
from collections.abc import Callable
from decimal import Decimal

from stagedoor.models import Booking
from stagedoor.payments.base import PaymentMethod, PaymentResult
from stagedoor.resilience import retry, timed


class RetryingPaymentMethod:
    """Tries a charge again when the provider is unavailable."""

    def __init__(
        self,
        inner: PaymentMethod,
        attempts: int = 3,
        base_delay: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.inner = inner
        self._charge = retry(attempts, base_delay, sleep)(inner.charge)

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> PaymentResult:
        return self._charge(amount, booking_id, token)

    def fee(self, amount: Decimal) -> Decimal:
        return self.inner.fee(amount)

    def describe(self, booking: Booking) -> str:
        return self.inner.describe(booking)


class LoggingPaymentMethod:
    """Logs how long every charge takes."""

    def __init__(self, inner: PaymentMethod, name: str) -> None:
        self.inner = inner
        self._charge = timed(name)(inner.charge)

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> PaymentResult:
        return self._charge(amount, booking_id, token)

    def fee(self, amount: Decimal) -> Decimal:
        return self.inner.fee(amount)

    def describe(self, booking: Booking) -> str:
        return self.inner.describe(booking)
