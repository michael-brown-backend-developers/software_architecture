"""A stand-in for a theatre's own box-office system.

The venue keeps its own count of the seats left for every performance, and
StageDoor has to hold seats in it for every ticket we sell. Its API is the
venue's, not ours: a hold comes back as a dictionary with camelCase keys,
and a refusal is an exception carrying an HTTP-style status code.

    SEATS            the venue's own count of seats left, by performance
    simulate_outage  set it to True, and every call raises VenueAPIError(503);
                     set it to a number, and only that many calls fail
"""

from uuid import uuid4

__all__ = ["SEATS", "VenueAPIError", "VenueClient", "simulate_outage"]

SEATS: dict[str, int] = {
    "MUC0314": 120,
    "MUC0315": 80,
    "GDF0320": 2,
}
simulate_outage: bool | int = False

_holds: dict[str, tuple[str, int]] = {}


def _outage() -> bool:
    """Whether this call should fail. A number counts down to recovery."""
    global simulate_outage
    if simulate_outage is True:
        return True
    if simulate_outage:
        simulate_outage -= 1
        return True
    return False


class VenueAPIError(Exception):
    """The venue's system said no. ``status`` is an HTTP status code."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"{status} {message}")
        self.status = status
        self.message = message


class VenueClient:
    """A connection to the venue's box-office system."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key

    def _connect(self) -> None:
        if _outage():
            raise VenueAPIError(503, "Service Unavailable")

    def create_hold(self, performance_code: str, seats: int) -> dict[str, str]:
        """Hold ``seats`` seats for a performance until they are released."""
        self._connect()
        available = SEATS.get(performance_code)
        if available is None:
            raise VenueAPIError(404, f"No performance {performance_code}")
        if available < seats:
            raise VenueAPIError(409, "Not enough seats")
        SEATS[performance_code] = available - seats
        hold_ref = f"H-{uuid4().hex[:10].upper()}"
        _holds[hold_ref] = (performance_code, seats)
        return {
            "holdRef": hold_ref,
            "performanceCode": performance_code,
            "seatCount": str(seats),
        }

    def cancel_hold(self, hold_ref: str) -> None:
        """Release a hold, and give its seats back."""
        self._connect()
        if hold_ref not in _holds:
            raise VenueAPIError(404, f"No hold {hold_ref}")
        performance_code, seats = _holds.pop(hold_ref)
        SEATS[performance_code] += seats
