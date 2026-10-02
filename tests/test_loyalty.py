from datetime import UTC, datetime
from decimal import Decimal

import pytest

from stagedoor.adapters.loyalty import award_points, points_for
from stagedoor.domain.events import BookingConfirmed


def confirmed(email: str, total: str) -> BookingConfirmed:
    return BookingConfirmed(
        booking_id="abc123",
        customer_email=email,
        total=Decimal(total),
        placed_at=datetime(2026, 9, 30, 9, 15, tzinfo=UTC),
    )


def test_a_member_gets_a_point_for_every_whole_pound() -> None:
    award_points(confirmed("ada@example.com", "70.99"))

    assert points_for("ada@example.com") == 70


def test_points_add_up() -> None:
    award_points(confirmed("ada@example.com", "70.00"))
    award_points(confirmed("Ada@Example.com", "18.00"))

    assert points_for("ada@example.com") == 88


def test_an_address_with_a_plus_is_still_refused() -> None:
    with pytest.raises(ValueError):
        award_points(confirmed("ada+shows@example.com", "70.00"))
