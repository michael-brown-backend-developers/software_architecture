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
from stagedoor.repository import BookingRepository, PlaceRepository


@dataclass(frozen=True, kw_only=True)
class BookingService:
    """Everything StageDoor can do with a booking.

    It is handed everything it works with - even the clock, and where
    booking IDs come from - and reaches for nothing itself.
    """

    payment_methods: Mapping[str, PaymentMethod]
    fulfilment: Fulfilment
    bookings: BookingRepository
    places: PlaceRepository
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

        # Payment needs a reference before the booking exists, so the ID
        # comes first.
        booking_id = self.new_id()
        method = get_payment_method(payment_method, self.payment_methods)

        lines = [_booking_line(code, quantity) for code, quantity in items]
        self.places.check(lines)
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
            placed_at=self.clock(),
        )

        # Issue the tickets, now that they are paid for.
        if booking.status == BookingStatus.PAID:
            self._issue_tickets(booking)

        self.places.take(lines)
        self.bookings.add(booking)
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
        return self.bookings.get(booking_id)

    def mark_paid(self, booking_id: str) -> Booking:
        """The customer's bank transfer has arrived: issue their tickets."""
        booking = self.bookings.get(booking_id)
        booking.mark_paid()
        self._issue_tickets(booking)
        self.bookings.save(booking)
        return booking

    def check_in(self, booking_id: str) -> Booking:
        """The customer is at the door: let them in."""
        booking = self.bookings.get(booking_id)
        booking.check_in()
        self.bookings.save(booking)
        return booking

    def cancel(self, booking_id: str) -> Booking:
        """Call a booking off. If it has been paid for, give the money back."""
        booking = self.bookings.get(booking_id)
        booking.cancel()
        if booking.status == BookingStatus.REFUNDED:
            # Seats first: if the venue says no, nothing has been given back.
            self.fulfilment.release(booking)
            method = get_payment_method(
                booking.payment_method, self.payment_methods
            )
            method.refund(booking.payment_reference, booking.total)
        self.places.give_back(booking.lines)
        self.bookings.save(booking)
        return booking

    def _issue_tickets(self, booking: Booking) -> None:
        issued = self.fulfilment.fulfil(booking)
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
