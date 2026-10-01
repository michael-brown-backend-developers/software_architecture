from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from stagedoor.exceptions import BookingNotFoundError
from stagedoor.models import (
    Address,
    Booking,
    BookingLine,
    BookingStatus,
    Customer,
    ItemKind,
)
from stagedoor.storage import BookingStore


def test_a_booking_survives_a_round_trip(
    ada: Customer, tmp_path: Path
) -> None:
    booking = Booking(
        id="abc123",
        customer=Customer(
            name=ada.name,
            email=ada.email,
            address=Address("1 High St", "Leeds", "LS1 1AA", "GB"),
        ),
        lines=(
            BookingLine(
                code="MUC0314-ADULT",
                name="Much Ado About NoneType",
                kind=ItemKind.TICKET,
                performance="MUC0314",
                unit_price=Decimal("32.00"),
                quantity=2,
            ),
        ),
        discount_code="FIRSTNIGHT10",
        subtotal=Decimal("64.00"),
        discount=Decimal("6.40"),
        delivery="post",
        delivery_fee=Decimal("2.50"),
        total=Decimal("60.10"),
        vat=Decimal("10.02"),
        payment_method="card",
        payment_reference="pi_123",
        status=BookingStatus.PAID,
        payment_fee=Decimal("1.10"),
        placed_at=datetime(2026, 9, 30, 9, 15, tzinfo=UTC),
        hold_references=("H-1234567890",),
        tracking_number="RM123456789GB",
        invoice_number="INV-000042",
    )

    store = BookingStore(tmp_path)
    store.save(booking)

    assert store.load("abc123") == booking


def test_loading_a_missing_booking_raises(tmp_path: Path) -> None:
    with pytest.raises(BookingNotFoundError):
        BookingStore(tmp_path).load("does-not-exist")
