import os
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import fakeroyalmail
import fakestripe
import fakevenue
import fakewallet
import pytest
from fakes import (
    InMemoryBookingRepository,
    InMemoryPlaceRepository,
    no_sleep,
)
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from stagedoor.bookings import BookingService
from stagedoor.bootstrap import App, bootstrap
from stagedoor.db import Base, create_tables
from stagedoor.models import Address, Customer
from stagedoor.settings import Settings


@pytest.fixture(autouse=True)
def isolated_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Give every test its own empty data and mail directories."""
    monkeypatch.setenv("STAGEDOOR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("STAGEDOOR_MAIL_DIR", str(tmp_path / "mail"))
    return tmp_path


TEST_DATABASE_URL = os.environ.get(
    "STAGEDOOR_TEST_DATABASE_URL",
    "postgresql+psycopg://stagedoor:stagedoor@localhost:5433/stagedoor_test",
)


@pytest.fixture(scope="session")
def test_database() -> str:
    """The test database, with StageDoor's tables, or a skipped test."""
    try:
        with create_engine(TEST_DATABASE_URL).connect():
            pass
    except OperationalError:
        pytest.skip("PostgreSQL is not running: docker compose up -d")
    # The tables are made afresh, in case they have changed since last time.
    Base.metadata.drop_all(create_engine(TEST_DATABASE_URL))
    create_tables(TEST_DATABASE_URL)
    return TEST_DATABASE_URL


@pytest.fixture
def database(test_database: str) -> str:
    """The test database, emptied, with every performance's places back."""
    with create_engine(test_database).begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(text(f"DELETE FROM {table.name}"))
    create_tables(test_database)
    return test_database


@pytest.fixture
def settings(isolated_directories: Path) -> Settings:
    """Development settings, with the test's own data and mail directories."""
    return Settings.from_env(
        {
            "STAGEDOOR_DATA_DIR": str(isolated_directories / "data"),
            "STAGEDOOR_MAIL_DIR": str(isolated_directories / "mail"),
        }
    )


@pytest.fixture
def app(settings: Settings) -> App:
    """StageDoor as it runs in development, except that retries never wait."""
    return bootstrap(settings, sleep=no_sleep)


@pytest.fixture
def places() -> InMemoryPlaceRepository:
    """Every performance, with all of its places."""
    return InMemoryPlaceRepository()


@pytest.fixture
def service(app: App, places: InMemoryPlaceRepository) -> BookingService:
    """The booking service, keeping its bookings and places in memory."""
    return replace(
        app.bookings, bookings=InMemoryBookingRepository(), places=places
    )


@pytest.fixture(autouse=True)
def reset_fakes() -> Iterator[None]:
    """Put the stand-in libraries back as they were after every test."""
    seats = dict(fakevenue.SEATS)
    yield
    fakevenue.SEATS.clear()
    fakevenue.SEATS.update(seats)
    fakevenue.simulate_outage = False
    fakewallet.simulate_outage = False
    fakeroyalmail.simulate_outage = False
    fakestripe.simulate_outage = False
    fakestripe._by_idempotency_key.clear()


@pytest.fixture
def ada() -> Customer:
    return Customer(name="Ada Lovelace", email="ada@example.com")


@pytest.fixture
def ada_at_home() -> Customer:
    return Customer(
        name="Ada Lovelace",
        email="ada@example.com",
        address=Address("12 St James's Square", "London", "SW1Y 4JH", "GB"),
    )
