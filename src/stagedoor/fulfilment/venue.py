"""Holding seats in the venue's own box-office system.

This is the only module in StageDoor that knows the venue's API. It holds
the seats for every performance on a booking, and gives them back.
"""

import logging
import time
from collections import Counter

import fakevenue

from stagedoor.exceptions import FulfilmentError
from stagedoor.models import Booking

logger = logging.getLogger(__name__)


class VenueHolds:
    """Seats held for us in the venue's system."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.client = fakevenue.VenueClient(base_url, api_key)

    def hold(self, booking: Booking) -> tuple[str, ...]:
        """Hold the seats for every ticket on a booking.

        If the venue refuses any of them, the ones already held are given
        back, so a booking is either held in full or not at all.
        """
        seats: Counter[str] = Counter()
        for line in booking.lines:
            if line.performance is not None:
                seats[line.performance] += line.quantity

        holds: list[str] = []
        try:
            for performance, count in seats.items():
                # The venue's system is sometimes busy. Try again once.
                for attempt in (1, 2):
                    started = time.perf_counter()
                    try:
                        hold = self.client.create_hold(performance, count)
                        break
                    except fakevenue.VenueAPIError as error:
                        if error.status != 503 or attempt == 2:
                            raise
                        time.sleep(1.0)
                    finally:
                        elapsed = time.perf_counter() - started
                        logger.info("Venue hold took %.3fs", elapsed)
                holds.append(hold["holdRef"])
        except fakevenue.VenueAPIError as error:
            self.release(tuple(holds))
            raise FulfilmentError(
                f"the venue could not hold the seats ({error.message})"
            ) from error
        return tuple(holds)

    def release(self, holds: tuple[str, ...]) -> None:
        """Give held seats back to the venue."""
        for hold_ref in holds:
            try:
                self.client.cancel_hold(hold_ref)
            except fakevenue.VenueAPIError as error:
                raise FulfilmentError(
                    f"the venue could not release {hold_ref}"
                ) from error
