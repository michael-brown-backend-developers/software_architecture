"""A stand-in for a mobile wallet pass service.

Give it the ticket holder's name, what the tickets are for, and a barcode
for each ticket, and it returns a link to a pass the customer can add to
the wallet on their phone.

    simulate_outage  set it to True, and every call raises WalletError
"""

from uuid import uuid4

__all__ = ["PassService", "WalletError", "simulate_outage"]

simulate_outage: bool = False


class WalletError(Exception):
    """The pass could not be issued."""


class PassService:
    """A connection to the wallet pass service."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def issue(self, *, holder: str, event: str, barcodes: list[str]) -> str:
        """Issue a pass, and return the link to it."""
        if simulate_outage:
            raise WalletError("The pass service is not responding.")
        if not barcodes:
            raise WalletError("A pass needs at least one barcode.")
        return f"https://wallet.example/pass/{uuid4().hex[:16]}"
