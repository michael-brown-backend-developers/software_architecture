"""Two box office terminals sell The Guido Father's last two places at once.

Run it with the database up:

    poetry run python scripts/race.py

Each terminal is a thread with its own StageDoor, sharing only the
database, as two real terminals would, and everything else they write
goes to temporary directories. A
bank transfer is usually quick, so each terminal's takes half a second
here, as a card payment might: that is all the time the two need to
overlap.
"""

import os
import tempfile
import threading
import time
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from sqlalchemy import update

from stagedoor.adapters.payments.bank_transfer import BankTransferPayment
from stagedoor.adapters.postgres import PerformanceRow, connect, create_tables
from stagedoor.application.commands import MakeBooking
from stagedoor.application.ports import PaymentMethod, PaymentResult
from stagedoor.bootstrap import bootstrap
from stagedoor.domain.exceptions import StageDoorError
from stagedoor.domain.models import Booking, Customer
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
    mail = Path(tempfile.mkdtemp(prefix=f"stagedoor-{name.lower()}-"))
    settings = replace(settings, mail_dir=mail)
    slow = SlowPayment(BankTransferPayment())
    app = bootstrap(settings, payment_methods={"bank_transfer": slow})
    command = MakeBooking(
        customer=Customer(name=name, email=f"{name.lower()}@example.com"),
        items=(("GDF0320-ADULT", 2),),
        payment_method="bank_transfer",
    )
    try:
        app.bus.handle(command)
        print(f"{name}: booking {command.booking_id} confirmed.")
    except StageDoorError as error:
        print(f"{name}: {error}")


def main() -> None:
    os.environ["STAGEDOOR_DATA_DIR"] = tempfile.mkdtemp(prefix="stagedoor-")
    settings = Settings.from_env(os.environ)
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
