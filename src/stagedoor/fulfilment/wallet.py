"""Issuing e-tickets as mobile wallet passes.

This is the only module in StageDoor that knows the wallet service's API.
"""

import fakewallet

from stagedoor.exceptions import FulfilmentError
from stagedoor.models import Booking


class WalletPasses:
    """E-tickets, as passes for the wallet on the customer's phone."""

    def __init__(self, api_key: str) -> None:
        self.service = fakewallet.PassService(api_key)

    def issue(self, booking: Booking) -> str | None:
        """Issue a pass for a booking's tickets, if it has any."""
        performances = sorted(
            {line.performance for line in booking.lines if line.performance}
        )
        tickets = sum(
            line.quantity for line in booking.lines if line.performance
        )
        if not tickets:
            return None
        try:
            return self.service.issue(
                holder=booking.customer.name,
                event=", ".join(performances),
                barcodes=[f"{booking.id}-{n}" for n in range(1, tickets + 1)],
            )
        except fakewallet.WalletError as error:
            raise FulfilmentError(str(error)) from error
