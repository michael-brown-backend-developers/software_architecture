from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from stagedoor.invoicing import create_invoice
from stagedoor.models import Booking, Customer, PaymentStatus


def test_invoice_numbers_follow_on_with_no_gaps(
    ada: Customer, isolated_directories: Path
) -> None:
    booking = Booking(
        id="abc123",
        customer=ada,
        lines=(),
        discount_code=None,
        subtotal=Decimal("18.00"),
        discount=Decimal("0.00"),
        delivery="e_ticket",
        delivery_fee=Decimal("0.00"),
        total=Decimal("18.00"),
        vat=Decimal("3.00"),
        payment_method="card",
        payment_reference="pi_123",
        payment_status=PaymentStatus.PAID,
        payment_fee=Decimal("0.47"),
        placed_at=datetime(2026, 9, 30, 9, 15, tzinfo=UTC),
    )

    assert create_invoice(booking) == "INV-000001"
    assert create_invoice(booking) == "INV-000002"

    invoice = isolated_directories / "data" / "invoices" / "INV-000002.txt"
    assert "Total: £18.00, including VAT of £3.00" in invoice.read_text()
