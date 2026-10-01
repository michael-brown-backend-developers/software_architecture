"""Building StageDoor.

This is the one place that knows which concrete classes StageDoor runs
with, and how they fit together. Everything is built here, once, from the
settings, and handed to the code that needs it.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from stagedoor.fulfilment import Fulfilment, create_fulfilment
from stagedoor.payments import create_payment_method
from stagedoor.payments.base import PaymentMethod
from stagedoor.settings import Settings


@dataclass(frozen=True)
class App:
    """Everything StageDoor needs to take a booking, built and ready."""

    payment_methods: Mapping[str, PaymentMethod]
    fulfilment: Fulfilment


def bootstrap(settings: Settings) -> App:
    """Build StageDoor from its settings."""
    return App(
        payment_methods={
            name: create_payment_method(name, settings)
            for name in sorted(settings.payment_methods)
        },
        fulfilment=create_fulfilment(settings),
    )
