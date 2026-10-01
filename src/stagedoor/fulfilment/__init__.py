"""Issuing a paid booking's tickets.

One call does everything that has to happen once a booking is paid for:
hold the seats at the venue, get the tickets to the customer, and invoice
the booking. If the tickets cannot be issued, the seats are given back.
"""

from dataclasses import dataclass

from stagedoor.exceptions import FulfilmentError
from stagedoor.fulfilment.royal_mail import RoyalMailShipping
from stagedoor.fulfilment.venue import VenueHolds
from stagedoor.fulfilment.wallet import WalletPasses
from stagedoor.invoicing import create_invoice
from stagedoor.models import Booking
from stagedoor.settings import Settings


@dataclass(frozen=True)
class FulfilmentResult:
    """What issuing a booking's tickets produced."""

    hold_references: tuple[str, ...]
    wallet_pass: str | None
    tracking_number: str | None
    invoice_number: str


class Fulfilment:
    """Everything that happens to a booking once it is paid for."""

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


def create_fulfilment(settings: Settings) -> Fulfilment:
    """Build the facade, and every adapter behind it, from the settings."""
    return Fulfilment(
        venue=VenueHolds(settings.venue_url, settings.venue_api_key),
        wallet=WalletPasses(settings.wallet_api_key),
        royal_mail=RoyalMailShipping(settings.royal_mail_api_key),
    )
