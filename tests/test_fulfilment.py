from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import fakeroyalmail
import fakevenue
import fakewallet
import pytest

from stagedoor.exceptions import FulfilmentError
from stagedoor.fulfilment import Fulfilment
from stagedoor.fulfilment.royal_mail import RoyalMailShipping
from stagedoor.fulfilment.venue import VenueHolds
from stagedoor.fulfilment.wallet import WalletPasses
from stagedoor.models import (
    Address,
    Booking,
    BookingLine,
    BookingStatus,
    Customer,
    ItemKind,
)


def ticket(performance: str, quantity: int) -> BookingLine:
    return BookingLine(
        f"{performance}-ADULT",
        "Ticket",
        ItemKind.TICKET,
        performance,
        Decimal("30.00"),
        quantity,
    )


def booking_for(
    customer: Customer, delivery: str, *lines: BookingLine
) -> Booking:
    return Booking(
        id="abc123",
        customer=customer,
        lines=lines,
        discount_code=None,
        subtotal=Decimal("60.00"),
        discount=Decimal("0.00"),
        delivery=delivery,
        delivery_fee=Decimal("0.00"),
        total=Decimal("60.00"),
        vat=Decimal("10.00"),
        payment_method="card",
        payment_reference="pi_123",
        status=BookingStatus.PAID,
        payment_fee=Decimal("1.10"),
        placed_at=datetime(2026, 9, 30, 9, 15, tzinfo=UTC),
    )


@pytest.fixture
def waits() -> list[float]:
    """How long each retry waited. Nothing really waits."""
    return []


@pytest.fixture
def fulfilment(waits: list[float]) -> Fulfilment:
    return Fulfilment(
        venue=VenueHolds("https://venue.test", "key", sleep=waits.append),
        wallet=WalletPasses("key"),
        royal_mail=RoyalMailShipping("key", sleep=waits.append),
    )


def test_e_tickets_are_held_issued_and_invoiced(
    fulfilment: Fulfilment, ada: Customer
) -> None:
    result = fulfilment.fulfil(
        booking_for(ada, "e_ticket", ticket("MUC0314", 2))
    )

    assert len(result.hold_references) == 1
    assert fakevenue.SEATS["MUC0314"] == 118
    assert result.wallet_pass is not None
    assert result.tracking_number is None
    assert result.invoice_number == "INV-000001"


def test_posted_tickets_are_sent_by_royal_mail(
    fulfilment: Fulfilment, ada_at_home: Customer
) -> None:
    result = fulfilment.fulfil(
        booking_for(ada_at_home, "post", ticket("MUC0314", 2))
    )

    assert result.tracking_number is not None
    assert result.tracking_number.endswith("GB")
    assert result.wallet_pass is None


def test_a_failed_label_gives_the_seats_back(
    fulfilment: Fulfilment, ada_at_home: Customer
) -> None:
    assert ada_at_home.address is not None
    nowhere = replace(ada_at_home.address, postcode="XX1 1XX")
    customer = replace(ada_at_home, address=nowhere)

    with pytest.raises(FulfilmentError):
        fulfilment.fulfil(booking_for(customer, "post", ticket("MUC0314", 2)))

    assert fakevenue.SEATS["MUC0314"] == 120


def test_a_wallet_outage_gives_the_seats_back(
    fulfilment: Fulfilment, ada: Customer
) -> None:
    fakewallet.simulate_outage = True

    with pytest.raises(FulfilmentError):
        fulfilment.fulfil(booking_for(ada, "e_ticket", ticket("MUC0314", 2)))

    assert fakevenue.SEATS["MUC0314"] == 120


def test_a_refused_hold_gives_back_the_ones_already_made(
    fulfilment: Fulfilment, ada: Customer
) -> None:
    booking = booking_for(
        ada, "box_office", ticket("MUC0314", 2), ticket("GDF0320", 3)
    )

    with pytest.raises(FulfilmentError, match="Not enough seats"):
        fulfilment.fulfil(booking)

    assert fakevenue.SEATS["MUC0314"] == 120


def test_collected_tickets_are_held_and_invoiced_only(
    fulfilment: Fulfilment, ada: Customer
) -> None:
    result = fulfilment.fulfil(
        booking_for(ada, "box_office", ticket("MUC0315", 4))
    )

    assert fakevenue.SEATS["MUC0315"] == 76
    assert result.wallet_pass is None
    assert result.tracking_number is None


def test_posting_to_the_eu_uses_royal_mails_eu_service(
    fulfilment: Fulfilment, ada: Customer
) -> None:
    paris = Address("1 Rue de Rivoli", "Paris", "75001", "FR")
    customer = replace(ada, address=paris)

    result = fulfilment.fulfil(
        booking_for(customer, "post", ticket("MUC0314", 1))
    )

    assert result.tracking_number is not None
    assert result.tracking_number.endswith("FR")


def test_a_brief_royal_mail_outage_is_tried_again(
    fulfilment: Fulfilment, ada_at_home: Customer, waits: list[float]
) -> None:
    fakeroyalmail.simulate_outage = 1

    result = fulfilment.fulfil(
        booking_for(ada_at_home, "post", ticket("MUC0314", 2))
    )

    assert result.tracking_number is not None
    assert waits == [0.5]


def test_a_brief_venue_outage_is_tried_again(
    fulfilment: Fulfilment, ada: Customer, waits: list[float]
) -> None:
    fakevenue.simulate_outage = 1

    result = fulfilment.fulfil(
        booking_for(ada, "box_office", ticket("MUC0314", 2))
    )

    assert len(result.hold_references) == 1
    assert waits == [1.0]
