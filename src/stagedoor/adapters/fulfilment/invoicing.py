"""Invoices, for the accountants.

Every paid booking gets the next invoice number - INV-000001, INV-000002,
and so on, with no gaps - and a text invoice in the invoices directory,
next to the bookings. The last number used is kept in a file there.
"""

import os
from pathlib import Path

from stagedoor.domain.models import Booking


def _invoices_dir() -> Path:
    directory = Path(os.environ.get("STAGEDOOR_DATA_DIR", "data")) / "invoices"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _next_number() -> int:
    counter = _invoices_dir() / "last-number.txt"
    last = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(last + 1))
    return last + 1


def create_invoice(booking: Booking) -> str:
    """Write an invoice for a booking, and return its number."""
    number = f"INV-{_next_number():06d}"
    lines = "\n".join(
        f"{line.quantity} x {line.name} = £{line.line_total}"
        for line in booking.lines
    )
    text = (
        f"Invoice {number}\n"
        f"Booking {booking.id}, for {booking.customer.name}\n"
        f"\n"
        f"{lines}\n"
        f"Delivery ({booking.delivery}): £{booking.delivery_fee}\n"
        f"Discount: -£{booking.discount}\n"
        f"Total: £{booking.total}, including VAT of £{booking.vat}\n"
    )
    (_invoices_dir() / f"{number}.txt").write_text(text, encoding="utf-8")
    return number
