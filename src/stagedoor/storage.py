"""Saving and loading bookings.

Each booking is a JSON file in a directory. Which directory is decided by
whoever builds the store, so a test can give it one of its own.
"""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from stagedoor.exceptions import BookingNotFoundError
from stagedoor.models import (
    Address,
    Booking,
    BookingLine,
    BookingStatus,
    Customer,
    ItemKind,
)


class BookingStore:
    """Bookings, kept as JSON files in one directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def save(self, booking: Booking) -> None:
        """Write a booking to disk, replacing any earlier copy."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{booking.id}.json"
        path.write_text(json.dumps(_to_dict(booking), indent=2))

    def load(self, booking_id: str) -> Booking:
        """Read a booking back from disk."""
        path = self.directory / f"{booking_id}.json"
        if not path.exists():
            raise BookingNotFoundError(booking_id)
        return _from_dict(json.loads(path.read_text()))


def _to_dict(booking: Booking) -> dict[str, Any]:
    return {
        "id": booking.id,
        "customer": {
            "name": booking.customer.name,
            "email": booking.customer.email,
            "address": _address_to_dict(booking.customer.address),
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
        "status": booking.status.value,
        "payment_fee": str(booking.payment_fee),
        "placed_at": booking.placed_at.isoformat(),
        "hold_references": list(booking.hold_references),
        "wallet_pass": booking.wallet_pass,
        "tracking_number": booking.tracking_number,
        "invoice_number": booking.invoice_number,
    }


def _from_dict(data: dict[str, Any]) -> Booking:
    return Booking(
        id=data["id"],
        customer=Customer(
            name=data["customer"]["name"],
            email=data["customer"]["email"],
            address=_address_from_dict(data["customer"]["address"]),
        ),
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
        status=BookingStatus(data["status"]),
        payment_fee=Decimal(data["payment_fee"]),
        placed_at=datetime.fromisoformat(data["placed_at"]),
        hold_references=tuple(data["hold_references"]),
        wallet_pass=data["wallet_pass"],
        tracking_number=data["tracking_number"],
        invoice_number=data["invoice_number"],
    )


def _address_to_dict(address: Address | None) -> dict[str, str] | None:
    if address is None:
        return None
    return {
        "line1": address.line1,
        "city": address.city,
        "postcode": address.postcode,
        "country": address.country,
    }


def _address_from_dict(data: dict[str, str] | None) -> Address | None:
    return None if data is None else Address(**data)
