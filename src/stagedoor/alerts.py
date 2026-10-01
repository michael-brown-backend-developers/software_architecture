"""Telling the sales team about a booking they will want to know about.

Like a confirmation, an alert is a text file in the mail directory, which
comes from the STAGEDOOR_MAIL_DIR environment variable, or ./mail.
"""

import os
from pathlib import Path

from stagedoor.models import Booking

SALES_TEAM = "sales@stagedoor.example"


def _mail_dir() -> Path:
    directory = Path(os.environ.get("STAGEDOOR_MAIL_DIR", "mail"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def notify_sales_team(booking: Booking) -> None:
    """Send the sales team the details of a booking, so they can call."""
    body = (
        f"To: {SALES_TEAM}\n"
        f"Subject: Big booking {booking.id}\n"
        f"\n"
        f"{booking.customer.name} <{booking.customer.email}> has just booked"
        f" £{booking.total} of tickets and extras. Worth a call.\n"
    )
    path = _mail_dir() / f"{booking.id}-sales.txt"
    path.write_text(body, encoding="utf-8")
