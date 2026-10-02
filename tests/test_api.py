from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from stagedoor.api import api, stagedoor
from stagedoor.bookings import BookingService
from stagedoor.bootstrap import App


@pytest.fixture
def client(app: App, service: BookingService) -> Iterator[TestClient]:
    """The API, with StageDoor keeping everything in memory."""
    api.dependency_overrides[stagedoor] = lambda: replace(
        app, bookings=service
    )
    yield TestClient(api, raise_server_exceptions=False)
    api.dependency_overrides.clear()


def book(client: TestClient, **changes: object) -> dict[str, object]:
    request = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "items": {"MUC0314-ADULT": 2},
        "payment_method": "bank_transfer",
    }
    response = client.post("/bookings", json=request | changes)
    assert response.status_code == 201, response.text
    booking: dict[str, object] = response.json()
    return booking


def test_a_booking_can_be_made(client: TestClient) -> None:
    booking = book(client)

    assert booking["total"] == "64.00"
    assert booking["status"] == "awaiting_payment"


def test_a_booking_can_be_looked_up(client: TestClient) -> None:
    booking = book(client)

    response = client.get(f"/bookings/{booking['id']}")

    assert response.json() == booking


def test_a_missing_booking_is_not_found(client: TestClient) -> None:
    response = client.get("/bookings/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "No booking with ID 'does-not-exist'"}


def test_a_bank_transfer_can_be_marked_paid(client: TestClient) -> None:
    booking = book(client)

    response = client.post(f"/bookings/{booking['id']}/paid")

    assert response.json()["status"] == "paid"


def test_an_unpaid_booking_cannot_be_checked_in(client: TestClient) -> None:
    booking = book(client)

    response = client.post(f"/bookings/{booking['id']}/check-in")

    assert response.status_code == 409


def test_a_declined_card_is_explained(client: TestClient) -> None:
    response = client.post(
        "/bookings",
        json={
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "items": {"MUC0314-ADULT": 2},
            "payment_method": "card",
            "payment_token": "pm_card_declined",
        },
    )

    assert response.status_code == 402
    assert response.json() == {"detail": "Your card was declined."}


@pytest.mark.xfail(strict=True, reason="a 500, mapped in one route only")
def test_selling_places_we_do_not_have_is_refused(client: TestClient) -> None:
    response = client.post(
        "/bookings",
        json={
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "items": {"GDF0320-ADULT": 3},
            "payment_method": "bank_transfer",
        },
    )

    assert response.status_code == 409
