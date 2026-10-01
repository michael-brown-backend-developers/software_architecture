"""The StageDoor command line.

Usage::

    stagedoor whats-on
    stagedoor book --name Ada --email ada@example.com MUC0314-ADULT:2
    stagedoor booking 3f9a1c2b7d4e
"""

import argparse
import logging
import os
import sys
from collections.abc import Mapping

from stagedoor.bookings import place_booking
from stagedoor.bootstrap import bootstrap
from stagedoor.catalogue import list_items
from stagedoor.delivery import DELIVERY_PRICING
from stagedoor.exceptions import StageDoorError
from stagedoor.models import Address, Customer
from stagedoor.payments.base import PaymentMethod
from stagedoor.settings import Settings
from stagedoor.storage import load_booking


def _parse_item(text: str) -> tuple[str, int]:
    code, _, quantity = text.partition(":")
    try:
        return code, int(quantity or "1")
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected CODE or CODE:QUANTITY, got {text!r}"
        ) from None


def _parse_address(text: str) -> Address:
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"expected 'LINE1, CITY, POSTCODE, COUNTRY', got {text!r}"
        )
    return Address(*parts)


def _build_parser(
    payment_methods: Mapping[str, PaymentMethod],
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stagedoor")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("whats-on", help="list everything we sell")

    book = commands.add_parser("book", help="make a booking")
    book.add_argument("--name", required=True)
    book.add_argument("--email", required=True)
    book.add_argument("--pay", required=True, choices=payment_methods)
    book.add_argument("--token", help="card or PayPal payment token")
    book.add_argument("--discount", metavar="CODE")
    book.add_argument(
        "--address",
        type=_parse_address,
        help="for posted tickets: 'LINE1, CITY, POSTCODE, COUNTRY'",
    )
    book.add_argument(
        "--delivery",
        default="e_ticket",
        choices=DELIVERY_PRICING,
    )
    book.add_argument(
        "items", nargs="+", type=_parse_item, metavar="CODE[:QUANTITY]"
    )

    booking = commands.add_parser("booking", help="show a booking")
    booking.add_argument("booking_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        app = bootstrap(Settings.from_env(os.environ))
        args = _build_parser(app.payment_methods).parse_args(argv)

        if args.command == "whats-on":
            for item in list_items():
                print(f"{item.code:<14} £{item.price:>6}  {item.name}")

        elif args.command == "book":
            booking = place_booking(
                Customer(
                    name=args.name, email=args.email, address=args.address
                ),
                args.items,
                payment_method=args.pay,
                payment_token=args.token,
                discount_code=args.discount,
                delivery=args.delivery,
                payment_methods=app.payment_methods,
                fulfilment=app.fulfilment,
                bus=app.bus,
            )
            print(f"Booking {booking.id} confirmed. Total: £{booking.total}")

        elif args.command == "booking":
            booking = load_booking(args.booking_id)
            customer = booking.customer
            print(
                f"Booking {booking.id} for {customer.name} <{customer.email}>"
            )
            print(f"Booked {booking.placed_at:%Y-%m-%d %H:%M} UTC")
            for line in booking.lines:
                print(f"  {line.quantity} x {line.name} = £{line.line_total}")
            print(f"Subtotal: £{booking.subtotal}")
            if booking.discount:
                print(
                    f"Discount ({booking.discount_code}): -£{booking.discount}"
                )
            print(f"Delivery ({booking.delivery}): £{booking.delivery_fee}")
            print(f"Total: £{booking.total} (includes VAT of £{booking.vat})")
            print(
                f"Payment: {booking.payment_method}, {booking.payment_status}"
                f" ({booking.payment_reference}), fee £{booking.payment_fee}"
            )
            if booking.invoice_number:
                print(f"Invoice: {booking.invoice_number}")
                print(f"Seats held: {', '.join(booking.hold_references)}")
            if booking.wallet_pass:
                print(f"Tickets: {booking.wallet_pass}")
            if booking.tracking_number:
                print(f"Posted: {booking.tracking_number}")

    except StageDoorError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
