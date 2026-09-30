"""Telling customers what has happened.

StageDoor does not send real email yet. Each "email" is a text file in the
mail directory, which comes from the STAGEDOOR_MAIL_DIR environment
variable, or ./mail if it is not set. Open the file and you can see exactly
what the customer would have received.
"""

import os
from pathlib import Path

from stagedoor.exceptions import UnknownPaymentMethodError
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

    if booking.payment_method == "card":
        payment = "Paid by card."
    elif booking.payment_method == "paypal":
        payment = "Paid with PayPal."
    elif booking.payment_method == "bank_transfer":
        payment = (
            f"Please pay £{booking.total} by bank transfer to sort code "
            f"12-34-56, account 12345678, quoting {booking.payment_reference}."
        )
    else:
        raise UnknownPaymentMethodError(booking.payment_method)

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
        f"Delivery ({booking.delivery}): £{booking.delivery_fee}\n"
        f"Total: £{booking.total} (includes VAT of £{booking.vat})\n"
        f"\n"
        f"{payment}\n"
    )
    path = _mail_dir() / f"{booking.id}-confirmation.txt"
    path.write_text(body, encoding="utf-8")
