from decimal import Decimal

from stagedoor.models import BookingLine, ItemKind


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
