"""Posting tickets with Royal Mail.

This is the only module in StageDoor that knows Royal Mail's API. It works
out what Royal Mail needs - the weight, the postcode and country, and the
right service code - and turns Royal Mail's errors into ours.
"""

import fakeroyalmail

from stagedoor.catalogue import get_item
from stagedoor.delivery import shipping_region
from stagedoor.exceptions import (
    FulfilmentError,
    FulfilmentUnavailableError,
    MissingAddressError,
)
from stagedoor.models import Booking
from stagedoor.resilience import retry, timed

# Royal Mail's service codes, by where the tickets are going.
SERVICES = {"UK": "TPN48", "EU": "INT-EU", "WORLD": "INT-ROW"}


class RoyalMailShipping:
    """Posted tickets, sent by Royal Mail."""

    def __init__(self, api_key: str) -> None:
        self.client = fakeroyalmail.RoyalMailClient(api_key)

    @timed("Royal Mail shipment")
    @retry(attempts=3, base_delay=0.5)
    def post(self, booking: Booking) -> str:
        """Book the postage for a booking, and return the tracking number."""
        address = booking.customer.address
        if address is None:
            raise MissingAddressError()
        weight = sum(
            get_item(line.code).weight_grams * line.quantity
            for line in booking.lines
        )
        try:
            return self.client.create_shipment(
                weight_grams=weight,
                postcode=address.postcode,
                country=address.country,
                service=SERVICES[shipping_region(address.country)],
            )
        except fakeroyalmail.RoyalMailError as error:
            if error.temporary:
                raise FulfilmentUnavailableError(str(error)) from error
            raise FulfilmentError(str(error)) from error
