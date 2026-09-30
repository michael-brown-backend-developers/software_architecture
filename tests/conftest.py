from collections.abc import Iterator
from pathlib import Path

import pytest

from stagedoor.capacity import PLACES
from stagedoor.models import Customer


@pytest.fixture(autouse=True)
def isolated_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Give every test its own empty data and mail directories."""
    monkeypatch.setenv("STAGEDOOR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("STAGEDOOR_MAIL_DIR", str(tmp_path / "mail"))
    return tmp_path


@pytest.fixture(autouse=True)
def restore_places() -> Iterator[None]:
    """Put the places back the way they were after every test."""
    saved = dict(PLACES)
    yield
    PLACES.clear()
    PLACES.update(saved)


@pytest.fixture
def ada() -> Customer:
    return Customer(name="Ada Lovelace", email="ada@example.com")
