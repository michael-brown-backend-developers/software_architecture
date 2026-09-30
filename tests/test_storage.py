from datetime import UTC, datetime
from decimal import Decimal

import pytest

from stagedoor.exceptions import BookingNotFoundError
from stagedoor.models import Booking, BookingLine, Customer, ItemKind
from stagedoor.storage import load_booking, save_booking


def test_a_booking_survives_a_round_trip(ada: Customer) -> None:
    booking = Booking(
        id="abc123",
        customer=ada,
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
        payment_fee=Decimal("1.10"),
        placed_at=datetime(2026, 9, 30, 9, 15, tzinfo=UTC),
    )

    save_booking(booking)

    assert load_booking("abc123") == booking


def test_loading_a_missing_booking_raises() -> None:
    with pytest.raises(BookingNotFoundError):
        load_booking("does-not-exist")
