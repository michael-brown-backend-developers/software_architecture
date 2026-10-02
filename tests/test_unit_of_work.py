"""What every unit of work must do, checked against each of them.

The PostgreSQL tests are skipped if the database is not running.
"""

from decimal import Decimal

import pytest

from stagedoor.adapters.in_memory import InMemoryUnitOfWork
from stagedoor.adapters.postgres import SqlAlchemyUnitOfWork, connect
from stagedoor.application.ports import UnitOfWork
from stagedoor.domain.exceptions import NotEnoughPlacesError
from stagedoor.domain.models import BookingLine, ItemKind

LAST_TWO = [
    BookingLine(
        "GDF0320-ADULT",
        "Ticket",
        ItemKind.TICKET,
        "GDF0320",
        Decimal("26.50"),
        2,
    )
]


@pytest.fixture(params=["memory", "postgres"])
def unit_of_work(request: pytest.FixtureRequest) -> UnitOfWork:
    if request.param == "memory":
        return InMemoryUnitOfWork()
    database = request.getfixturevalue("database")
    return SqlAlchemyUnitOfWork(connect(database))


def test_committed_changes_are_kept(unit_of_work: UnitOfWork) -> None:
    with unit_of_work as uow:
        uow.places.take(LAST_TWO)
        uow.commit()

    with unit_of_work as uow, pytest.raises(NotEnoughPlacesError):
        uow.places.take(LAST_TWO)


def test_changes_are_undone_without_a_commit(
    unit_of_work: UnitOfWork,
) -> None:
    with unit_of_work as uow:
        uow.places.take(LAST_TWO)

    with unit_of_work as uow:
        uow.places.take(LAST_TWO)


def test_changes_are_undone_when_something_goes_wrong(
    unit_of_work: UnitOfWork,
) -> None:
    with pytest.raises(RuntimeError), unit_of_work as uow:
        uow.places.take(LAST_TWO)
        raise RuntimeError("The card machine is on fire.")

    with unit_of_work as uow:
        uow.places.take(LAST_TWO)
