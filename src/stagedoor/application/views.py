"""Answering questions about bookings, without changing anything.

A command asks StageDoor to do something, and returns nothing. A question
is answered here, and changes nothing.
"""

from collections.abc import Callable

from stagedoor.application.ports import UnitOfWork
from stagedoor.domain.models import Booking


def booking(
    booking_id: str, unit_of_work: Callable[[], UnitOfWork]
) -> Booking:
    """The booking with this ID."""
    with unit_of_work() as uow:
        return uow.bookings.get(booking_id)
