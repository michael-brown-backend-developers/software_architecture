"""Where bookings are kept, as far as the rest of StageDoor knows.

A repository looks like a collection of bookings: put one in, and get it
back by its ID. Where they really live - a database, or a dictionary in a
test - is the business of whichever repository StageDoor is given.
"""

from typing import Protocol

from stagedoor.models import Booking


class BookingRepository(Protocol):
    """Every booking StageDoor has made."""

    def add(self, booking: Booking) -> None:
        """Keep a new booking."""
        ...

    def get(self, booking_id: str) -> Booking:
        """The booking with this ID. Raise BookingNotFoundError if none."""
        ...

    def save(self, booking: Booking) -> None:
        """Keep the changes to a booking that was already added."""
        ...
