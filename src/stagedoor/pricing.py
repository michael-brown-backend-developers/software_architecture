"""What a booking costs.

Finance own everything in here: the discount codes, the VAT rates, and how
the two combine. Nothing in this module reads or writes anything. Give it the
same lines and it will always give you the same answer.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from stagedoor.delivery import delivery_cost
from stagedoor.exceptions import UnknownDiscountCodeError
from stagedoor.models import BookingLine, ItemKind

PENNY = Decimal("0.01")

# Percentage off the whole booking.
DISCOUNT_CODES: dict[str, Decimal] = {
    "FIRSTNIGHT10": Decimal("10"),
    "STAFF25": Decimal("25"),
}

# Our prices include VAT. Programmes are printed matter, so zero-rated.
VAT_RATES: dict[ItemKind, Decimal] = {
    ItemKind.TICKET: Decimal("0.20"),
    ItemKind.PROGRAMME: Decimal("0.00"),
    ItemKind.MERCH: Decimal("0.20"),
}

# Strictly, the VAT on postage follows whatever is being posted. We keep
# things simple and charge it at the standard rate.
DELIVERY_VAT_RATE = Decimal("0.20")


@dataclass(frozen=True)
class Totals:
    """What a booking costs.

    ``total`` is ``subtotal`` minus ``discount``, plus ``delivery_fee``.
    ``vat`` is the VAT included in ``total``, not added to it.
    """

    subtotal: Decimal
    discount: Decimal
    delivery_fee: Decimal
    total: Decimal
    vat: Decimal


def discount_percentage(code: str | None) -> Decimal:
    """The percentage a discount code takes off, or nothing for no code."""
    if code is None:
        return Decimal("0")
    try:
        return DISCOUNT_CODES[code]
    except KeyError:
        raise UnknownDiscountCodeError(code) from None


def vat_included(gross: Decimal, rate: Decimal) -> Decimal:
    """The VAT inside a VAT-inclusive amount, to the nearest penny."""
    return (gross * rate / (1 + rate)).quantize(PENNY, ROUND_HALF_UP)


def price_booking(
    lines: Sequence[BookingLine], discount_code: str | None, delivery: str
) -> Totals:
    """Work out what a booking costs, including delivery.

    The discount comes off every line equally, so each line's VAT is worked
    out on its discounted amount. Delivery is priced on the goods after the
    discount, and the discount never comes off delivery.
    """
    percent_off = discount_percentage(discount_code)

    subtotal = sum((line.line_total for line in lines), Decimal("0.00"))
    discount = (subtotal * percent_off / 100).quantize(PENNY, ROUND_HALF_UP)
    delivery_fee = delivery_cost(delivery, subtotal - discount)

    vat = sum(
        (
            vat_included(
                line.line_total * (100 - percent_off) / 100,
                VAT_RATES[line.kind],
            )
            for line in lines
        ),
        Decimal("0.00"),
    )
    vat += vat_included(delivery_fee, DELIVERY_VAT_RATE)

    return Totals(
        subtotal=subtotal,
        discount=discount,
        delivery_fee=delivery_fee,
        total=subtotal - discount + delivery_fee,
        vat=vat,
    )
