"""Making bookings."""

from datetime import UTC, datetime
from uuid import uuid4

from stagedoor.capacity import check_places, take_places
from stagedoor.catalogue import get_item
from stagedoor.exceptions import EmptyBookingError, InvalidQuantityError
from stagedoor.models import Booking, BookingLine, Customer
from stagedoor.notifications import send_confirmation
from stagedoor.pricing import price_booking
from stagedoor.storage import save_booking


def place_booking(
    customer: Customer,
    items: list[tuple[str, int]],
    discount_code: str | None = None,
) -> Booking:
    """Make a booking for a customer.

    ``items`` is a list of (code, quantity) pairs.
    """
    if not items:
        raise EmptyBookingError()

    lines = [_booking_line(code, quantity) for code, quantity in items]
    check_places(lines)
    totals = price_booking(lines, discount_code)

    booking = Booking(
        id=uuid4().hex[:12],
        customer=customer,
        lines=tuple(lines),
        discount_code=discount_code,
        subtotal=totals.subtotal,
        discount=totals.discount,
        total=totals.total,
        vat=totals.vat,
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
