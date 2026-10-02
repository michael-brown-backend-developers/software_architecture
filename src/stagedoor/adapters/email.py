"""Telling customers what has happened, by email.

Email goes through our email provider. Its library is used only here, and
its errors become StageDoor's. The stand-in provider delivers each message
as a text file in the mail directory, so you can read what was sent.
"""

import fakemailer

from stagedoor.application.ports import PaymentMethod
from stagedoor.domain.exceptions import EmailUnavailableError
from stagedoor.domain.models import Booking
from stagedoor.settings import Settings


class ProviderMailer:
    """Sends customers their email, through the email provider."""

    def __init__(self, client: fakemailer.EmailClient) -> None:
        self.client = client

    def send_confirmation(
        self, booking: Booking, payment_method: PaymentMethod
    ) -> None:
        """Send the customer a confirmation of their booking."""
        try:
            self.client.send(
                to=booking.customer.email,
                subject=f"Your StageDoor booking {booking.id}",
                text=_confirmation(booking, payment_method),
            )
        except fakemailer.ProviderError as error:
            raise EmailUnavailableError(error.message) from error


def create_mailer(settings: Settings) -> ProviderMailer:
    """The mailer for these settings."""
    return ProviderMailer(
        fakemailer.EmailClient(settings.mailer_api_key, settings.mail_dir)
    )


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
