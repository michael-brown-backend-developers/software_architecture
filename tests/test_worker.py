from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import fakemailer
import pytest
from fakes import mail_about

from stagedoor.adapters.loyalty import points_for
from stagedoor.application import views
from stagedoor.application.commands import MakeBooking
from stagedoor.application.worker import handle_next, work
from stagedoor.bootstrap import App, now
from stagedoor.domain.events import BookingConfirmed
from stagedoor.domain.models import BookingStatus, Customer


def days_from_now(days: int) -> Callable[[], datetime]:
    """A clock that always says it is ``days`` from now."""
    moment = now() + timedelta(days=days)
    return lambda: moment


def book(app: App, customer: Customer) -> str:
    command = MakeBooking(
        customer=customer,
        items=(("TEE-STAGEDOOR", 1),),
        payment_method="card",
        payment_token="pm_card_visa",
    )
    app.bus.handle(command)
    return command.booking_id


def test_the_confirmation_is_sent_by_the_worker(
    app: App, ada: Customer, isolated_directories: Path
) -> None:
    mail = isolated_directories / "mail"
    booking_id = book(app, ada)
    assert mail_about(booking_id, mail) == ""

    work(app.bus, app.unit_of_work, app.clock, once=True)

    assert "Total: £18.00" in mail_about(booking_id, mail)


def test_a_booking_is_made_while_the_email_provider_is_down(
    app: App, ada: Customer
) -> None:
    fakemailer.simulate_outage = True

    booking_id = book(app, ada)

    booking = views.booking(booking_id, app.unit_of_work)
    assert booking.status == BookingStatus.PAID


def test_an_email_that_cannot_be_sent_is_tried_again_later(
    app: App, ada: Customer, isolated_directories: Path
) -> None:
    mail = isolated_directories / "mail"
    fakemailer.simulate_outage = 1
    booking_id = book(app, ada)

    work(app.bus, app.unit_of_work, app.clock, once=True)
    assert mail_about(booking_id, mail) == ""

    in_two_seconds = now() + timedelta(seconds=2)
    handle_next(app.bus, app.unit_of_work, lambda: in_two_seconds)
    assert mail_about(booking_id, mail) != ""


def test_a_retry_does_not_repeat_what_already_worked(
    app: App, ada: Customer, isolated_directories: Path
) -> None:
    failures = [RuntimeError("The sales system is down.")]

    def flaky(event: BookingConfirmed) -> None:
        if failures:
            raise failures.pop()

    app.bus.subscribe(BookingConfirmed, flaky)
    booking_id = book(app, ada)

    work(app.bus, app.unit_of_work, app.clock, once=True)
    in_two_seconds = now() + timedelta(seconds=2)
    handle_next(app.bus, app.unit_of_work, lambda: in_two_seconds)

    assert points_for("ada@example.com") == 18
    assert len(list((isolated_directories / "mail").glob("msg_*"))) == 1
    assert mail_about(booking_id, isolated_directories / "mail") != ""


def test_the_worker_gives_up_in_the_end(
    app: App, ada: Customer, caplog: pytest.LogCaptureFixture
) -> None:
    fakemailer.simulate_outage = True
    book(app, ada)

    for day in range(1, 6):
        assert handle_next(app.bus, app.unit_of_work, days_from_now(day))

    assert not handle_next(app.bus, app.unit_of_work, days_from_now(6))
    assert "attempt 5 of 5, giving up" in caplog.text
