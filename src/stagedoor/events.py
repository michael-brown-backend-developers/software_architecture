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
    """A booking has been made, and the customer has been told."""

    booking_id: str
    customer_email: str
    total: Decimal
    placed_at: datetime
