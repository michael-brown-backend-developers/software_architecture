"""A payment method that adds something to another payment method.

The wrapper is a PaymentMethod that holds another PaymentMethod, passes
every call on to it, and adds one thing of its own: trying a charge again.
"""

import time
from collections.abc import Callable
from decimal import Decimal

from stagedoor.adapters.resilience import retry
from stagedoor.application.ports import PaymentMethod, PaymentResult
from stagedoor.domain.models import Booking


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

    def refund(self, reference: str, amount: Decimal) -> None:
        self.inner.refund(reference, amount)

    def fee(self, amount: Decimal) -> Decimal:
        return self.inner.fee(amount)

    def describe(self, booking: Booking) -> str:
        return self.inner.describe(booking)
