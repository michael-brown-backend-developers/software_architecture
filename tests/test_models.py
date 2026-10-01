from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from stagedoor.exceptions import IllegalTransitionError
from stagedoor.models import (
    STATES,
    Booking,
    BookingLine,
    BookingStatus,
    Customer,
    ItemKind,
)

AWAITING_PAYMENT = BookingStatus.AWAITING_PAYMENT
PAID = BookingStatus.PAID
CHECKED_IN = BookingStatus.CHECKED_IN
CANCELLED = BookingStatus.CANCELLED
REFUNDED = BookingStatus.REFUNDED


def test_line_total_is_unit_price_times_quantity() -> None:
    line = BookingLine(
        code="TEE-STAGEDOOR",
        name="T-shirt",
        kind=ItemKind.MERCH,
        performance=None,
        unit_price=Decimal("18.00"),
        quantity=3,
    )

    assert line.line_total == Decimal("54.00")


def booking_in(status: BookingStatus) -> Booking:
    return Booking(
        id="abc123",
        customer=Customer(name="Ada Lovelace", email="ada@example.com"),
        lines=(),
        discount_code=None,
        subtotal=Decimal("64.00"),
        discount=Decimal("0.00"),
        delivery="e_ticket",
        delivery_fee=Decimal("0.00"),
        total=Decimal("64.00"),
        vat=Decimal("10.67"),
        payment_method="bank_transfer",
        payment_reference="SD-ABC123",
        status=status,
        payment_fee=Decimal("0.00"),
        placed_at=datetime(2026, 9, 30, 9, 15, tzinfo=UTC),
    )


ACTIONS: dict[str, Callable[[Booking], None]] = {
    "mark_paid": Booking.mark_paid,
    "check_in": Booking.check_in,
    "cancel": Booking.cancel,
}

# Where each action takes a booking. Anything not here is refused.
LIFECYCLE = {
    ("mark_paid", AWAITING_PAYMENT): PAID,
    ("check_in", PAID): CHECKED_IN,
    ("cancel", AWAITING_PAYMENT): CANCELLED,
    ("cancel", PAID): REFUNDED,
}


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("status", BookingStatus)
def test_every_action_in_every_status(
    action: str, status: BookingStatus
) -> None:
    booking = booking_in(status)
    expected = LIFECYCLE.get((action, status))

    if expected is None:
        with pytest.raises(IllegalTransitionError):
            ACTIONS[action](booking)
        assert booking.status == status
    else:
        ACTIONS[action](booking)
        assert booking.status == expected


def test_every_status_has_a_state() -> None:
    assert set(STATES) == set(BookingStatus)
    assert all(state.status == status for status, state in STATES.items())
