"""Everything StageDoor can be asked to do, as plain data.

A command is a request, named in the imperative. It carries everything
needed to carry it out, as plain values, and nothing that does the work:
that is its handler's job. Each command has exactly one handler, and the
handler may refuse it.
"""

from dataclasses import dataclass, field
from uuid import uuid4

from stagedoor.domain.models import Customer


def new_booking_id() -> str:
    """A new, random booking ID: twelve hexadecimal digits."""
    return uuid4().hex[:12]


class Command:
    """Something StageDoor has been asked to do."""


@dataclass(frozen=True, kw_only=True)
class MakeBooking(Command):
    """Make a booking. ``items`` are (code, quantity) pairs.

    Whoever sends it knows the new booking's ID before it exists, so they
    can ask for the booking afterwards.
    """

    booking_id: str = field(default_factory=new_booking_id)
    customer: Customer
    items: tuple[tuple[str, int], ...]
    payment_method: str
    payment_token: str | None = None
    discount_code: str | None = None
    delivery: str = "e_ticket"


@dataclass(frozen=True)
class MarkPaid(Command):
    """The customer's bank transfer has arrived: issue their tickets."""

    booking_id: str


@dataclass(frozen=True)
class CheckIn(Command):
    """The customer is at the door: let them in."""

    booking_id: str


@dataclass(frozen=True)
class CancelBooking(Command):
    """Call a booking off. If it has been paid for, give the money back."""

    booking_id: str
