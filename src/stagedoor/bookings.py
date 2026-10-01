"""Making bookings, and everything that happens to them afterwards."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from stagedoor.bus import EventBus
from stagedoor.capacity import check_places, give_back_places, take_places
from stagedoor.catalogue import get_item
from stagedoor.db import BookingLineRow, BookingRow
from stagedoor.events import BookingConfirmed
from stagedoor.exceptions import (
    BookingNotFoundError,
    EmptyBookingError,
    InvalidQuantityError,
    MissingAddressError,
)
from stagedoor.fulfilment import Fulfilment
from stagedoor.models import (
    Address,
    Booking,
    BookingLine,
    BookingStatus,
    Customer,
    ItemKind,
    PaymentStatus,
)
from stagedoor.notifications import Mailer
from stagedoor.payments import get_payment_method
from stagedoor.payments.base import PaymentMethod
from stagedoor.pricing import price_booking


@dataclass(frozen=True, kw_only=True)
class BookingService:
    """Everything StageDoor can do with a booking.

    It is handed everything it works with - even the clock, and where
    booking IDs come from - and reaches for nothing itself.
    """

    payment_methods: Mapping[str, PaymentMethod]
    fulfilment: Fulfilment
    sessions: sessionmaker[Session]
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
            placed_at=self.clock(),
        )

        # Issue the tickets, now that they are paid for.
        if booking.status == BookingStatus.PAID:
            self._issue_tickets(booking)

        take_places(lines)
        with self.sessions() as session:
            session.add(_to_row(booking))
            session.commit()
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
        with self.sessions() as session:
            return _to_booking(_load_row(session, booking_id))

    def mark_paid(self, booking_id: str) -> Booking:
        """The customer's bank transfer has arrived: issue their tickets."""
        with self.sessions() as session:
            row = _load_row(session, booking_id)
            booking = _to_booking(row)
            booking.mark_paid()
            self._issue_tickets(booking)
            _update_row(row, booking)
            session.commit()
        return booking

    def check_in(self, booking_id: str) -> Booking:
        """The customer is at the door: let them in."""
        with self.sessions() as session:
            row = _load_row(session, booking_id)
            booking = _to_booking(row)
            booking.check_in()
            _update_row(row, booking)
            session.commit()
        return booking

    def cancel(self, booking_id: str) -> Booking:
        """Call a booking off. If it has been paid for, give the money back."""
        with self.sessions() as session:
            row = _load_row(session, booking_id)
            booking = _to_booking(row)
            booking.cancel()
            if booking.status == BookingStatus.REFUNDED:
                # Seats first: if the venue says no, nothing is given back.
                self.fulfilment.release(booking)
                method = get_payment_method(
                    booking.payment_method, self.payment_methods
                )
                method.refund(booking.payment_reference, booking.total)
            give_back_places(booking.lines)
            _update_row(row, booking)
            session.commit()
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


def _load_row(session: Session, booking_id: str) -> BookingRow:
    row = session.get(BookingRow, booking_id)
    if row is None:
        raise BookingNotFoundError(booking_id)
    return row


def _to_row(booking: Booking) -> BookingRow:
    address = booking.customer.address
    return BookingRow(
        id=booking.id,
        customer_name=booking.customer.name,
        customer_email=booking.customer.email,
        address_line1=address.line1 if address else None,
        address_city=address.city if address else None,
        address_postcode=address.postcode if address else None,
        address_country=address.country if address else None,
        discount_code=booking.discount_code,
        subtotal=booking.subtotal,
        discount=booking.discount,
        delivery=booking.delivery,
        delivery_fee=booking.delivery_fee,
        total=booking.total,
        vat=booking.vat,
        payment_method=booking.payment_method,
        payment_reference=booking.payment_reference,
        status=booking.status.value,
        payment_fee=booking.payment_fee,
        placed_at=booking.placed_at,
        hold_references=list(booking.hold_references),
        wallet_pass=booking.wallet_pass,
        tracking_number=booking.tracking_number,
        invoice_number=booking.invoice_number,
        lines=[
            BookingLineRow(
                code=line.code,
                name=line.name,
                kind=line.kind.value,
                performance=line.performance,
                unit_price=line.unit_price,
                quantity=line.quantity,
            )
            for line in booking.lines
        ],
    )


def _to_booking(row: BookingRow) -> Booking:
    address = None
    if row.address_line1 is not None:
        address = Address(
            line1=row.address_line1,
            city=row.address_city or "",
            postcode=row.address_postcode or "",
            country=row.address_country or "",
        )
    return Booking(
        id=row.id,
        customer=Customer(
            name=row.customer_name, email=row.customer_email, address=address
        ),
        lines=tuple(
            BookingLine(
                code=line.code,
                name=line.name,
                kind=ItemKind(line.kind),
                performance=line.performance,
                unit_price=line.unit_price,
                quantity=line.quantity,
            )
            for line in row.lines
        ),
        discount_code=row.discount_code,
        subtotal=row.subtotal,
        discount=row.discount,
        delivery=row.delivery,
        delivery_fee=row.delivery_fee,
        total=row.total,
        vat=row.vat,
        payment_method=row.payment_method,
        payment_reference=row.payment_reference,
        status=BookingStatus(row.status),
        payment_fee=row.payment_fee,
        placed_at=row.placed_at,
        hold_references=tuple(row.hold_references),
        wallet_pass=row.wallet_pass,
        tracking_number=row.tracking_number,
        invoice_number=row.invoice_number,
    )


def _update_row(row: BookingRow, booking: Booking) -> None:
    # Only these change once a booking has been made.
    row.status = booking.status.value
    row.hold_references = list(booking.hold_references)
    row.wallet_pass = booking.wallet_pass
    row.tracking_number = booking.tracking_number
    row.invoice_number = booking.invoice_number
