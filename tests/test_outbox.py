"""What every outbox must do, checked against each of them.

The PostgreSQL tests are skipped if the database is not running.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fakes import InMemoryUnitOfWork

from stagedoor.db import SqlAlchemyUnitOfWork, connect
from stagedoor.events import BookingConfirmed
from stagedoor.unit_of_work import UnitOfWork

# By then, everything added to an outbox is due.
LATER = datetime(2100, 1, 1, tzinfo=UTC)

CONFIRMED = BookingConfirmed(
    booking_id="abc123",
    customer_email="ada@example.com",
    total=Decimal("18.00"),
    placed_at=datetime(2026, 3, 14, 12, 0, tzinfo=UTC),
)


@pytest.fixture(params=["memory", "postgres"])
def unit_of_work(request: pytest.FixtureRequest) -> UnitOfWork:
    if request.param == "memory":
        return InMemoryUnitOfWork()
    database = request.getfixturevalue("database")
    return SqlAlchemyUnitOfWork(connect(database))


def add_one(unit_of_work: UnitOfWork) -> None:
    with unit_of_work as uow:
        uow.outbox.add(CONFIRMED)
        uow.commit()


def test_an_event_comes_back_as_it_went_in(unit_of_work: UnitOfWork) -> None:
    add_one(unit_of_work)

    with unit_of_work as uow:
        message = uow.outbox.next_due(LATER)

    assert message is not None
    assert message.event == CONFIRMED
    assert message.attempts == 0
    assert message.handled == frozenset()


def test_nothing_is_kept_unless_it_is_committed(
    unit_of_work: UnitOfWork,
) -> None:
    with unit_of_work as uow:
        uow.outbox.add(CONFIRMED)

    with unit_of_work as uow:
        assert uow.outbox.next_due(LATER) is None


def test_a_message_that_is_done_is_not_due_again(
    unit_of_work: UnitOfWork,
) -> None:
    add_one(unit_of_work)
    with unit_of_work as uow:
        message = uow.outbox.next_due(LATER)
        assert message is not None
        uow.outbox.done(message.id)
        uow.commit()

    with unit_of_work as uow:
        assert uow.outbox.next_due(LATER) is None


def test_a_failed_message_is_due_again_when_it_is_retried(
    unit_of_work: UnitOfWork,
) -> None:
    add_one(unit_of_work)
    with unit_of_work as uow:
        message = uow.outbox.next_due(LATER)
        assert message is not None
        uow.outbox.handled(message.id, "award_points")
        uow.outbox.failed(message.id, "send_confirmation: down", LATER)
        uow.commit()

    with unit_of_work as uow:
        assert uow.outbox.next_due(LATER - timedelta(seconds=1)) is None
        retried = uow.outbox.next_due(LATER)

    assert retried is not None
    assert retried.attempts == 1
    assert retried.handled == {"award_points"}


def test_a_message_given_up_on_is_never_due_again(
    unit_of_work: UnitOfWork,
) -> None:
    add_one(unit_of_work)
    with unit_of_work as uow:
        message = uow.outbox.next_due(LATER)
        assert message is not None
        uow.outbox.failed(message.id, "send_confirmation: down", None)
        uow.commit()

    with unit_of_work as uow:
        assert uow.outbox.next_due(LATER) is None


def test_two_workers_never_claim_the_same_message(database: str) -> None:
    sessions = connect(database)
    add_one(SqlAlchemyUnitOfWork(sessions))

    with SqlAlchemyUnitOfWork(sessions) as first:
        assert first.outbox.next_due(LATER) is not None
        with SqlAlchemyUnitOfWork(sessions) as second:
            assert second.outbox.next_due(LATER) is None
