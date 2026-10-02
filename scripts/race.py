"""Two box office terminals sell The Guido Father's last two places at once.

Run it with the database up:

    poetry run python scripts/race.py

Each terminal is a thread with its own StageDoor, sharing only the
database, as two real terminals would. A bank transfer is usually quick, so
each terminal's takes half a second here, as a card payment might: that is
all the time the two need to overlap. Confirmations go to a temporary
directory, and nothing else reacts to the bookings.
"""

import os
import tempfile
import threading
import time
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from sqlalchemy import update

from stagedoor.bootstrap import bootstrap
from stagedoor.bus import EventBus
from stagedoor.db import PerformanceRow, connect, create_tables
from stagedoor.exceptions import StageDoorError
from stagedoor.models import Booking, Customer
from stagedoor.payments.base import PaymentMethod, PaymentResult
from stagedoor.settings import Settings


class SlowPayment:
    """A payment method that takes half a second to answer."""

    def __init__(self, method: PaymentMethod) -> None:
        self.method = method

    def charge(
        self, amount: Decimal, booking_id: str, token: str | None
    ) -> PaymentResult:
        time.sleep(0.5)
        return self.method.charge(amount, booking_id, token)

    def refund(self, reference: str, amount: Decimal) -> None:
        self.method.refund(reference, amount)

    def fee(self, amount: Decimal) -> Decimal:
        return self.method.fee(amount)

    def describe(self, booking: Booking) -> str:
        return self.method.describe(booking)


def terminal(name: str, settings: Settings) -> None:
    app = bootstrap(settings)
    slow = SlowPayment(app.payment_methods["bank_transfer"])
    service = replace(
        app.bookings, payment_methods={"bank_transfer": slow}, bus=EventBus()
    )
    customer = Customer(name=name, email=f"{name.lower()}@example.com")
    try:
        booking = service.place(
            customer, [("GDF0320-ADULT", 2)], "bank_transfer"
        )
        print(f"{name}: booking {booking.id} confirmed.")
    except StageDoorError as error:
        print(f"{name}: {error}")


def main() -> None:
    settings = replace(
        Settings.from_env(os.environ),
        mail_dir=Path(tempfile.mkdtemp(prefix="stagedoor-race-")),
    )
    create_tables(settings.database_url)
    with connect(settings.database_url)() as session:
        session.execute(
            update(PerformanceRow)
            .where(PerformanceRow.code == "GDF0320")
            .values(places=2)
        )
        session.commit()
    print("The Guido Father has 2 places left.")

    terminals = [
        threading.Thread(target=terminal, args=(name, settings))
        for name in ["Ada", "Grace"]
    ]
    for thread in terminals:
        thread.start()
    for thread in terminals:
        thread.join()

    with connect(settings.database_url)() as session:
        left = session.get_one(PerformanceRow, "GDF0320").places
    print(f"The Guido Father has {left} places left.")


if __name__ == "__main__":
    main()
