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

import fakemailer

from stagedoor.adapters.alerts import notify_sales_team
from stagedoor.adapters.analytics import record_sale
from stagedoor.adapters.email import ProviderMailer
from stagedoor.adapters.fulfilment import VenueFulfilment
from stagedoor.adapters.fulfilment.royal_mail import RoyalMailShipping
from stagedoor.adapters.fulfilment.venue import VenueHolds
from stagedoor.adapters.fulfilment.wallet import WalletPasses
from stagedoor.adapters.loyalty import award_points
from stagedoor.adapters.payments.bank_transfer import BankTransferPayment
from stagedoor.adapters.payments.paypal import PayPalPayment
from stagedoor.adapters.payments.stripe import StripeCardPayment
from stagedoor.adapters.payments.wrappers import RetryingPaymentMethod
from stagedoor.adapters.postgres import SqlAlchemyUnitOfWork, connect
from stagedoor.application.bus import MessageBus
from stagedoor.application.commands import (
    CancelBooking,
    CheckIn,
    MakeBooking,
    MarkPaid,
)
from stagedoor.application.handlers import (
    cancel_booking,
    check_in,
    make_booking,
    mark_paid,
    send_confirmation,
)
from stagedoor.application.ports import (
    PaymentMethod,
    UnitOfWork,
    get_payment_method,
)
from stagedoor.domain.events import BookingConfirmed
from stagedoor.settings import Settings


@dataclass(frozen=True)
class App:
    """Everything StageDoor needs to run, built and ready."""

    payment_methods: Mapping[str, PaymentMethod]
    bus: MessageBus
    unit_of_work: Callable[[], UnitOfWork]
    clock: Callable[[], datetime]


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
        every_method: dict[str, PaymentMethod] = {
            "card": RetryingPaymentMethod(
                StripeCardPayment(settings.stripe_api_key), sleep=sleep
            ),
            "paypal": PayPalPayment(
                settings.paypal_client_id, settings.paypal_secret
            ),
            "bank_transfer": BankTransferPayment(),
        }
        payment_methods = {
            name: get_payment_method(name, every_method)
            for name in sorted(settings.payment_methods)
        }
    fulfilment = VenueFulfilment(
        venue=VenueHolds(settings.venue_url, settings.venue_api_key, sleep),
        wallet=WalletPasses(settings.wallet_api_key),
        royal_mail=RoyalMailShipping(settings.royal_mail_api_key, sleep),
    )
    mailer = ProviderMailer(
        fakemailer.EmailClient(settings.mailer_api_key, settings.mail_dir)
    )
    clock = clock or now

    bus = MessageBus()
    bus.register(
        MakeBooking,
        partial(
            make_booking,
            payment_methods=payment_methods,
            fulfilment=fulfilment,
            unit_of_work=unit_of_work,
            clock=clock,
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
            mailer=mailer,
        ),
    )
    bus.subscribe(BookingConfirmed, award_points)
    bus.subscribe(BookingConfirmed, record_sale)
    bus.subscribe(BookingConfirmed, notify_sales_team)

    return App(
        payment_methods=payment_methods,
        bus=bus,
        unit_of_work=unit_of_work,
        clock=clock,
    )


def now() -> datetime:
    """The time, in UTC."""
    return datetime.now(UTC)
