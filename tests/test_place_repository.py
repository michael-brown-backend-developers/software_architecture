"""What every place repository must do, checked against each of them.

The PostgreSQL tests are skipped if the database is not running.
"""

from decimal import Decimal

import pytest
from fakes import InMemoryPlaceRepository

from stagedoor.db import SqlAlchemyPlaceRepository, connect
from stagedoor.exceptions import NotEnoughPlacesError
from stagedoor.models import BookingLine, ItemKind
from stagedoor.repository import PlaceRepository


@pytest.fixture(params=["memory", "postgres"])
def places(request: pytest.FixtureRequest) -> PlaceRepository:
    if request.param == "memory":
        return InMemoryPlaceRepository()
    database = request.getfixturevalue("database")
    return SqlAlchemyPlaceRepository(connect(database))


def tickets(performance: str, quantity: int) -> BookingLine:
    return BookingLine(
        f"{performance}-ADULT",
        "Ticket",
        ItemKind.TICKET,
        performance,
        Decimal("20.00"),
        quantity,
    )


def test_enough_places_passes(places: PlaceRepository) -> None:
    places.check([tickets("GDF0320", 2)])


def test_not_enough_places_raises(places: PlaceRepository) -> None:
    with pytest.raises(NotEnoughPlacesError) as error:
        places.check([tickets("GDF0320", 3)])

    assert error.value.available == 2


def test_lines_for_the_same_performance_are_added_up(
    places: PlaceRepository,
) -> None:
    with pytest.raises(NotEnoughPlacesError):
        places.check([tickets("GDF0320", 2), tickets("GDF0320", 1)])


def test_extras_do_not_need_places(places: PlaceRepository) -> None:
    programmes = BookingLine(
        "PROG-MUCHADO",
        "Programme",
        ItemKind.PROGRAMME,
        None,
        Decimal("6"),
        500,
    )

    places.check([programmes])


def test_places_taken_are_gone(places: PlaceRepository) -> None:
    places.take([tickets("GDF0320", 2)])

    with pytest.raises(NotEnoughPlacesError):
        places.check([tickets("GDF0320", 1)])


def test_places_given_back_can_be_sold_again(
    places: PlaceRepository,
) -> None:
    places.take([tickets("GDF0320", 2)])
    places.give_back([tickets("GDF0320", 2)])

    places.check([tickets("GDF0320", 2)])


@pytest.mark.xfail(strict=True, reason="checked, then taken: chapter 11")
def test_the_last_places_cannot_be_sold_twice(
    places: PlaceRepository,
) -> None:
    # Two terminals, each selling the last two places for The Guido Father.
    last_two = [tickets("GDF0320", 2)]
    places.check(last_two)
    places.check(last_two)
    places.take(last_two)

    with pytest.raises(NotEnoughPlacesError):
        places.take(last_two)
