"""Making bookings."""

from datetime import UTC, datetime
from uuid import uuid4

import fakestripe

from stagedoor.capacity import check_places, take_places
from stagedoor.catalogue import get_item
from stagedoor.exceptions import (
    EmptyBookingError,
    InvalidQuantityError,
    PaymentFailedError,
)
from stagedoor.models import Booking, BookingLine, Customer
from stagedoor.notifications import send_confirmation
from stagedoor.payments import get_payment_method
from stagedoor.pricing import price_booking
from stagedoor.storage import save_booking


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

    # Payment needs a reference before the booking exists, so the ID comes
    # first.
    booking_id = uuid4().hex[:12]
    method = get_payment_method(payment_method)

    lines = [_booking_line(code, quantity) for code, quantity in items]
    check_places(lines)
    totals = price_booking(lines, discount_code, delivery)

    # Take the payment, and tell the customer in plain words if it failed.
    try:
        result = method.charge(totals.total, booking_id, payment_token)
    except fakestripe.error.CardError as error:
        raise PaymentFailedError(error.user_message) from error
    if isinstance(result, dict):
        # PayPal answers with a dictionary, and a failure is not an error.
        if result["status"] != "COMPLETED":
            raise PaymentFailedError("PayPal declined the payment.")
        payment_reference = result["id"]
    else:
        payment_reference = result

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
        payment_reference=payment_reference,
        payment_fee=method.fee(totals.total),
        placed_at=datetime.now(UTC),
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
