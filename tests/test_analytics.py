from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from stagedoor.adapters.analytics import record_sale
from stagedoor.domain.events import BookingConfirmed


def test_every_sale_is_a_row_under_a_heading(
    isolated_directories: Path,
) -> None:
    for booking_id in ["abc123", "def456"]:
        record_sale(
            BookingConfirmed(
                booking_id=booking_id,
                customer_email="ada@example.com",
                total=Decimal("18.00"),
                placed_at=datetime(2026, 9, 30, 9, 15, tzinfo=UTC),
            )
        )

    sales = isolated_directories / "data" / "analytics.csv"
    assert sales.read_text().splitlines() == [
        "placed_at,booking_id,total",
        "2026-09-30T09:15:00+00:00,abc123,18.00",
        "2026-09-30T09:15:00+00:00,def456,18.00",
    ]
