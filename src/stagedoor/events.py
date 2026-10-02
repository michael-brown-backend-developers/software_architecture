"""Things that have happened in StageDoor, for anything that wants to know.

An event is a fact, named in the past tense. It carries what a handler
needs to know about what happened, as plain values, and it cannot be
changed once it has been made.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class BookingConfirmed:
    """A booking has been made, and paid for if it was paid for by card."""

    booking_id: str
    customer_email: str
    total: Decimal
    placed_at: datetime


# Every event, by name, so that one can be stored and read back.
EVENTS: dict[str, type] = {"BookingConfirmed": BookingConfirmed}
