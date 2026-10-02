"""Issuing a paid booking's tickets.

One call does everything that has to happen once a booking is paid for:
hold the seats at the venue, get the tickets to the customer, and invoice
the booking. If the tickets cannot be issued, the seats are given back.
"""

from stagedoor.adapters.fulfilment.invoicing import create_invoice
from stagedoor.adapters.fulfilment.royal_mail import RoyalMailShipping
from stagedoor.adapters.fulfilment.venue import VenueHolds
from stagedoor.adapters.fulfilment.wallet import WalletPasses
from stagedoor.application.ports import FulfilmentResult
from stagedoor.domain.exceptions import FulfilmentError
from stagedoor.domain.models import Booking


class VenueFulfilment:
    """Fulfilment through the venue, the wallet service and Royal Mail."""

    def __init__(
        self,
        venue: VenueHolds,
        wallet: WalletPasses,
        royal_mail: RoyalMailShipping,
    ) -> None:
        self.venue = venue
        self.wallet = wallet
        self.royal_mail = royal_mail

    def fulfil(self, booking: Booking) -> FulfilmentResult:
        """Hold the seats, get the tickets out, and invoice the booking."""
        holds = self.venue.hold(booking)
        wallet_pass = tracking_number = None
        try:
            if booking.delivery == "e_ticket":
                wallet_pass = self.wallet.issue(booking)
            elif booking.delivery == "post":
                tracking_number = self.royal_mail.post(booking)
        except FulfilmentError:
            # The tickets did not go out, so give the seats back.
            self.venue.release(holds)
            raise
        return FulfilmentResult(
            hold_references=holds,
            wallet_pass=wallet_pass,
            tracking_number=tracking_number,
            invoice_number=create_invoice(booking),
        )

    def release(self, booking: Booking) -> None:
        """Give a cancelled booking's seats back to the venue."""
        self.venue.release(booking.hold_references)
