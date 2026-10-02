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

from stagedoor.alerts import notify_sales_team
from stagedoor.analytics import record_sale
from stagedoor.bus import MessageBus
from stagedoor.commands import CancelBooking, CheckIn, MakeBooking, MarkPaid
from stagedoor.db import SqlAlchemyUnitOfWork, connect
from stagedoor.events import BookingConfirmed
from stagedoor.fulfilment import create_fulfilment
from stagedoor.handlers import (
    cancel_booking,
    check_in,
    make_booking,
    mark_paid,
    send_confirmation,
)
from stagedoor.loyalty import award_points
from stagedoor.notifications import create_mailer
from stagedoor.payments import create_payment_method
from stagedoor.payments.base import PaymentMethod
from stagedoor.settings import Settings
from stagedoor.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class App:
    """Everything StageDoor needs to run, built and ready."""

    payment_methods: Mapping[str, PaymentMethod]
    bus: MessageBus
    unit_of_work: Callable[[], UnitOfWork]


def bootstrap(
    settings: Settings,
    sleep: Callable[[float], None] = time.sleep,
    *,
    unit_of_work: Callable[[], UnitOfWork] | None = None,
    payment_methods: Mapping[str, PaymentMethod] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> App:
    """Build StageDoor from its settings.

    ``sleep`` is how everything that retries waits between tries. A test
    can hand in its own unit of work, payment methods and clock; whatever
    it leaves out is built from the settings.
    """
    if unit_of_work is None:
        unit_of_work = partial(
            SqlAlchemyUnitOfWork, connect(settings.database_url)
        )
    if payment_methods is None:
        payment_methods = {
            name: create_payment_method(name, settings, sleep)
            for name in sorted(settings.payment_methods)
        }
    fulfilment = create_fulfilment(settings, sleep)

    bus = MessageBus()
    bus.register(
        MakeBooking,
        partial(
            make_booking,
            payment_methods=payment_methods,
            fulfilment=fulfilment,
            unit_of_work=unit_of_work,
            clock=clock or now,
        ),
    )
    bus.register(
        MarkPaid,
        partial(mark_paid, fulfilment=fulfilment, unit_of_work=unit_of_work),
    )
    bus.register(CheckIn, partial(check_in, unit_of_work=unit_of_work))
    bus.register(
        CancelBooking,
        partial(
            cancel_booking,
            payment_methods=payment_methods,
            fulfilment=fulfilment,
            unit_of_work=unit_of_work,
        ),
    )

    # Everything that happens because a booking was made.
    bus.subscribe(
        BookingConfirmed,
        partial(
            send_confirmation,
            payment_methods=payment_methods,
            unit_of_work=unit_of_work,
            mailer=create_mailer(settings),
        ),
    )
    bus.subscribe(BookingConfirmed, award_points)
    bus.subscribe(BookingConfirmed, record_sale)
    bus.subscribe(BookingConfirmed, notify_sales_team)

    return App(
        payment_methods=payment_methods, bus=bus, unit_of_work=unit_of_work
    )


def now() -> datetime:
    """The time, in UTC."""
    return datetime.now(UTC)
