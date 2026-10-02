from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from stagedoor.adapters.alerts import notify_sales_team
from stagedoor.domain.events import BookingConfirmed


def confirmed(total: str) -> BookingConfirmed:
    return BookingConfirmed(
        booking_id="abc123",
        customer_email="ada@example.com",
        total=Decimal(total),
        placed_at=datetime(2026, 9, 30, 9, 15, tzinfo=UTC),
    )


def test_a_big_booking_is_passed_to_the_sales_team(
    isolated_directories: Path,
) -> None:
    notify_sales_team(confirmed("512.00"))

    alert = isolated_directories / "mail" / "abc123-sales.txt"
    assert "has just booked £512.00" in alert.read_text()


def test_a_small_booking_is_not(isolated_directories: Path) -> None:
    notify_sales_team(confirmed("500.00"))

    assert not (isolated_directories / "mail" / "abc123-sales.txt").exists()
