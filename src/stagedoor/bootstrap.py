"""Building StageDoor.

This is the one place that knows which concrete classes StageDoor runs
with, and how they fit together. Everything is built here, once, from the
settings, and handed to the code that needs it.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from stagedoor.alerts import notify_sales_team
from stagedoor.analytics import record_sale
from stagedoor.bus import EventBus
from stagedoor.events import BookingConfirmed
from stagedoor.fulfilment import Fulfilment, create_fulfilment
from stagedoor.loyalty import award_points
from stagedoor.payments import create_payment_method
from stagedoor.payments.base import PaymentMethod
from stagedoor.settings import Settings


@dataclass(frozen=True)
class App:
    """Everything StageDoor needs to take a booking, built and ready."""

    payment_methods: Mapping[str, PaymentMethod]
    fulfilment: Fulfilment
    bus: EventBus


def bootstrap(settings: Settings) -> App:
    """Build StageDoor from its settings."""
    # Everything that happens because a booking was made.
    bus = EventBus()
    bus.subscribe(BookingConfirmed, award_points)
    bus.subscribe(BookingConfirmed, record_sale)
    bus.subscribe(BookingConfirmed, notify_sales_team)

    return App(
        payment_methods={
            name: create_payment_method(name, settings)
            for name in sorted(settings.payment_methods)
        },
        fulfilment=create_fulfilment(settings),
        bus=bus,
    )
