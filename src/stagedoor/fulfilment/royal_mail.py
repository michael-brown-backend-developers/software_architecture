"""Posting tickets with Royal Mail.

This is the only module in StageDoor that knows Royal Mail's API. It works
out what Royal Mail needs - the weight, the postcode and country, and the
right service code - and turns Royal Mail's errors into ours.
"""

import logging
import time

import fakeroyalmail

from stagedoor.catalogue import get_item
from stagedoor.delivery import shipping_region
from stagedoor.exceptions import FulfilmentError, MissingAddressError
from stagedoor.models import Booking

# Royal Mail's service codes, by where the tickets are going.
SERVICES = {"UK": "TPN48", "EU": "INT-EU", "WORLD": "INT-ROW"}

logger = logging.getLogger(__name__)


class RoyalMailShipping:
    """Posted tickets, sent by Royal Mail."""

    def __init__(self, api_key: str) -> None:
        self.client = fakeroyalmail.RoyalMailClient(api_key)

    def post(self, booking: Booking) -> str:
        """Book the postage for a booking, and return the tracking number."""
        address = booking.customer.address
        if address is None:
            raise MissingAddressError()
        weight = sum(
            get_item(line.code).weight_grams * line.quantity
            for line in booking.lines
        )
        # Royal Mail has a bad hour most Mondays. Try three times.
        for attempt in range(1, 4):
            started = time.perf_counter()
            try:
                tracking_number = self.client.create_shipment(
                    weight_grams=weight,
                    postcode=address.postcode,
                    country=address.country,
                    service=SERVICES[shipping_region(address.country)],
                )
                break
            except fakeroyalmail.RoyalMailError as error:
                if attempt == 3:
                    raise FulfilmentError(str(error)) from error
                time.sleep(0.5)
            finally:
                elapsed = time.perf_counter() - started
                logger.info("Royal Mail shipment took %.3fs", elapsed)
        return tracking_number
