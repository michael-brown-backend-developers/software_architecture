from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import fakeroyalmail
import fakevenue
import pytest

from stagedoor.bookings import place_booking
from stagedoor.capacity import PLACES
from stagedoor.exceptions import (
    EmptyBookingError,
    InvalidQuantityError,
    MissingAddressError,
    NotEnoughPlacesError,
    PaymentFailedError,
    UnknownDiscountCodeError,
    UnknownItemError,
)
from stagedoor.models import Address, Customer, PaymentStatus
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
    assert booking.payment_status == PaymentStatus.PAID
    assert booking.payment_fee == Decimal("0.47")


def test_a_bank_transfer_confirmation_says_how_to_pay(
    ada: Customer, isolated_directories: Path
) -> None:
    booking = place_booking(ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    confirmation = (
        isolated_directories / "mail" / f"{booking.id}-confirmation.txt"
    )
    assert f"quoting SD-{booking.id.upper()}" in confirmation.read_text()


def test_a_declined_card_says_why_and_books_nothing(ada: Customer) -> None:
    with pytest.raises(PaymentFailedError, match="Your card was declined."):
        place_booking(ada, [("GDF0320-ADULT", 1)], "card", "pm_card_declined")

    assert PLACES["GDF0320"] == 2


def test_a_declined_paypal_payment_says_why_and_books_nothing(
    ada: Customer, isolated_directories: Path
) -> None:
    with pytest.raises(PaymentFailedError, match="PayPal declined"):
        place_booking(ada, [("GDF0320-ADULT", 1)], "paypal", "payer_declined")

    assert not (isolated_directories / "data").exists()
    assert PLACES["GDF0320"] == 2


def test_a_bank_transfer_booking_is_awaiting_payment(ada: Customer) -> None:
    booking = place_booking(ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    assert booking.payment_status == PaymentStatus.AWAITING_PAYMENT


def test_paid_e_tickets_are_held_issued_and_invoiced(ada: Customer) -> None:
    booking = place_booking(
        ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa"
    )

    assert len(booking.hold_references) == 1
    assert fakevenue.SEATS["MUC0314"] == 118
    assert booking.wallet_pass is not None
    assert booking.wallet_pass.startswith("https://wallet.example/")
    assert booking.invoice_number == "INV-000001"


def test_posted_tickets_get_a_tracking_number(ada_at_home: Customer) -> None:
    booking = place_booking(
        ada_at_home,
        [("MUC0314-ADULT", 2), ("PROG-MUCHADO", 1)],
        "card",
        "pm_card_visa",
        delivery="post",
    )

    assert booking.tracking_number is not None
    assert booking.tracking_number.startswith("RM")
    assert booking.wallet_pass is None


def test_a_failed_label_gives_the_seats_back(ada_at_home: Customer) -> None:
    nowhere = Address("1 Nowhere Lane", "Nowhere", "XX1 1XX", "GB")

    with pytest.raises(fakeroyalmail.RoyalMailError):
        place_booking(
            replace(ada_at_home, address=nowhere),
            [("MUC0314-ADULT", 2)],
            "card",
            "pm_card_visa",
            delivery="post",
        )

    assert fakevenue.SEATS["MUC0314"] == 120
    assert PLACES["MUC0314"] == 120


def test_posted_tickets_need_an_address(ada: Customer) -> None:
    with pytest.raises(MissingAddressError):
        place_booking(
            ada, [("MUC0314-ADULT", 1)], "bank_transfer", delivery="post"
        )


def test_a_bank_transfer_is_not_issued_until_it_is_paid(
    ada: Customer,
) -> None:
    booking = place_booking(ada, [("MUC0314-ADULT", 2)], "bank_transfer")

    assert booking.hold_references == ()
    assert booking.invoice_number is None
