"""What StageDoor does with each command it is sent.

One function for each command. Each is handed the command, and then,
by keyword, only what it needs to carry it out - which bootstrap.py fills
in once, so the bus only ever passes the command. A handler returns the
events that happened, for the bus to pass on.
"""

from collections.abc import Callable, Mapping
from datetime import datetime

from stagedoor.catalogue import get_item
from stagedoor.commands import CancelBooking, CheckIn, MakeBooking, MarkPaid
from stagedoor.events import BookingConfirmed
from stagedoor.exceptions import (
    EmptyBookingError,
    InvalidQuantityError,
    MissingAddressError,
)
from stagedoor.fulfilment import Fulfilment
from stagedoor.models import (
    Booking,
    BookingLine,
    BookingStatus,
    PaymentStatus,
)
from stagedoor.notifications import Mailer
from stagedoor.payments import get_payment_method
from stagedoor.payments.base import PaymentMethod
from stagedoor.pricing import price_booking
from stagedoor.unit_of_work import UnitOfWork


def make_booking(
    command: MakeBooking,
    *,
    payment_methods: Mapping[str, PaymentMethod],
    fulfilment: Fulfilment,
    unit_of_work: Callable[[], UnitOfWork],
    mailer: Mailer,
    clock: Callable[[], datetime],
) -> list[object]:
    if not command.items:
        raise EmptyBookingError()
    if command.delivery == "post" and command.customer.address is None:
        raise MissingAddressError()

    method = get_payment_method(command.payment_method, payment_methods)
    lines = [_booking_line(code, quantity) for code, quantity in command.items]
    totals = price_booking(lines, command.discount_code, command.delivery)
    booking = Booking(
        id=command.booking_id,
        customer=command.customer,
        lines=tuple(lines),
        discount_code=command.discount_code,
        subtotal=totals.subtotal,
        discount=totals.discount,
        delivery=command.delivery,
        delivery_fee=totals.delivery_fee,
        total=totals.total,
        vat=totals.vat,
        payment_method=command.payment_method,
        payment_reference="",
        status=BookingStatus.AWAITING_PAYMENT,
        payment_fee=method.fee(totals.total),
        placed_at=clock(),
    )

    # The places and the booking are kept together, or not at all.
    with unit_of_work() as uow:
        uow.places.take(booking.lines)
        uow.bookings.add(booking)
        uow.commit()

    # Nobody else's system is called while a transaction is open.
    try:
        payment = method.charge(
            booking.total, booking.id, command.payment_token
        )
        booking.payment_reference = payment.reference
        if payment.status is PaymentStatus.PAID:
            booking.mark_paid()
            _issue_tickets(booking, fulfilment)
    except Exception:
        _call_off(booking, method, unit_of_work)
        raise

    with unit_of_work() as uow:
        uow.bookings.save(booking)
        uow.commit()

    mailer.send_confirmation(booking, method)
    return [
        BookingConfirmed(
            booking_id=booking.id,
            customer_email=booking.customer.email,
            total=booking.total,
            placed_at=booking.placed_at,
        )
    ]


def mark_paid(
    command: MarkPaid,
    *,
    fulfilment: Fulfilment,
    unit_of_work: Callable[[], UnitOfWork],
) -> list[object]:
    with unit_of_work() as uow:
        booking = uow.bookings.get(command.booking_id)
        booking.mark_paid()
        _issue_tickets(booking, fulfilment)
        uow.bookings.save(booking)
        uow.commit()
    return []


def check_in(
    command: CheckIn, *, unit_of_work: Callable[[], UnitOfWork]
) -> list[object]:
    with unit_of_work() as uow:
        booking = uow.bookings.get(command.booking_id)
        booking.check_in()
        uow.bookings.save(booking)
        uow.commit()
    return []


def cancel_booking(
    command: CancelBooking,
    *,
    payment_methods: Mapping[str, PaymentMethod],
    fulfilment: Fulfilment,
    unit_of_work: Callable[[], UnitOfWork],
) -> list[object]:
    with unit_of_work() as uow:
        booking = uow.bookings.get(command.booking_id)
        booking.cancel()
        if booking.status == BookingStatus.REFUNDED:
            # Seats first: if the venue says no, nothing has been given back.
            fulfilment.release(booking)
            method = get_payment_method(
                booking.payment_method, payment_methods
            )
            method.refund(booking.payment_reference, booking.total)
        uow.places.give_back(booking.lines)
        uow.bookings.save(booking)
        uow.commit()
    return []


def _issue_tickets(booking: Booking, fulfilment: Fulfilment) -> None:
    issued = fulfilment.fulfil(booking)
    booking.hold_references = issued.hold_references
    booking.wallet_pass = issued.wallet_pass
    booking.tracking_number = issued.tracking_number
    booking.invoice_number = issued.invoice_number


def _call_off(
    booking: Booking,
    method: PaymentMethod,
    unit_of_work: Callable[[], UnitOfWork],
) -> None:
    """Undo a booking whose payment, or tickets, fell through."""
    booking.cancel()
    if booking.status == BookingStatus.REFUNDED:
        method.refund(booking.payment_reference, booking.total)
    with unit_of_work() as uow:
        uow.places.give_back(booking.lines)
        uow.bookings.save(booking)
        uow.commit()


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
