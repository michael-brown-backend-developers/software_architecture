"""What every booking repository must do, checked against each of them.

The in-memory repository stands in for PostgreSQL in most tests, so it has
to keep the same promises. The PostgreSQL tests are skipped if the
database is not running.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fakes import InMemoryBookingRepository

from stagedoor.db import SqlAlchemyBookingRepository, connect
from stagedoor.exceptions import BookingNotFoundError
from stagedoor.models import (
    Address,
    Booking,
    BookingLine,
    BookingStatus,
    Customer,
    ItemKind,
)
from stagedoor.repository import BookingRepository


@pytest.fixture(params=["memory", "postgres"])
def repository(request: pytest.FixtureRequest) -> BookingRepository:
    if request.param == "memory":
        return InMemoryBookingRepository()
    database = request.getfixturevalue("database")
    return SqlAlchemyBookingRepository(connect(database))


def posted_booking() -> Booking:
    return Booking(
        id="abc123",
        customer=Customer(
            name="Ada Lovelace",
            email="ada@example.com",
            address=Address(
                "12 St James's Square", "London", "SW1Y 4JH", "GB"
            ),
        ),
        lines=(
            BookingLine(
                "MUC0314-ADULT",
                "Much Ado About NoneType, Sat 14 Mar 19:30 - Adult",
                ItemKind.TICKET,
                "MUC0314",
                Decimal("32.00"),
                2,
            ),
            BookingLine(
                "PROG-MUCHADO",
                "Much Ado About NoneType programme",
                ItemKind.PROGRAMME,
                None,
                Decimal("6.00"),
                1,
            ),
        ),
        discount_code="FIRSTNIGHT10",
        subtotal=Decimal("70.00"),
        discount=Decimal("7.00"),
        delivery="post",
        delivery_fee=Decimal("2.50"),
        total=Decimal("65.50"),
        vat=Decimal("10.08"),
        payment_method="bank_transfer",
        payment_reference="SD-ABC123",
        status=BookingStatus.AWAITING_PAYMENT,
        payment_fee=Decimal("0.00"),
        placed_at=datetime(2026, 9, 30, 9, 15, tzinfo=UTC),
    )


def test_a_booking_comes_back_as_it_went_in(
    repository: BookingRepository,
) -> None:
    repository.add(posted_booking())

    assert repository.get("abc123") == posted_booking()


def test_a_missing_booking_is_not_found(
    repository: BookingRepository,
) -> None:
    with pytest.raises(BookingNotFoundError):
        repository.get("does-not-exist")


def test_changes_are_kept_once_saved(repository: BookingRepository) -> None:
    repository.add(posted_booking())
    booking = repository.get("abc123")
    booking.mark_paid()
    booking.hold_references = ("H-1234567890",)
    booking.tracking_number = "RM123456789GB"
    booking.invoice_number = "INV-000042"

    repository.save(booking)

    assert repository.get("abc123") == booking


def test_changes_are_not_kept_until_saved(
    repository: BookingRepository,
) -> None:
    repository.add(posted_booking())
    booking = repository.get("abc123")

    booking.mark_paid()

    assert repository.get("abc123").status == BookingStatus.AWAITING_PAYMENT
