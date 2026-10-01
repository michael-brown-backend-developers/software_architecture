"""Making bookings."""

import os
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import fakeroyalmail
import fakevenue
import fakewallet

from stagedoor.capacity import check_places, take_places
from stagedoor.catalogue import get_item
from stagedoor.delivery import shipping_region
from stagedoor.exceptions import (
    EmptyBookingError,
    InvalidQuantityError,
    MissingAddressError,
)
from stagedoor.invoicing import create_invoice
from stagedoor.models import Booking, BookingLine, Customer, PaymentStatus
from stagedoor.notifications import send_confirmation
from stagedoor.payments import get_payment_method
from stagedoor.pricing import price_booking
from stagedoor.storage import save_booking

# Royal Mail's service codes, by where the tickets are going.
ROYAL_MAIL_SERVICES = {"UK": "TPN48", "EU": "INT-EU", "WORLD": "INT-ROW"}


def place_booking(
    customer: Customer,
    items: list[tuple[str, int]],
    payment_method: str,
    payment_token: str | None = None,
    discount_code: str | None = None,
    delivery: str = "e_ticket",
) -> Booking:
    """Make a booking for a customer.

    ``items`` is a list of (code, quantity) pairs.
    """
    if not items:
        raise EmptyBookingError()
    address = customer.address
    if delivery == "post" and address is None:
        raise MissingAddressError()

    # Payment needs a reference before the booking exists, so the ID comes
    # first.
    booking_id = uuid4().hex[:12]
    method = get_payment_method(payment_method)

    lines = [_booking_line(code, quantity) for code, quantity in items]
    check_places(lines)
    totals = price_booking(lines, discount_code, delivery)
    payment = method.charge(totals.total, booking_id, payment_token)

    booking = Booking(
        id=booking_id,
        customer=customer,
        lines=tuple(lines),
        discount_code=discount_code,
        subtotal=totals.subtotal,
        discount=totals.discount,
        delivery=delivery,
        delivery_fee=totals.delivery_fee,
        total=totals.total,
        vat=totals.vat,
        payment_method=payment_method,
        payment_reference=payment.reference,
        payment_status=payment.status,
        payment_fee=method.fee(totals.total),
        placed_at=datetime.now(UTC),
    )

    # Issue the tickets, now that they are paid for: hold the seats at the
    # venue, get the tickets to the customer, and invoice the booking.
    if payment.status is PaymentStatus.PAID:
        venue = fakevenue.VenueClient(
            os.environ.get("VENUE_URL", "https://boxoffice.example"),
            os.environ.get("VENUE_API_KEY", "venue-test-key"),
        )
        seats: Counter[str] = Counter()
        for line in lines:
            if line.performance is not None:
                seats[line.performance] += line.quantity
        holds = []
        for performance, count in seats.items():
            hold = venue.create_hold(performance, count)
            holds.append(hold["holdRef"])

        wallet_pass = tracking_number = None
        try:
            if delivery == "e_ticket" and seats:
                passes = fakewallet.PassService(
                    os.environ.get("WALLET_API_KEY", "wallet-test-key")
                )
                wallet_pass = passes.issue(
                    holder=customer.name,
                    event=", ".join(sorted(seats)),
                    barcodes=[
                        f"{booking_id}-{n}"
                        for n in range(1, sum(seats.values()) + 1)
                    ],
                )
            elif delivery == "post":
                assert address is not None  # checked before payment
                royal_mail = fakeroyalmail.RoyalMailClient(
                    os.environ.get("ROYAL_MAIL_API_KEY", "rm-test-key")
                )
                tracking_number = royal_mail.create_shipment(
                    weight_grams=sum(
                        get_item(line.code).weight_grams * line.quantity
                        for line in lines
                    ),
                    postcode=address.postcode,
                    country=address.country,
                    service=ROYAL_MAIL_SERVICES[
                        shipping_region(address.country)
                    ],
                )
        except fakewallet.WalletError, fakeroyalmail.RoyalMailError:
            # The tickets did not go out, so give the seats back.
            for hold_ref in holds:
                venue.cancel_hold(hold_ref)
            raise

        booking = replace(
            booking,
            hold_references=tuple(holds),
            wallet_pass=wallet_pass,
            tracking_number=tracking_number,
            invoice_number=create_invoice(booking),
        )

    take_places(lines)
    save_booking(booking)
    send_confirmation(booking)

    return booking


def _booking_line(code: str, quantity: int) -> BookingLine:
    if quantity < 1:
        raise InvalidQuantityError(code, quantity)
    item = get_item(code)
    return BookingLine(
        code=item.code,
        name=item.name,
        kind=item.kind,
        performance=item.performance,
        unit_price=item.price,
        quantity=quantity,
    )
