from decimal import Decimal

import pytest

from stagedoor.exceptions import UnknownDiscountCodeError
from stagedoor.models import BookingLine, ItemKind
from stagedoor.pricing import Totals, price_booking, vat_included

MUCH_ADO = BookingLine(
    "MUC0314-ADULT",
    "Much Ado About NoneType",
    ItemKind.TICKET,
    "MUC0314",
    Decimal("32.00"),
    1,
)
GUIDO_FATHER = BookingLine(
    "GDF0320-ADULT",
    "The Guido Father",
    ItemKind.TICKET,
    "GDF0320",
    Decimal("26.50"),
    1,
)
PROGRAMME = BookingLine(
    "PROG-MUCHADO", "Programme", ItemKind.PROGRAMME, None, Decimal("6.00"), 1
)
TEE = BookingLine(
    "TEE-STAGEDOOR", "T-shirt", ItemKind.MERCH, None, Decimal("18.00"), 1
)


@pytest.mark.parametrize(
    ("gross", "rate", "vat"),
    [
        (Decimal("18.00"), Decimal("0.20"), Decimal("3.00")),
        (Decimal("26.50"), Decimal("0.20"), Decimal("4.42")),
        (Decimal("8.55"), Decimal("0.20"), Decimal("1.43")),  # 1.425
        (Decimal("6.00"), Decimal("0.00"), Decimal("0.00")),
    ],
)
def test_vat_included(gross: Decimal, rate: Decimal, vat: Decimal) -> None:
    assert vat_included(gross, rate) == vat


def test_programmes_are_zero_rated() -> None:
    totals = price_booking([PROGRAMME, PROGRAMME], None)

    assert totals.vat == Decimal("0.00")


def test_no_discount_code() -> None:
    assert price_booking([TEE], None) == Totals(
        subtotal=Decimal("18.00"),
        discount=Decimal("0.00"),
        total=Decimal("18.00"),
        vat=Decimal("3.00"),
    )


def test_vat_is_worked_out_after_the_discount() -> None:
    # The tickets cost £57.60 after 10% off, which includes £9.60 of VAT.
    # The programme adds none.
    assert price_booking(
        [MUCH_ADO, MUCH_ADO, PROGRAMME], "FIRSTNIGHT10"
    ) == Totals(
        subtotal=Decimal("70.00"),
        discount=Decimal("7.00"),
        total=Decimal("63.00"),
        vat=Decimal("9.60"),
    )


def test_staff_discount() -> None:
    # £19.875 after 25% off; the VAT in that is £3.3125, to the penny.
    assert price_booking([GUIDO_FATHER], "STAFF25") == Totals(
        subtotal=Decimal("26.50"),
        discount=Decimal("6.63"),
        total=Decimal("19.87"),
        vat=Decimal("3.31"),
    )


def test_an_unknown_discount_code_is_rejected() -> None:
    with pytest.raises(UnknownDiscountCodeError):
        price_booking([TEE], "FREESTUFF")
