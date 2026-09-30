"""Saving and loading bookings.

Each booking is a JSON file in the data directory. The directory comes from
the STAGEDOOR_DATA_DIR environment variable, or ./data if it is not set.
"""

import json
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from stagedoor.exceptions import BookingNotFoundError
from stagedoor.models import (
    Booking,
    BookingLine,
    Customer,
    ItemKind,
    PaymentStatus,
)


def _bookings_dir() -> Path:
    directory = Path(os.environ.get("STAGEDOOR_DATA_DIR", "data")) / "bookings"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_booking(booking: Booking) -> None:
    """Write a booking to disk, replacing any earlier copy."""
    path = _bookings_dir() / f"{booking.id}.json"
    path.write_text(json.dumps(_to_dict(booking), indent=2))


def load_booking(booking_id: str) -> Booking:
    """Read a booking back from disk."""
    path = _bookings_dir() / f"{booking_id}.json"
    if not path.exists():
        raise BookingNotFoundError(booking_id)
    return _from_dict(json.loads(path.read_text()))


def _to_dict(booking: Booking) -> dict[str, Any]:
    return {
        "id": booking.id,
        "customer": {
            "name": booking.customer.name,
            "email": booking.customer.email,
        },
        "lines": [
            {
                "code": line.code,
                "name": line.name,
                "kind": line.kind.value,
                "performance": line.performance,
                "unit_price": str(line.unit_price),
                "quantity": line.quantity,
            }
            for line in booking.lines
        ],
        "discount_code": booking.discount_code,
        "subtotal": str(booking.subtotal),
        "discount": str(booking.discount),
        "delivery": booking.delivery,
        "delivery_fee": str(booking.delivery_fee),
        "total": str(booking.total),
        "vat": str(booking.vat),
        "payment_method": booking.payment_method,
        "payment_reference": booking.payment_reference,
        "payment_status": booking.payment_status.value,
        "payment_fee": str(booking.payment_fee),
        "placed_at": booking.placed_at.isoformat(),
    }


def _from_dict(data: dict[str, Any]) -> Booking:
    return Booking(
        id=data["id"],
        customer=Customer(**data["customer"]),
        lines=tuple(
            BookingLine(
                code=line["code"],
                name=line["name"],
                kind=ItemKind(line["kind"]),
                performance=line["performance"],
                unit_price=Decimal(line["unit_price"]),
                quantity=line["quantity"],
            )
            for line in data["lines"]
        ),
        discount_code=data["discount_code"],
        subtotal=Decimal(data["subtotal"]),
        discount=Decimal(data["discount"]),
        delivery=data["delivery"],
        delivery_fee=Decimal(data["delivery_fee"]),
        total=Decimal(data["total"]),
        vat=Decimal(data["vat"]),
        payment_method=data["payment_method"],
        payment_reference=data["payment_reference"],
        payment_status=PaymentStatus(data["payment_status"]),
        payment_fee=Decimal(data["payment_fee"]),
        placed_at=datetime.fromisoformat(data["placed_at"]),
    )
