"""Telling customers what has happened.

StageDoor does not send real email yet. Each "email" is a text file in the
mail directory, which comes from the STAGEDOOR_MAIL_DIR environment
variable, or ./mail if it is not set. Open the file and you can see exactly
what the customer would have received.
"""

import os
from pathlib import Path

from stagedoor.models import Booking


def _mail_dir() -> Path:
    directory = Path(os.environ.get("STAGEDOOR_MAIL_DIR", "mail"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def send_confirmation(booking: Booking) -> None:
    """Send the customer a confirmation of their booking."""
    lines = "\n".join(
        f"  {line.quantity} x {line.name} @ £{line.unit_price}"
        f" = £{line.line_total}"
        for line in booking.lines
    )
    discount = ""
    if booking.discount:
        discount = (
            f"Discount ({booking.discount_code}): -£{booking.discount}\n"
        )
    body = (
        f"To: {booking.customer.email}\n"
        f"Subject: Your StageDoor booking {booking.id}\n"
        f"\n"
        f"Hi {booking.customer.name},\n"
        f"\n"
        f"Thanks for booking with us. Here is what you bought:\n"
        f"\n"
        f"{lines}\n"
        f"\n"
        f"Subtotal: £{booking.subtotal}\n"
        f"{discount}"
        f"Total: £{booking.total} (includes VAT of £{booking.vat})\n"
    )
    path = _mail_dir() / f"{booking.id}-confirmation.txt"
    path.write_text(body, encoding="utf-8")
