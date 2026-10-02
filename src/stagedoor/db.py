"""Keeping bookings and places in PostgreSQL, with SQLAlchemy.

This is the only module in StageDoor that knows SQLAlchemy exists. Each
Row class is a table, and each attribute a column: a booking is one row in
bookings, and one row in booking_lines for each thing on it, and each
performance is one row in performances. The repositories turn bookings
into rows and back, so nothing outside this module ever sees a row.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ARRAY, DateTime, ForeignKey, Numeric, String
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from stagedoor.capacity import CAPACITY, places_wanted
from stagedoor.exceptions import BookingNotFoundError, NotEnoughPlacesError
from stagedoor.models import (
    Address,
    Booking,
    BookingLine,
    BookingStatus,
    Customer,
    ItemKind,
)

Money = Numeric(10, 2)


class Base(DeclarativeBase):
    """What every table is built on."""


class BookingRow(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    customer_name: Mapped[str]
    customer_email: Mapped[str]
    address_line1: Mapped[str | None]
    address_city: Mapped[str | None]
    address_postcode: Mapped[str | None]
    address_country: Mapped[str | None]
    discount_code: Mapped[str | None]
    subtotal: Mapped[Decimal] = mapped_column(Money)
    discount: Mapped[Decimal] = mapped_column(Money)
    delivery: Mapped[str]
    delivery_fee: Mapped[Decimal] = mapped_column(Money)
    total: Mapped[Decimal] = mapped_column(Money)
    vat: Mapped[Decimal] = mapped_column(Money)
    payment_method: Mapped[str]
    payment_reference: Mapped[str]
    status: Mapped[str]
    payment_fee: Mapped[Decimal] = mapped_column(Money)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hold_references: Mapped[list[str]] = mapped_column(ARRAY(String))
    wallet_pass: Mapped[str | None]
    tracking_number: Mapped[str | None]
    invoice_number: Mapped[str | None]
    lines: Mapped[list[BookingLineRow]] = relationship(
        order_by="BookingLineRow.id", cascade="all, delete-orphan"
    )


class BookingLineRow(Base):
    __tablename__ = "booking_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"))
    code: Mapped[str]
    name: Mapped[str]
    kind: Mapped[str]
    performance: Mapped[str | None]
    unit_price: Mapped[Decimal] = mapped_column(Money)
    quantity: Mapped[int]


class PerformanceRow(Base):
    __tablename__ = "performances"

    code: Mapped[str] = mapped_column(String(7), primary_key=True)
    places: Mapped[int]


class SqlAlchemyBookingRepository:
    """Bookings, kept in PostgreSQL."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def add(self, booking: Booking) -> None:
        with self.sessions() as session:
            session.add(_to_row(booking))
            session.commit()

    def get(self, booking_id: str) -> Booking:
        with self.sessions() as session:
            return _to_booking(_load_row(session, booking_id))

    def save(self, booking: Booking) -> None:
        with self.sessions() as session:
            _update_row(_load_row(session, booking.id), booking)
            session.commit()


class SqlAlchemyPlaceRepository:
    """The places left for every performance, kept in PostgreSQL."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def check(self, lines: Sequence[BookingLine]) -> None:
        with self.sessions() as session:
            for performance, quantity in places_wanted(lines).items():
                row = session.get(PerformanceRow, performance)
                available = row.places if row else 0
                if available < quantity:
                    raise NotEnoughPlacesError(
                        performance, quantity, available
                    )

    def take(self, lines: Sequence[BookingLine]) -> None:
        with self.sessions() as session:
            for performance, quantity in places_wanted(lines).items():
                session.get_one(PerformanceRow, performance).places -= quantity
            session.commit()

    def give_back(self, lines: Sequence[BookingLine]) -> None:
        with self.sessions() as session:
            for performance, quantity in places_wanted(lines).items():
                session.get_one(PerformanceRow, performance).places += quantity
            session.commit()


def connect(url: str) -> sessionmaker[Session]:
    """Sessions with the database at ``url``. Nothing connects until used."""
    return sessionmaker(_create_engine(url), expire_on_commit=False)


def create_tables(url: str) -> None:
    """Create any of StageDoor's tables that do not exist yet.

    Every performance that is not in the database yet goes on sale with all
    of its places.
    """
    engine = _create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for code, places in CAPACITY.items():
            if session.get(PerformanceRow, code) is None:
                session.add(PerformanceRow(code=code, places=places))
        session.commit()


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
