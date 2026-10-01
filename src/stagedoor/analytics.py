"""Every sale, for the data team's dashboard.

Each sale is a row in analytics.csv, in the data directory: when it was
made, the booking, and the total. The dashboard reads the file every night.
"""

import csv
import os
from pathlib import Path

from stagedoor.models import Booking

COLUMNS = ["placed_at", "booking_id", "total"]


def _sales_file() -> Path:
    directory = Path(os.environ.get("STAGEDOOR_DATA_DIR", "data"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "analytics.csv"


def record_sale(booking: Booking) -> None:
    """Add a booking to the sales file."""
    path = _sales_file()
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if new_file:
            writer.writerow(COLUMNS)
        writer.writerow(
            [booking.placed_at.isoformat(), booking.id, booking.total]
        )
