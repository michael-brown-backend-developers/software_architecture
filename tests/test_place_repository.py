"""What every place repository must do, checked against each of them.

The PostgreSQL tests are skipped if the database is not running.
"""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fakes import InMemoryPlaceRepository

from stagedoor.db import SqlAlchemyUnitOfWork, connect
from stagedoor.exceptions import NotEnoughPlacesError
from stagedoor.models import BookingLine, ItemKind
from stagedoor.repository import PlaceRepository


@pytest.fixture(params=["memory", "postgres"])
def places(request: pytest.FixtureRequest) -> Iterator[PlaceRepository]:
    if request.param == "memory":
        yield InMemoryPlaceRepository()
        return
    database = request.getfixturevalue("database")
    with SqlAlchemyUnitOfWork(connect(database)) as uow:
        yield uow.places


def tickets(performance: str, quantity: int) -> BookingLine:
    return BookingLine(
        f"{performance}-ADULT",
        "Ticket",
        ItemKind.TICKET,
        performance,
        Decimal("20.00"),
        quantity,
    )


def test_places_can_be_taken(places: PlaceRepository) -> None:
    places.take([tickets("GDF0320", 2)])


def test_not_enough_places_raises(places: PlaceRepository) -> None:
    with pytest.raises(NotEnoughPlacesError) as error:
        places.take([tickets("GDF0320", 3)])

    assert error.value.available == 2


def test_lines_for_the_same_performance_are_added_up(
    places: PlaceRepository,
) -> None:
    with pytest.raises(NotEnoughPlacesError):
        places.take([tickets("GDF0320", 2), tickets("GDF0320", 1)])


def test_extras_do_not_need_places(places: PlaceRepository) -> None:
    programmes = BookingLine(
        "PROG-MUCHADO",
        "Programme",
        ItemKind.PROGRAMME,
        None,
        Decimal("6"),
        500,
    )

    places.take([programmes])


def test_places_given_back_can_be_sold_again(
    places: PlaceRepository,
) -> None:
    places.take([tickets("GDF0320", 2)])
    places.give_back([tickets("GDF0320", 2)])

    places.take([tickets("GDF0320", 2)])


def test_the_last_places_cannot_be_sold_twice(
    places: PlaceRepository,
) -> None:
    # Two terminals, each selling the last two places for The Guido Father.
    last_two = [tickets("GDF0320", 2)]
    places.take(last_two)

    with pytest.raises(NotEnoughPlacesError):
        places.take(last_two)
