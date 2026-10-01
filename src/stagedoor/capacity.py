"""How many places each performance has left.

The box office owns these numbers. They live in memory, so they go back to
the same numbers every time the program starts. That is fine for now.
"""

from collections import Counter
from collections.abc import Sequence

from stagedoor.exceptions import NotEnoughPlacesError
from stagedoor.models import BookingLine

PLACES: dict[str, int] = {
    "MUC0314": 120,
    "MUC0315": 80,
    "GDF0320": 2,
}


def check_places(lines: Sequence[BookingLine]) -> None:
    """Raise NotEnoughPlacesError unless every performance has room.

    Several lines can be for the same performance - adults and concessions,
    say - so the places are added up before they are checked.
    """
    wanted: Counter[str] = Counter()
    for line in lines:
        if line.performance is not None:
            wanted[line.performance] += line.quantity

    for performance, quantity in wanted.items():
        available = PLACES.get(performance, 0)
        if available < quantity:
            raise NotEnoughPlacesError(performance, quantity, available)


def take_places(lines: Sequence[BookingLine]) -> None:
    """Take the places off sale. Call check_places() first."""
    for line in lines:
        if line.performance is not None:
            PLACES[line.performance] -= line.quantity


def give_back_places(lines: Sequence[BookingLine]) -> None:
    """Put the places back on sale."""
    for line in lines:
        if line.performance is not None:
            PLACES[line.performance] += line.quantity
