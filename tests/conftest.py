from collections.abc import Iterator
from pathlib import Path

import fakeroyalmail
import fakestripe
import fakevenue
import fakewallet
import pytest
from fakes import no_sleep

from stagedoor.bookings import BookingService
from stagedoor.bootstrap import App, bootstrap
from stagedoor.capacity import PLACES
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
def service(app: App) -> BookingService:
    return app.bookings


@pytest.fixture(autouse=True)
def restore_places() -> Iterator[None]:
    """Put the places back the way they were after every test."""
    saved = dict(PLACES)
    yield
    PLACES.clear()
    PLACES.update(saved)


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
