from decimal import Decimal
from pathlib import Path

import pytest

from stagedoor.bookings import place_booking
from stagedoor.capacity import PLACES
from stagedoor.exceptions import (
    EmptyBookingError,
    InvalidQuantityError,
    NotEnoughPlacesError,
    UnknownDiscountCodeError,
    UnknownItemError,
)
from stagedoor.models import Customer
from stagedoor.storage import load_booking


def test_total_is_the_sum_of_the_lines(ada: Customer) -> None:
    booking = place_booking(
        ada, [("MUC0314-ADULT", 2), ("PROG-MUCHADO", 1)], "bank_transfer"
    )

    assert booking.total == Decimal("70.00")


def test_lines_keep_the_price_at_the_time_of_booking(ada: Customer) -> None:
    booking = place_booking(ada, [("TEE-STAGEDOOR", 3)], "bank_transfer")

    assert booking.lines[0].unit_price == Decimal("18.00")
    assert booking.lines[0].name == "StageDoor T-Shirt"


def test_the_booking_is_saved(ada: Customer) -> None:
    booking = place_booking(ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    assert load_booking(booking.id) == booking


def test_the_customer_is_sent_a_confirmation(
    ada: Customer, isolated_directories: Path
) -> None:
    booking = place_booking(ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    confirmation = (
        isolated_directories / "mail" / f"{booking.id}-confirmation.txt"
    )
    assert "To: ada@example.com" in confirmation.read_text()
    assert "Total: £18.00 (includes VAT of £3.00)" in confirmation.read_text()


def test_an_empty_booking_is_rejected(ada: Customer) -> None:
    with pytest.raises(EmptyBookingError):
        place_booking(ada, [], "bank_transfer")


@pytest.mark.parametrize("quantity", [0, -1])
def test_a_quantity_below_one_is_rejected(
    ada: Customer, quantity: int
) -> None:
    with pytest.raises(InvalidQuantityError):
        place_booking(ada, [("TEE-STAGEDOOR", quantity)], "bank_transfer")


def test_an_unknown_item_is_rejected_and_nothing_is_saved(
    ada: Customer, isolated_directories: Path
) -> None:
    with pytest.raises(UnknownItemError):
        place_booking(
            ada, [("TEE-STAGEDOOR", 1), ("NOPE-999", 1)], "bank_transfer"
        )

    assert not list((isolated_directories / "mail").glob("*"))


def test_the_booking_carries_its_totals(ada: Customer) -> None:
    booking = place_booking(
        ada,
        [("MUC0314-ADULT", 2), ("PROG-MUCHADO", 1)],
        "bank_transfer",
        discount_code="FIRSTNIGHT10",
    )

    assert booking.subtotal == Decimal("70.00")
    assert booking.discount == Decimal("7.00")
    assert booking.total == Decimal("63.00")
    assert booking.vat == Decimal("9.60")


def test_an_unknown_discount_code_is_rejected(ada: Customer) -> None:
    with pytest.raises(UnknownDiscountCodeError):
        place_booking(
            ada,
            [("TEE-STAGEDOOR", 1)],
            "bank_transfer",
            discount_code="FREESTUFF",
        )


def test_booking_takes_the_places(ada: Customer) -> None:
    place_booking(ada, [("GDF0320-ADULT", 2)], "bank_transfer")

    assert PLACES["GDF0320"] == 0


def test_we_cannot_sell_places_we_do_not_have(ada: Customer) -> None:
    with pytest.raises(NotEnoughPlacesError):
        place_booking(ada, [("GDF0320-ADULT", 3)], "bank_transfer")


def test_a_rejected_booking_leaves_the_places_alone(ada: Customer) -> None:
    with pytest.raises(NotEnoughPlacesError):
        place_booking(
            ada, [("MUC0314-ADULT", 5), ("GDF0320-ADULT", 3)], "bank_transfer"
        )

    assert PLACES["MUC0314"] == 120


def test_the_booking_records_its_payment(ada: Customer) -> None:
    booking = place_booking(
        ada, [("TEE-STAGEDOOR", 1)], "card", "pm_card_visa"
    )

    assert booking.payment_method == "card"
    assert booking.payment_reference.startswith("pi_")
    assert booking.payment_fee == Decimal("0.47")


def test_a_bank_transfer_confirmation_says_how_to_pay(
    ada: Customer, isolated_directories: Path
) -> None:
    booking = place_booking(ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    confirmation = (
        isolated_directories / "mail" / f"{booking.id}-confirmation.txt"
    )
    assert f"quoting SD-{booking.id.upper()}" in confirmation.read_text()
