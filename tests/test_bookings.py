from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import fakestripe
import fakevenue
import pytest
from fakes import (
    FailingRepository,
    FakePaymentMethod,
    InMemoryPlaceRepository,
    InMemoryUnitOfWork,
)

from stagedoor.bookings import BookingService
from stagedoor.bus import EventBus
from stagedoor.events import BookingConfirmed
from stagedoor.exceptions import (
    EmptyBookingError,
    FulfilmentError,
    IllegalTransitionError,
    InvalidQuantityError,
    MissingAddressError,
    NotEnoughPlacesError,
    PaymentFailedError,
    UnknownDiscountCodeError,
    UnknownItemError,
)
from stagedoor.models import Address, BookingStatus, Customer


def test_total_is_the_sum_of_the_lines(
    service: BookingService, ada: Customer
) -> None:
    booking = service.place(
        ada, [("MUC0314-ADULT", 2), ("PROG-MUCHADO", 1)], "bank_transfer"
    )

    assert booking.total == Decimal("70.00")


def test_lines_keep_the_price_at_the_time_of_booking(
    service: BookingService, ada: Customer
) -> None:
    booking = service.place(ada, [("TEE-STAGEDOOR", 3)], "bank_transfer")

    assert booking.lines[0].unit_price == Decimal("18.00")
    assert booking.lines[0].name == "StageDoor T-Shirt"


