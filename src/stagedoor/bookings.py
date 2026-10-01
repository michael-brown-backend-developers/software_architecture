"""Making bookings."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from stagedoor.bus import EventBus
from stagedoor.capacity import check_places, take_places
from stagedoor.catalogue import get_item
from stagedoor.events import BookingConfirmed
from stagedoor.exceptions import (
    EmptyBookingError,
    InvalidQuantityError,
    MissingAddressError,
)
from stagedoor.fulfilment import Fulfilment
from stagedoor.models import Booking, BookingLine, Customer, PaymentStatus
from stagedoor.notifications import send_confirmation
from stagedoor.payments import get_payment_method
from stagedoor.payments.base import PaymentMethod
from stagedoor.pricing import price_booking
from stagedoor.storage import save_booking


def place_booking(
    customer: Customer,
    items: list[tuple[str, int]],
    payment_method: str,
    payment_token: str | None = None,
    discount_code: str | None = None,
    delivery: str = "e_ticket",
    *,
    payment_methods: Mapping[str, PaymentMethod],
    fulfilment: Fulfilment,
    bus: EventBus,
) -> Booking:
    """Make a booking for a customer.

    ``items`` is a list of (code, quantity) pairs. ``payment_methods`` are
    the ways of paying that are switched on, ``fulfilment`` issues the
    tickets once a booking is paid for, and ``bus`` tells everything else
    that is interested that the booking has been made.
    """
    if not items:
        raise EmptyBookingError()
    address = customer.address
    if delivery == "post" and address is None:
        raise MissingAddressError()

    # Payment needs a reference before the booking exists, so the ID comes
    # first.
    booking_id = uuid4().hex[:12]
    method = get_payment_method(payment_method, payment_methods)

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

    # Issue the tickets, now that they are paid for.
    if payment.status is PaymentStatus.PAID:
        issued = fulfilment.fulfil(booking)
        booking = replace(
            booking,
            hold_references=issued.hold_references,
            wallet_pass=issued.wallet_pass,
            tracking_number=issued.tracking_number,
            invoice_number=issued.invoice_number,
        )

    take_places(lines)
    save_booking(booking)
    send_confirmation(booking, method)
    bus.publish(
        BookingConfirmed(
            booking_id=booking.id,
            customer_email=customer.email,
            total=booking.total,
            placed_at=booking.placed_at,
        )
    )

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
