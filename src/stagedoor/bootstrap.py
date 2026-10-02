"""Building StageDoor.

This is the one place that knows which concrete classes StageDoor runs
with, and how they fit together. Everything is built here, once, from the
settings, and handed to the code that needs it.
"""

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from uuid import uuid4

from stagedoor.alerts import notify_sales_team
from stagedoor.analytics import record_sale
from stagedoor.bookings import BookingService
from stagedoor.bus import EventBus
from stagedoor.db import SqlAlchemyUnitOfWork, connect
from stagedoor.events import BookingConfirmed
from stagedoor.fulfilment import create_fulfilment
from stagedoor.loyalty import award_points
from stagedoor.notifications import Mailer
from stagedoor.payments import create_payment_method
from stagedoor.payments.base import PaymentMethod
from stagedoor.settings import Settings


@dataclass(frozen=True)
class App:
    """Everything StageDoor needs to run, built and ready."""

    payment_methods: Mapping[str, PaymentMethod]
    bookings: BookingService


def bootstrap(
    settings: Settings, sleep: Callable[[float], None] = time.sleep
) -> App:
    """Build StageDoor from its settings.

    ``sleep`` is how everything that retries waits between tries.
    """
    # Everything that happens because a booking was made.
    bus = EventBus()
    bus.subscribe(BookingConfirmed, award_points)
    bus.subscribe(BookingConfirmed, record_sale)
    bus.subscribe(BookingConfirmed, notify_sales_team)

    sessions = connect(settings.database_url)
    payment_methods = {
        name: create_payment_method(name, settings, sleep)
        for name in sorted(settings.payment_methods)
    }
    return App(
        payment_methods=payment_methods,
        bookings=BookingService(
            payment_methods=payment_methods,
            fulfilment=create_fulfilment(settings, sleep),
            unit_of_work=partial(SqlAlchemyUnitOfWork, sessions),
            mailer=Mailer(settings.mail_dir),
            bus=bus,
            clock=now,
            new_id=new_booking_id,
        ),
    )


def now() -> datetime:
    """The time, in UTC."""
    return datetime.now(UTC)


def new_booking_id() -> str:
    """A new, random booking ID: twelve hexadecimal digits."""
    return uuid4().hex[:12]