def test_the_booking_is_saved(service: BookingService, ada: Customer) -> None:
    booking = service.place(ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    assert service.get(booking.id) == booking


def test_the_customer_is_sent_a_confirmation(
    service: BookingService, ada: Customer, isolated_directories: Path
) -> None:
    booking = service.place(ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    confirmation = (
        isolated_directories / "mail" / f"{booking.id}-confirmation.txt"
    )
    assert "To: ada@example.com" in confirmation.read_text()
    assert "Total: £18.00 (includes VAT of £3.00)" in confirmation.read_text()


def test_an_empty_booking_is_rejected(
    service: BookingService, ada: Customer
) -> None:
    with pytest.raises(EmptyBookingError):
        service.place(ada, [], "bank_transfer")


@pytest.mark.parametrize("quantity", [0, -1])
def test_a_quantity_below_one_is_rejected(
    service: BookingService, ada: Customer, quantity: int
) -> None:
    with pytest.raises(InvalidQuantityError):
        service.place(ada, [("TEE-STAGEDOOR", quantity)], "bank_transfer")


def test_an_unknown_item_is_rejected_and_nothing_is_saved(
    service: BookingService, ada: Customer, isolated_directories: Path
) -> None:
    with pytest.raises(UnknownItemError):
        service.place(
            ada, [("TEE-STAGEDOOR", 1), ("NOPE-999", 1)], "bank_transfer"
        )

    assert not list((isolated_directories / "mail").glob("*"))


def test_the_booking_carries_its_totals(
    service: BookingService, ada: Customer
) -> None:
    booking = service.place(
        ada,
        [("MUC0314-ADULT", 2), ("PROG-MUCHADO", 1)],
        "bank_transfer",
        discount_code="FIRSTNIGHT10",
    )

    assert booking.subtotal == Decimal("70.00")
    assert booking.discount == Decimal("7.00")
    assert booking.total == Decimal("63.00")
    assert booking.vat == Decimal("9.60")


def test_an_unknown_discount_code_is_rejected(
    service: BookingService, ada: Customer
) -> None:
    with pytest.raises(UnknownDiscountCodeError):
        service.place(
            ada,
            [("TEE-STAGEDOOR", 1)],
            "bank_transfer",
            discount_code="FREESTUFF",
        )


def test_booking_takes_the_places(
    service: BookingService, ada: Customer, places: InMemoryPlaceRepository
) -> None:
    service.place(ada, [("GDF0320-ADULT", 2)], "bank_transfer")

    assert places.left["GDF0320"] == 0


def test_we_cannot_sell_places_we_do_not_have(
    service: BookingService, ada: Customer
) -> None:
    with pytest.raises(NotEnoughPlacesError):
        service.place(ada, [("GDF0320-ADULT", 3)], "bank_transfer")


def test_a_rejected_booking_leaves_the_places_alone(
    service: BookingService, ada: Customer, places: InMemoryPlaceRepository
) -> None:
    with pytest.raises(NotEnoughPlacesError):
        service.place(
            ada, [("MUC0314-ADULT", 5), ("GDF0320-ADULT", 3)], "bank_transfer"
        )

    assert places.left["MUC0314"] == 120


def test_the_booking_records_its_payment(
    service: BookingService, ada: Customer
) -> None:
    booking = service.place(
        ada, [("TEE-STAGEDOOR", 1)], "card", "pm_card_visa"
    )

    assert booking.payment_method == "card"
    assert booking.payment_reference.startswith("pi_")
    assert booking.status == BookingStatus.PAID
    assert booking.payment_fee == Decimal("0.47")


def test_a_bank_transfer_confirmation_says_how_to_pay(
    service: BookingService, ada: Customer, isolated_directories: Path
) -> None:
    booking = service.place(ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    confirmation = (
        isolated_directories / "mail" / f"{booking.id}-confirmation.txt"
    )
    assert f"quoting SD-{booking.id.upper()}" in confirmation.read_text()


def test_a_declined_card_says_why_and_books_nothing(
    service: BookingService, ada: Customer, places: InMemoryPlaceRepository
) -> None:
    with pytest.raises(PaymentFailedError, match="Your card was declined."):
        service.place(ada, [("GDF0320-ADULT", 1)], "card", "pm_card_declined")

    assert places.left["GDF0320"] == 2


def test_a_declined_paypal_payment_says_why_and_books_nothing(
    service: BookingService,
    ada: Customer,
    isolated_directories: Path,
    places: InMemoryPlaceRepository,
) -> None:
    with pytest.raises(PaymentFailedError, match="PayPal declined"):
        service.place(ada, [("GDF0320-ADULT", 1)], "paypal", "payer_declined")

    assert not (isolated_directories / "data").exists()
    assert places.left["GDF0320"] == 2


def test_a_bank_transfer_booking_is_awaiting_payment(
    service: BookingService, ada: Customer
) -> None:
    booking = service.place(ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    assert booking.status == BookingStatus.AWAITING_PAYMENT


def test_paid_e_tickets_are_held_issued_and_invoiced(
    service: BookingService, ada: Customer
) -> None:
    booking = service.place(
        ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa"
    )

    assert len(booking.hold_references) == 1
    assert fakevenue.SEATS["MUC0314"] == 118
    assert booking.wallet_pass is not None
    assert booking.wallet_pass.startswith("https://wallet.example/")
    assert booking.invoice_number == "INV-000001"


def test_posted_tickets_get_a_tracking_number(
    service: BookingService, ada_at_home: Customer
) -> None:
    booking = service.place(
        ada_at_home,
        [("MUC0314-ADULT", 2), ("PROG-MUCHADO", 1)],
        "card",
        "pm_card_visa",
        delivery="post",
    )

    assert booking.tracking_number is not None
    assert booking.tracking_number.startswith("RM")
    assert booking.wallet_pass is None


def test_a_failed_label_gives_the_seats_back(
    service: BookingService,
    ada_at_home: Customer,
    places: InMemoryPlaceRepository,
) -> None:
    nowhere = Address("1 Nowhere Lane", "Nowhere", "XX1 1XX", "GB")

    with pytest.raises(FulfilmentError):
        service.place(
            replace(ada_at_home, address=nowhere),
            [("MUC0314-ADULT", 2)],
            "card",
            "pm_card_visa",
            delivery="post",
        )

    assert fakevenue.SEATS["MUC0314"] == 120
    assert places.left["MUC0314"] == 120


def test_posted_tickets_need_an_address(
    service: BookingService, ada: Customer
) -> None:
    with pytest.raises(MissingAddressError):
        service.place(
            ada, [("MUC0314-ADULT", 1)], "bank_transfer", delivery="post"
        )


def test_a_bank_transfer_is_not_issued_until_it_is_paid(
    service: BookingService,
    ada: Customer,
) -> None:
    booking = service.place(ada, [("MUC0314-ADULT", 2)], "bank_transfer")

    assert booking.hold_references == ()
    assert booking.invoice_number is None


def test_a_booking_is_announced(
    service: BookingService, ada: Customer
) -> None:
    bus = EventBus()
    heard: list[BookingConfirmed] = []
    bus.subscribe(BookingConfirmed, heard.append)

    service = replace(service, bus=bus)

    booking = service.place(ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    assert heard == [
        BookingConfirmed(
            booking_id=booking.id,
            customer_email="ada@example.com",
            total=Decimal("18.00"),
            placed_at=booking.placed_at,
        )
    ]


def test_a_reaction_that_fails_does_not_fail_the_booking(
    service: BookingService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    ada = Customer(name="Ada Lovelace", email="ada+shows@example.com")

    booking = service.place(
        ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa"
    )

    assert service.get(booking.id) == booking
    assert "award_points failed to handle BookingConfirmed" in caplog.text


def test_a_bank_transfer_is_issued_once_it_is_paid(
    service: BookingService, ada: Customer
) -> None:
    booking = service.place(ada, [("MUC0314-ADULT", 2)], "bank_transfer")

    paid = service.mark_paid(booking.id)

    assert paid.status == BookingStatus.PAID
    assert paid.invoice_number == "INV-000001"
    assert service.get(booking.id) == paid


def test_only_a_booking_awaiting_payment_can_be_marked_paid(
    service: BookingService,
    ada: Customer,
) -> None:
    booking = service.place(
        ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa"
    )

    with pytest.raises(IllegalTransitionError):
        service.mark_paid(booking.id)


def test_a_paid_booking_can_be_checked_in(
    service: BookingService, ada: Customer
) -> None:
    booking = service.place(
        ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa"
    )

    assert service.check_in(booking.id).status == BookingStatus.CHECKED_IN


def test_a_booking_cannot_be_checked_in_twice(
    service: BookingService, ada: Customer
) -> None:
    booking = service.place(
        ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa"
    )
    service.check_in(booking.id)

    with pytest.raises(IllegalTransitionError):
        service.check_in(booking.id)


def test_cancelling_an_unpaid_booking_gives_the_places_back(
    service: BookingService, ada: Customer, places: InMemoryPlaceRepository
) -> None:
    booking = service.place(ada, [("GDF0320-ADULT", 2)], "bank_transfer")

    assert service.cancel(booking.id).status == BookingStatus.CANCELLED
    assert places.left["GDF0320"] == 2


def test_cancelling_a_paid_booking_refunds_it(
    service: BookingService, ada: Customer, places: InMemoryPlaceRepository
) -> None:
    booking = service.place(
        ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa"
    )

    assert service.cancel(booking.id).status == BookingStatus.REFUNDED
    assert places.left["MUC0314"] == 120
    assert fakevenue.SEATS["MUC0314"] == 120


def test_a_booking_that_has_been_used_cannot_be_cancelled(
    service: BookingService,
    ada: Customer,
) -> None:
    booking = service.place(
        ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa"
    )
    service.check_in(booking.id)

    with pytest.raises(IllegalTransitionError):
        service.cancel(booking.id)


# Written after a customer was charged for a booking that was never saved.

NOON = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)


def test_a_booking_records_when_it_was_made(
    service: BookingService, ada: Customer
) -> None:
    service = replace(service, clock=lambda: NOON)

    booking = service.place(ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    assert booking.placed_at == NOON


def test_a_bank_transfer_is_paid_by_quoting_the_booking_id(
    service: BookingService, ada: Customer
) -> None:
    service = replace(service, new_id=lambda: "3f9a1c2b7d4e")

    booking = service.place(ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    assert booking.payment_reference == "SD-3F9A1C2B7D4E"


def test_a_booking_that_cannot_be_saved_is_not_confirmed(
    service: BookingService, ada: Customer, isolated_directories: Path
) -> None:
    uow = InMemoryUnitOfWork(bookings=FailingRepository())
    service = replace(
        service, unit_of_work=lambda: uow, new_id=lambda: "abc123"
    )

    with pytest.raises(OSError):
        service.place(ada, [("TEE-STAGEDOOR", 1)], "card", "pm_card_visa")

    mail = isolated_directories / "mail"
    assert not (mail / "abc123-confirmation.txt").exists()


def test_a_booking_that_cannot_be_saved_is_not_paid_for(
    service: BookingService, ada: Customer
) -> None:
    card = FakePaymentMethod()
    uow = InMemoryUnitOfWork(bookings=FailingRepository())
    service = replace(service, payment_methods={"card": card})
    service = replace(service, unit_of_work=lambda: uow)

    with pytest.raises(OSError):
        service.place(ada, [("TEE-STAGEDOOR", 1)], "card", "tok_ok")

    assert card.charges == []


def test_a_booking_that_cannot_be_saved_gives_its_places_back(
    service: BookingService, ada: Customer, places: InMemoryPlaceRepository
) -> None:
    uow = InMemoryUnitOfWork(bookings=FailingRepository(), places=places)
    service = replace(service, unit_of_work=lambda: uow)

    with pytest.raises(OSError):
        service.place(ada, [("GDF0320-ADULT", 2)], "bank_transfer")

    assert places.left["GDF0320"] == 2


def test_a_booking_survives_a_busy_moment_at_stripe(
    service: BookingService, ada: Customer
) -> None:
    fakestripe.simulate_outage = 2

    booking = service.place(
        ada, [("TEE-STAGEDOOR", 1)], "card", "pm_card_visa"
    )

    assert booking.payment_reference.startswith("pi_")


def test_a_booking_survives_a_busy_moment_at_the_venue(
    service: BookingService, ada: Customer
) -> None:
    fakevenue.simulate_outage = 1

    booking = service.place(
        ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa"
    )

    assert len(booking.hold_references) == 1
