"""Making bookings, and everything that happens to them afterwards."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from stagedoor.bus import EventBus
from stagedoor.catalogue import get_item
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
    Customer,
    PaymentStatus,
)
from stagedoor.notifications import Mailer
from stagedoor.payments import get_payment_method
from stagedoor.payments.base import PaymentMethod
from stagedoor.pricing import price_booking
from stagedoor.unit_of_work import UnitOfWork


@dataclass(frozen=True, kw_only=True)
class BookingService:
    """Everything StageDoor can do with a booking.

    It is handed everything it works with - even the clock, and where
    booking IDs come from - and reaches for nothing itself. Each thing it
    does to bookings and places is a unit of work: kept whole, or not at
    all.
    """

    payment_methods: Mapping[str, PaymentMethod]
    fulfilment: Fulfilment
    unit_of_work: Callable[[], UnitOfWork]
    mailer: Mailer
    bus: EventBus
    clock: Callable[[], datetime]
    new_id: Callable[[], str]

    def place(
        self,
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

        method = get_payment_method(payment_method, self.payment_methods)
        lines = [_booking_line(code, quantity) for code, quantity in items]
        totals = price_booking(lines, discount_code, delivery)
        booking = Booking(
            id=self.new_id(),
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
            payment_reference="",
            status=BookingStatus.AWAITING_PAYMENT,
            payment_fee=method.fee(totals.total),
            placed_at=self.clock(),
        )

        # The places and the booking are kept together, or not at all.
        with self.unit_of_work() as uow:
            uow.places.take(booking.lines)
            uow.bookings.add(booking)
            uow.commit()

        # Nobody else's system is called while a transaction is open.
        try:
            payment = method.charge(booking.total, booking.id, payment_token)
            booking.payment_reference = payment.reference
            if payment.status is PaymentStatus.PAID:
                booking.mark_paid()
                self._issue_tickets(booking)
        except Exception:
            self._call_off(booking, method)
            raise

        with self.unit_of_work() as uow:
            uow.bookings.save(booking)
            uow.commit()

        self.mailer.send_confirmation(booking, method)
        self.bus.publish(
            BookingConfirmed(
                booking_id=booking.id,
                customer_email=customer.email,
                total=booking.total,
                placed_at=booking.placed_at,
            )
        )

        return booking

    def get(self, booking_id: str) -> Booking:
        """The booking with this ID."""
        with self.unit_of_work() as uow:
            return uow.bookings.get(booking_id)

    def mark_paid(self, booking_id: str) -> Booking:
        """The customer's bank transfer has arrived: issue their tickets."""
        with self.unit_of_work() as uow:
            booking = uow.bookings.get(booking_id)
            booking.mark_paid()
            self._issue_tickets(booking)
            uow.bookings.save(booking)
            uow.commit()
        return booking

    def check_in(self, booking_id: str) -> Booking:
        """The customer is at the door: let them in."""
        with self.unit_of_work() as uow:
            booking = uow.bookings.get(booking_id)
            booking.check_in()
            uow.bookings.save(booking)
            uow.commit()
        return booking

    def cancel(self, booking_id: str) -> Booking:
        """Call a booking off. If it has been paid for, give the money back."""
        with self.unit_of_work() as uow:
            booking = uow.bookings.get(booking_id)
            booking.cancel()
            if booking.status == BookingStatus.REFUNDED:
                # Seats first: if the venue says no, nothing has been given
                # back.
                self.fulfilment.release(booking)
                method = get_payment_method(
                    booking.payment_method, self.payment_methods
                )
                method.refund(booking.payment_reference, booking.total)
            uow.places.give_back(booking.lines)
            uow.bookings.save(booking)
            uow.commit()
        return booking

    def _issue_tickets(self, booking: Booking) -> None:
        issued = self.fulfilment.fulfil(booking)
        booking.hold_references = issued.hold_references
        booking.wallet_pass = issued.wallet_pass
        booking.tracking_number = issued.tracking_number
        booking.invoice_number = issued.invoice_number

    def _call_off(self, booking: Booking, method: PaymentMethod) -> None:
        """Undo a booking whose payment, or tickets, fell through."""
        booking.cancel()
        if booking.status == BookingStatus.REFUNDED:
            method.refund(booking.payment_reference, booking.total)
        with self.unit_of_work() as uow:
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
