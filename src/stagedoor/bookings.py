"""Making bookings."""

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import uuid4

from stagedoor.bus import EventBus
from stagedoor.capacity import check_places, give_back_places, take_places
from stagedoor.catalogue import get_item
from stagedoor.events import BookingConfirmed
from stagedoor.exceptions import (
    BookingStatusError,
    EmptyBookingError,
    InvalidQuantityError,
    MissingAddressError,
)
from stagedoor.fulfilment import Fulfilment
from stagedoor.models import (
    Booking,
    BookingLine,
    BookingStatus,
    Customer,
    PaymentStatus,
)
from stagedoor.notifications import send_confirmation
from stagedoor.payments import get_payment_method
from stagedoor.payments.base import PaymentMethod
from stagedoor.pricing import price_booking
from stagedoor.storage import load_booking, save_booking


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
        status=(
            BookingStatus.PAID
            if payment.status is PaymentStatus.PAID
            else BookingStatus.AWAITING_PAYMENT
        ),
        payment_fee=method.fee(totals.total),
        placed_at=datetime.now(UTC),
    )

    # Issue the tickets, now that they are paid for.
    if booking.status == BookingStatus.PAID:
        _issue_tickets(booking, fulfilment)

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


def mark_paid(booking_id: str, *, fulfilment: Fulfilment) -> Booking:
    """The customer's bank transfer has arrived: issue their tickets."""
    booking = load_booking(booking_id)
    if booking.status != BookingStatus.AWAITING_PAYMENT:
        raise BookingStatusError(booking.id, "is not waiting to be paid")
    booking.status = BookingStatus.PAID
    _issue_tickets(booking, fulfilment)
    save_booking(booking)
    return booking


def check_in(booking_id: str) -> Booking:
    """The customer is at the door: let them in."""
    booking = load_booking(booking_id)
    if booking.status == BookingStatus.CHECKED_IN:
        raise BookingStatusError(booking.id, "has already been checked in")
    if booking.status in (BookingStatus.CANCELLED, BookingStatus.REFUNDED):
        raise BookingStatusError(booking.id, "has been cancelled")
    booking.status = BookingStatus.CHECKED_IN
    save_booking(booking)
    return booking


def cancel_booking(
    booking_id: str,
    *,
    payment_methods: Mapping[str, PaymentMethod],
    fulfilment: Fulfilment,
) -> Booking:
    """Call a booking off. If it has been paid for, give the money back."""
    booking = load_booking(booking_id)
    if booking.status == BookingStatus.CHECKED_IN:
        raise BookingStatusError(booking.id, "has already been used")
    if booking.status in (BookingStatus.CANCELLED, BookingStatus.REFUNDED):
        raise BookingStatusError(booking.id, "has already been cancelled")
    if booking.status == BookingStatus.PAID:
        method = get_payment_method(booking.payment_method, payment_methods)
        method.refund(booking.payment_reference, booking.total)
        fulfilment.release(booking)
        booking.status = BookingStatus.REFUNDED
    else:
        booking.status = BookingStatus.CANCELLED
    give_back_places(booking.lines)
    save_booking(booking)
    return booking


def _issue_tickets(booking: Booking, fulfilment: Fulfilment) -> None:
    issued = fulfilment.fulfil(booking)
    booking.hold_references = issued.hold_references
    booking.wallet_pass = issued.wallet_pass
    booking.tracking_number = issued.tracking_number
    booking.invoice_number = issued.invoice_number


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
