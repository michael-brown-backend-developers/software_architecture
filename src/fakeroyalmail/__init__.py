"""A stand-in for Royal Mail's shipping API.

Weights are whole grams, the service is one of Royal Mail's own codes, and
the answer is a tracking number. A failure raises RoyalMailError.

    XX1 1XX          a postcode Royal Mail cannot deliver to
    simulate_outage  set it to True, and every call raises RoyalMailError;
                     set it to a number, and only that many calls fail
"""

from random import randint

__all__ = ["RoyalMailClient", "RoyalMailError", "simulate_outage"]

SERVICES = {"TPN48", "INT-EU", "INT-ROW"}
simulate_outage: bool | int = False


def _outage() -> bool:
    """Whether this call should fail. A number counts down to recovery."""
    global simulate_outage
    if simulate_outage is True:
        return True
    if simulate_outage:
        simulate_outage -= 1
        return True
    return False


class RoyalMailError(Exception):
    """Royal Mail could not book the shipment."""


class RoyalMailClient:
    """A connection to Royal Mail's shipping API."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def create_shipment(
        self, *, weight_grams: int, postcode: str, country: str, service: str
    ) -> str:
        """Book a shipment, and return its tracking number."""
        if _outage():
            raise RoyalMailError("Royal Mail is not responding.")
        if service not in SERVICES:
            raise RoyalMailError(f"Unknown service {service!r}")
        if postcode.strip().upper() == "XX1 1XX":
            raise RoyalMailError(f"Cannot deliver to {postcode}")
        if weight_grams <= 0:
            raise RoyalMailError("A shipment must weigh something.")
        return f"RM{randint(100000000, 999999999)}{country.upper()[:2]}"
