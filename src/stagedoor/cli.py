"""The StageDoor command line.

Usage::

    stagedoor whats-on
    stagedoor book --name Ada --email ada@example.com MUC0314-ADULT:2
    stagedoor booking 3f9a1c2b7d4e
"""

import argparse
import sys

from stagedoor.bookings import place_booking
from stagedoor.catalogue import list_items
from stagedoor.exceptions import StageDoorError
from stagedoor.models import Customer
from stagedoor.storage import load_booking


def _parse_item(text: str) -> tuple[str, int]:
    code, _, quantity = text.partition(":")
    try:
        return code, int(quantity or "1")
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected CODE or CODE:QUANTITY, got {text!r}"
        ) from None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stagedoor")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("whats-on", help="list everything we sell")

    book = commands.add_parser("book", help="make a booking")
    book.add_argument("--name", required=True)
    book.add_argument("--email", required=True)
    book.add_argument(
        "--pay", required=True, choices=["card", "paypal", "bank_transfer"]
    )
    book.add_argument("--token", help="card or PayPal payment token")
    book.add_argument("--discount", metavar="CODE")
    book.add_argument(
        "--delivery",
        default="e_ticket",
        choices=["e_ticket", "box_office", "post"],
    )
    book.add_argument(
        "items", nargs="+", type=_parse_item, metavar="CODE[:QUANTITY]"
    )

    booking = commands.add_parser("booking", help="show a booking")
    booking.add_argument("booking_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        if args.command == "whats-on":
            for item in list_items():
                print(f"{item.code:<14} £{item.price:>6}  {item.name}")

        elif args.command == "book":
            booking = place_booking(
                Customer(name=args.name, email=args.email),
                args.items,
                payment_method=args.pay,
                payment_token=args.token,
                discount_code=args.discount,
                delivery=args.delivery,
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
                f"Paid by {booking.payment_method}"
                f" ({booking.payment_reference}), fee £{booking.payment_fee}"
            )

    except StageDoorError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
