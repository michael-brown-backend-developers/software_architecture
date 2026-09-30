from decimal import Decimal

import pytest

from stagedoor.capacity import PLACES, check_places, take_places
from stagedoor.exceptions import NotEnoughPlacesError
from stagedoor.models import BookingLine, ItemKind


def tickets(performance: str, quantity: int) -> BookingLine:
    return BookingLine(
        f"{performance}-ADULT",
        "Ticket",
        ItemKind.TICKET,
        performance,
        Decimal("20.00"),
        quantity,
    )


def test_enough_places_passes() -> None:
    check_places([tickets("GDF0320", 2)])


def test_not_enough_places_raises() -> None:
    with pytest.raises(NotEnoughPlacesError) as error:
        check_places([tickets("GDF0320", 3)])

    assert error.value.available == 2


def test_lines_for_the_same_performance_are_added_up() -> None:
    with pytest.raises(NotEnoughPlacesError):
        check_places([tickets("GDF0320", 2), tickets("GDF0320", 1)])


def test_extras_do_not_need_places() -> None:
    programmes = BookingLine(
        "PROG-MUCHADO",
        "Programme",
        ItemKind.PROGRAMME,
        None,
        Decimal("6"),
        500,
    )

    check_places([programmes])


def test_checking_does_not_take_anything() -> None:
    check_places([tickets("MUC0314", 5)])

    assert PLACES["MUC0314"] == 120


def test_taking_places() -> None:
    take_places([tickets("MUC0314", 5), tickets("MUC0314", 1)])

    assert PLACES["MUC0314"] == 114
