"""Holding seats in the venue's own box-office system.

This is the only module in StageDoor that knows the venue's API. It holds
the seats for every performance on a booking, and gives them back.
"""

import time
from collections import Counter
from collections.abc import Callable

import fakevenue

from stagedoor.exceptions import FulfilmentError, FulfilmentUnavailableError
from stagedoor.models import Booking
from stagedoor.resilience import retry, timed


class VenueHolds:
    """Seats held for us in the venue's system."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = fakevenue.VenueClient(base_url, api_key)
        # Wrapped here, where the adapter is built, so that whoever builds
        # it decides how long a retry waits.
        self._hold = timed("Venue hold")(
            retry(attempts=2, base_delay=1.0, sleep=sleep)(self._hold_once)
        )

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
                holds.append(self._hold(performance, count))
        except FulfilmentError:
            self.release(tuple(holds))
            raise
        return tuple(holds)

    def _hold_once(self, performance: str, count: int) -> str:
        try:
            return self.client.create_hold(performance, count)["holdRef"]
        except fakevenue.VenueAPIError as error:
            if error.status == 503:
                raise FulfilmentUnavailableError(
                    "the venue's system is not answering"
                ) from error
            raise FulfilmentError(
                f"the venue could not hold the seats ({error.message})"
            ) from error

    def release(self, holds: tuple[str, ...]) -> None:
        """Give held seats back to the venue."""
        for hold_ref in holds:
            try:
                self.client.cancel_hold(hold_ref)
            except fakevenue.VenueAPIError as error:
                raise FulfilmentError(
                    f"the venue could not release {hold_ref}"
                ) from error
