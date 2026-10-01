"""Telling customers what has happened.

StageDoor does not send real email yet. Each "email" is a text file in a
mail directory. Open the file and you can see exactly what the customer
would have received.
"""

from pathlib import Path

from stagedoor.models import Booking
from stagedoor.payments.base import PaymentMethod


class Mailer:
    """Sends customers their email, as files in one directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def send_confirmation(
        self, booking: Booking, payment_method: PaymentMethod
    ) -> None:
        """Send the customer a confirmation of their booking."""
        body = _confirmation(booking, payment_method)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{booking.id}-confirmation.txt"
        path.write_text(body, encoding="utf-8")


def _confirmation(booking: Booking, payment_method: PaymentMethod) -> str:
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

    payment = payment_method.describe(booking)

    return (
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
