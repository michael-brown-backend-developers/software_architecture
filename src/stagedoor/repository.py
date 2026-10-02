"""Where bookings and places are kept, as far as the rest of StageDoor knows.

A repository looks like a collection: put a booking in, and get it back by
its ID; take places, and give them back. Where they really live - a
database, or a dictionary in a test - is the business of whichever
repository StageDoor is given.
"""

from collections.abc import Sequence
from typing import Protocol

from stagedoor.models import Booking, BookingLine


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


class PlaceRepository(Protocol):
    """The places left for every performance."""

    def check(self, lines: Sequence[BookingLine]) -> None:
        """Raise NotEnoughPlacesError unless every performance has room."""
        ...

    def take(self, lines: Sequence[BookingLine]) -> None:
        """Take the places off sale. Call check() first."""
        ...

    def give_back(self, lines: Sequence[BookingLine]) -> None:
        """Put the places back on sale."""
        ...
