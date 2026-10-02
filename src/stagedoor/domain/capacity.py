"""How many places each performance has, and how many a booking needs.

The places left are kept with the bookings, so every terminal sees the same
numbers. This module only knows how many each performance starts with, and
how to count the places a booking asks for.
"""

from collections import Counter
from collections.abc import Sequence

from stagedoor.domain.models import BookingLine

CAPACITY: dict[str, int] = {
    "MUC0314": 120,
    "MUC0315": 80,
    "GDF0320": 2,
}


def places_wanted(lines: Sequence[BookingLine]) -> Counter[str]:
    """How many places each performance on a booking needs.

    Several lines can be for the same performance - adults and concessions,
    say - so they are added up.
    """
    wanted: Counter[str] = Counter()
    for line in lines:
        if line.performance is not None:
            wanted[line.performance] += line.quantity
    return wanted
