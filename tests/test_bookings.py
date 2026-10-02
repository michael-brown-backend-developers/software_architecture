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
    no_sleep,
)

from stagedoor import views
from stagedoor.bootstrap import App, bootstrap
from stagedoor.commands import CancelBooking, CheckIn, MakeBooking, MarkPaid
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
from stagedoor.models import Address, Booking, BookingStatus, Customer
from stagedoor.settings import Settings


def book(
    app: App,
    customer: Customer,
    items: list[tuple[str, int]],
    payment_method: str,
    payment_token: str | None = None,
    discount_code: str | None = None,
    delivery: str = "e_ticket",
) -> Booking:
    """Make a booking through the bus, and look it up."""
    command = MakeBooking(
        customer=customer,
        items=tuple(items),
        payment_method=payment_method,
        payment_token=payment_token,
        discount_code=discount_code,
        delivery=delivery,
    )
    app.bus.handle(command)
    return views.booking(command.booking_id, app.unit_of_work)


def test_total_is_the_sum_of_the_lines(app: App, ada: Customer) -> None:
    booking = book(
        app, ada, [("MUC0314-ADULT", 2), ("PROG-MUCHADO", 1)], "bank_transfer"
    )

    assert booking.total == Decimal("70.00")


def test_lines_keep_the_price_at_the_time_of_booking(
    app: App, ada: Customer
) -> None:
    booking = book(app, ada, [("TEE-STAGEDOOR", 3)], "bank_transfer")

    assert booking.lines[0].unit_price == Decimal("18.00")
    assert booking.lines[0].name == "StageDoor T-Shirt"


