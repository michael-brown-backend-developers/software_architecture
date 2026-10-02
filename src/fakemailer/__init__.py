"""A stand-in for an email provider's Python library.

StageDoor needs an email provider whose API never changes and never needs a
network connection, so this package imitates the general shape of one: a
client made with an API key, and a send() that returns the provider's ID
for the message. It delivers each message as a text file in a folder of
your choosing, so you can read exactly what the customer would receive.

    simulate_outage  set it to True, and every send raises ProviderError(503);
                     set it to a number, and only that many sends fail
"""

from pathlib import Path
from uuid import uuid4

__all__ = ["EmailClient", "ProviderError", "simulate_outage"]

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


class ProviderError(Exception):
    """The provider said no. ``status`` is an HTTP status code."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"{status} {message}")
        self.status = status
        self.message = message


class EmailClient:
    """A connection to the email provider."""

    def __init__(self, api_key: str, folder: Path) -> None:
        self.api_key = api_key
        self.folder = folder

    def send(self, *, to: str, subject: str, text: str) -> str:
        """Send an email, and return the provider's ID for it."""
        if _outage():
            raise ProviderError(503, "Service Unavailable")
        message_id = f"msg_{uuid4().hex[:12]}"
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / f"{message_id}.txt").write_text(
            f"To: {to}\nSubject: {subject}\n\n{text}", encoding="utf-8"
        )
        return message_id
