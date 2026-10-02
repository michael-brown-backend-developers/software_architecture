"""Telling the sales team about a booking they will want to know about.

Like a confirmation, an alert is a text file in the mail directory, which
comes from the STAGEDOOR_MAIL_DIR environment variable, or ./mail.
"""

import os
from decimal import Decimal
from pathlib import Path

from stagedoor.domain.events import BookingConfirmed

SALES_TEAM = "sales@stagedoor.example"

# The sales team like to ring anybody who spends more than this.
BIG_BOOKING = Decimal("500.00")


def _mail_dir() -> Path:
    directory = Path(os.environ.get("STAGEDOOR_MAIL_DIR", "mail"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def notify_sales_team(event: BookingConfirmed) -> None:
    """Tell the sales team about a big booking, so they can call."""
    if event.total <= BIG_BOOKING:
        return
    body = (
        f"To: {SALES_TEAM}\n"
        f"Subject: Big booking {event.booking_id}\n"
        f"\n"
        f"{event.customer_email} has just booked £{event.total} of tickets"
        f" and extras. Worth a call.\n"
    )
    path = _mail_dir() / f"{event.booking_id}-sales.txt"
    path.write_text(body, encoding="utf-8")