def test_the_booking_is_saved(app: App, ada: Customer) -> None:
    booking = book(app, ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    assert views.booking(booking.id, app.unit_of_work) == booking


def test_the_customer_is_sent_a_confirmation(
    app: App, ada: Customer, isolated_directories: Path
) -> None:
    booking = book(app, ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    confirmation = (
        isolated_directories / "mail" / f"{booking.id}-confirmation.txt"
    )
    assert "To: ada@example.com" in confirmation.read_text()
    assert "Total: £18.00 (includes VAT of £3.00)" in confirmation.read_text()


def test_an_empty_booking_is_rejected(app: App, ada: Customer) -> None:
    with pytest.raises(EmptyBookingError):
        book(app, ada, [], "bank_transfer")


@pytest.mark.parametrize("quantity", [0, -1])
def test_a_quantity_below_one_is_rejected(
    app: App, ada: Customer, quantity: int
) -> None:
    with pytest.raises(InvalidQuantityError):
        book(app, ada, [("TEE-STAGEDOOR", quantity)], "bank_transfer")


def test_an_unknown_item_is_rejected_and_nothing_is_saved(
    app: App, ada: Customer, isolated_directories: Path
) -> None:
    with pytest.raises(UnknownItemError):
        book(
            app, ada, [("TEE-STAGEDOOR", 1), ("NOPE-999", 1)], "bank_transfer"
        )

    assert not list((isolated_directories / "mail").glob("*"))


def test_the_booking_carries_its_totals(app: App, ada: Customer) -> None:
    booking = book(
        app,
        ada,
        [("MUC0314-ADULT", 2), ("PROG-MUCHADO", 1)],
        "bank_transfer",
        discount_code="FIRSTNIGHT10",
    )

    assert booking.subtotal == Decimal("70.00")
    assert booking.discount == Decimal("7.00")
    assert booking.total == Decimal("63.00")
    assert booking.vat == Decimal("9.60")


def test_an_unknown_discount_code_is_rejected(app: App, ada: Customer) -> None:
    with pytest.raises(UnknownDiscountCodeError):
        book(
            app,
            ada,
            [("TEE-STAGEDOOR", 1)],
            "bank_transfer",
            discount_code="FREESTUFF",
        )


def test_booking_takes_the_places(
    app: App, ada: Customer, places: InMemoryPlaceRepository
) -> None:
    book(app, ada, [("GDF0320-ADULT", 2)], "bank_transfer")

    assert places.left["GDF0320"] == 0


def test_we_cannot_sell_places_we_do_not_have(app: App, ada: Customer) -> None:
    with pytest.raises(NotEnoughPlacesError):
        book(app, ada, [("GDF0320-ADULT", 3)], "bank_transfer")


def test_a_rejected_booking_leaves_the_places_alone(
    app: App, ada: Customer, places: InMemoryPlaceRepository
) -> None:
    with pytest.raises(NotEnoughPlacesError):
        book(
            app,
            ada,
            [("MUC0314-ADULT", 5), ("GDF0320-ADULT", 3)],
            "bank_transfer",
        )

    assert places.left["MUC0314"] == 120


def test_the_booking_records_its_payment(app: App, ada: Customer) -> None:
    booking = book(app, ada, [("TEE-STAGEDOOR", 1)], "card", "pm_card_visa")

    assert booking.payment_method == "card"
    assert booking.payment_reference.startswith("pi_")
    assert booking.status == BookingStatus.PAID
    assert booking.payment_fee == Decimal("0.47")


def test_a_bank_transfer_confirmation_says_how_to_pay(
    app: App, ada: Customer, isolated_directories: Path
) -> None:
    booking = book(app, ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    confirmation = (
        isolated_directories / "mail" / f"{booking.id}-confirmation.txt"
    )
    assert f"quoting SD-{booking.id.upper()}" in confirmation.read_text()


def test_a_declined_card_says_why_and_books_nothing(
    app: App, ada: Customer, places: InMemoryPlaceRepository
) -> None:
    with pytest.raises(PaymentFailedError, match="Your card was declined."):
        book(app, ada, [("GDF0320-ADULT", 1)], "card", "pm_card_declined")

    assert places.left["GDF0320"] == 2


def test_a_declined_paypal_payment_says_why_and_books_nothing(
    app: App,
    ada: Customer,
    isolated_directories: Path,
    places: InMemoryPlaceRepository,
) -> None:
    with pytest.raises(PaymentFailedError, match="PayPal declined"):
        book(app, ada, [("GDF0320-ADULT", 1)], "paypal", "payer_declined")

    assert not (isolated_directories / "data").exists()
    assert places.left["GDF0320"] == 2


def test_a_bank_transfer_booking_is_awaiting_payment(
    app: App, ada: Customer
) -> None:
    booking = book(app, ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    assert booking.status == BookingStatus.AWAITING_PAYMENT


def test_paid_e_tickets_are_held_issued_and_invoiced(
    app: App, ada: Customer
) -> None:
    booking = book(app, ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa")

    assert len(booking.hold_references) == 1
    assert fakevenue.SEATS["MUC0314"] == 118
    assert booking.wallet_pass is not None
    assert booking.wallet_pass.startswith("https://wallet.example/")
    assert booking.invoice_number == "INV-000001"


def test_posted_tickets_get_a_tracking_number(
    app: App, ada_at_home: Customer
) -> None:
    booking = book(
        app,
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
    app: App,
    ada_at_home: Customer,
    places: InMemoryPlaceRepository,
) -> None:
    nowhere = Address("1 Nowhere Lane", "Nowhere", "XX1 1XX", "GB")

    with pytest.raises(FulfilmentError):
        book(
            app,
            replace(ada_at_home, address=nowhere),
            [("MUC0314-ADULT", 2)],
            "card",
            "pm_card_visa",
            delivery="post",
        )

    assert fakevenue.SEATS["MUC0314"] == 120
    assert places.left["MUC0314"] == 120


def test_posted_tickets_need_an_address(app: App, ada: Customer) -> None:
    with pytest.raises(MissingAddressError):
        book(
            app, ada, [("MUC0314-ADULT", 1)], "bank_transfer", delivery="post"
        )


def test_a_bank_transfer_is_not_issued_until_it_is_paid(
    app: App,
    ada: Customer,
) -> None:
    booking = book(app, ada, [("MUC0314-ADULT", 2)], "bank_transfer")

    assert booking.hold_references == ()
    assert booking.invoice_number is None


def test_a_booking_is_announced(app: App, ada: Customer) -> None:
    heard: list[BookingConfirmed] = []
    app.bus.subscribe(BookingConfirmed, heard.append)

    booking = book(app, ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    assert heard == [
        BookingConfirmed(
            booking_id=booking.id,
            customer_email="ada@example.com",
            total=Decimal("18.00"),
            placed_at=booking.placed_at,
        )
    ]


def test_a_reaction_that_fails_does_not_fail_the_booking(
    app: App,
    caplog: pytest.LogCaptureFixture,
) -> None:
    ada = Customer(name="Ada Lovelace", email="ada+shows@example.com")

    booking = book(app, ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa")

    assert views.booking(booking.id, app.unit_of_work) == booking
    assert "award_points failed to handle BookingConfirmed" in caplog.text


def test_a_bank_transfer_is_issued_once_it_is_paid(
    app: App, ada: Customer
) -> None:
    booking = book(app, ada, [("MUC0314-ADULT", 2)], "bank_transfer")

    app.bus.handle(MarkPaid(booking.id))

    paid = views.booking(booking.id, app.unit_of_work)
    assert paid.status == BookingStatus.PAID
    assert paid.invoice_number == "INV-000001"


def test_only_a_booking_awaiting_payment_can_be_marked_paid(
    app: App,
    ada: Customer,
) -> None:
    booking = book(app, ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa")

    with pytest.raises(IllegalTransitionError):
        app.bus.handle(MarkPaid(booking.id))


def test_a_paid_booking_can_be_checked_in(app: App, ada: Customer) -> None:
    booking = book(app, ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa")

    app.bus.handle(CheckIn(booking.id))

    checked_in = views.booking(booking.id, app.unit_of_work)
    assert checked_in.status == BookingStatus.CHECKED_IN


def test_a_booking_cannot_be_checked_in_twice(app: App, ada: Customer) -> None:
    booking = book(app, ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa")
    app.bus.handle(CheckIn(booking.id))

    with pytest.raises(IllegalTransitionError):
        app.bus.handle(CheckIn(booking.id))


def test_cancelling_an_unpaid_booking_gives_the_places_back(
    app: App, ada: Customer, places: InMemoryPlaceRepository
) -> None:
    booking = book(app, ada, [("GDF0320-ADULT", 2)], "bank_transfer")

    app.bus.handle(CancelBooking(booking.id))

    cancelled = views.booking(booking.id, app.unit_of_work)
    assert cancelled.status == BookingStatus.CANCELLED
    assert places.left["GDF0320"] == 2


def test_cancelling_a_paid_booking_refunds_it(
    app: App, ada: Customer, places: InMemoryPlaceRepository
) -> None:
    booking = book(app, ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa")

    app.bus.handle(CancelBooking(booking.id))

    refunded = views.booking(booking.id, app.unit_of_work)
    assert refunded.status == BookingStatus.REFUNDED
    assert places.left["MUC0314"] == 120
    assert fakevenue.SEATS["MUC0314"] == 120


def test_a_booking_that_has_been_used_cannot_be_cancelled(
    app: App,
    ada: Customer,
) -> None:
    booking = book(app, ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa")
    app.bus.handle(CheckIn(booking.id))

    with pytest.raises(IllegalTransitionError):
        app.bus.handle(CancelBooking(booking.id))


# Written after a customer was charged for a booking that was never saved.

NOON = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)


def test_a_booking_records_when_it_was_made(
    settings: Settings, ada: Customer
) -> None:
    uow = InMemoryUnitOfWork()
    app = bootstrap(settings, unit_of_work=lambda: uow, clock=lambda: NOON)

    booking = book(app, ada, [("TEE-STAGEDOOR", 1)], "bank_transfer")

    assert booking.placed_at == NOON


def test_a_bank_transfer_is_paid_by_quoting_the_booking_id(
    app: App, ada: Customer
) -> None:
    app.bus.handle(
        MakeBooking(
            booking_id="3f9a1c2b7d4e",
            customer=ada,
            items=(("TEE-STAGEDOOR", 1),),
            payment_method="bank_transfer",
        )
    )

    booking = views.booking("3f9a1c2b7d4e", app.unit_of_work)
    assert booking.payment_reference == "SD-3F9A1C2B7D4E"


def test_a_booking_that_cannot_be_saved_is_not_confirmed(
    settings: Settings, ada: Customer, isolated_directories: Path
) -> None:
    uow = InMemoryUnitOfWork(bookings=FailingRepository())
    app = bootstrap(settings, sleep=no_sleep, unit_of_work=lambda: uow)

    with pytest.raises(OSError):
        app.bus.handle(
            MakeBooking(
                booking_id="abc123",
                customer=ada,
                items=(("TEE-STAGEDOOR", 1),),
                payment_method="card",
                payment_token="pm_card_visa",
            )
        )

    mail = isolated_directories / "mail"
    assert not (mail / "abc123-confirmation.txt").exists()


def test_a_booking_that_cannot_be_saved_is_not_paid_for(
    settings: Settings, ada: Customer
) -> None:
    card = FakePaymentMethod()
    uow = InMemoryUnitOfWork(bookings=FailingRepository())
    app = bootstrap(
        settings, unit_of_work=lambda: uow, payment_methods={"card": card}
    )

    with pytest.raises(OSError):
        book(app, ada, [("TEE-STAGEDOOR", 1)], "card", "tok_ok")

    assert card.charges == []


def test_a_booking_that_cannot_be_saved_gives_its_places_back(
    settings: Settings, ada: Customer, places: InMemoryPlaceRepository
) -> None:
    uow = InMemoryUnitOfWork(bookings=FailingRepository(), places=places)
    app = bootstrap(settings, unit_of_work=lambda: uow)

    with pytest.raises(OSError):
        book(app, ada, [("GDF0320-ADULT", 2)], "bank_transfer")

    assert places.left["GDF0320"] == 2


def test_a_booking_survives_a_busy_moment_at_stripe(
    app: App, ada: Customer
) -> None:
    fakestripe.simulate_outage = 2

    booking = book(app, ada, [("TEE-STAGEDOOR", 1)], "card", "pm_card_visa")

    assert booking.payment_reference.startswith("pi_")


def test_a_booking_survives_a_busy_moment_at_the_venue(
    app: App, ada: Customer
) -> None:
    fakevenue.simulate_outage = 1

    booking = book(app, ada, [("MUC0314-ADULT", 2)], "card", "pm_card_visa")

    assert len(booking.hold_references) == 1
