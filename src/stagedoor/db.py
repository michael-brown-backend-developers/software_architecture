"""StageDoor's tables in PostgreSQL, described for SQLAlchemy.

Each class is a table, and each attribute a column. A booking is one row in
bookings, and one row in booking_lines for each thing on it.
"""

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


def connect(url: str) -> sessionmaker[Session]:
    """Sessions with the database at ``url``. Nothing connects until used."""
    return sessionmaker(_create_engine(url), expire_on_commit=False)


def create_tables(url: str) -> None:
    """Create any of StageDoor's tables that do not exist yet."""
    Base.metadata.create_all(_create_engine(url))
