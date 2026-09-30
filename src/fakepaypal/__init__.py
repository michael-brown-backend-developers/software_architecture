"""A stand-in for a PayPal client library.

StageDoor needs a second payment provider whose API never changes and never
needs a network connection. Where fakestripe raises exceptions, this one
answers every request with a dictionary, and a failure is a dictionary too:
look at its "status".

Some payers behave differently, so that failures can be tested:

    payer_ok        always pays
    payer_declined  the payment comes back with status "FAILED"
"""

from uuid import uuid4

__all__ = ["PayPalClient"]


class PayPalClient:
    """A connection to PayPal, or to its sandbox."""

    def __init__(
        self, client_id: str, secret: str, sandbox: bool = True
    ) -> None:
        self.client_id = client_id
        self.secret = secret
        self.sandbox = sandbox

    def create_order(self, order: dict[str, str]) -> dict[str, str]:
        """Take a payment. ``order`` needs "amount", "currency" and "payer"."""
        order_id = f"PAYID-{uuid4().hex[:20].upper()}"
        if order.get("payer") == "payer_declined":
            return {
                "id": order_id,
                "status": "FAILED",
                "reason": "INSTRUMENT_DECLINED",
            }
        return {"id": order_id, "status": "COMPLETED"}

    def refund(self, order_id: str) -> dict[str, str]:
        """Give back the whole of a payment."""
        return {
            "id": f"REFUND-{uuid4().hex[:20].upper()}",
            "order_id": order_id,
            "status": "COMPLETED",
        }
