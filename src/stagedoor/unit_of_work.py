"""Changes that are kept together, or not at all.

A unit of work is one business transaction: everything one thing StageDoor
does changes in its bookings and places. Nothing is kept until commit() is
called. Leave the with block without committing - because something went
wrong, or because nobody said to - and every change is undone.
"""

from typing import Protocol, Self

from stagedoor.outbox import Outbox
from stagedoor.repository import BookingRepository, PlaceRepository


class UnitOfWork(Protocol):
    """One transaction's worth of changes to bookings, places and events."""

    @property
    def bookings(self) -> BookingRepository: ...

    @property
    def places(self) -> PlaceRepository: ...

    @property
    def outbox(self) -> Outbox: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, *exc: object) -> None:
        """Undo anything that was not committed."""
        ...

    def commit(self) -> None:
        """Keep every change made so far."""
        ...

    def rollback(self) -> None:
        """Undo every change since the last commit."""
        ...
