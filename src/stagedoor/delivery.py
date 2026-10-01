"""What getting a booking to the customer costs.

Each delivery option is priced by a function that takes the value of the
goods and returns the cost of delivering them. Delivery prices include
VAT, like everything else we sell.
"""

from collections.abc import Callable
from decimal import Decimal

from stagedoor.exceptions import UnknownDeliveryOptionError

FREE_POST_FROM = Decimal("100.00")


def e_ticket_delivery(goods_total: Decimal) -> Decimal:
    return Decimal("0.00")


def box_office_delivery(goods_total: Decimal) -> Decimal:
    return Decimal("0.00")


def post_delivery(goods_total: Decimal) -> Decimal:
    if goods_total >= FREE_POST_FROM:
        return Decimal("0.00")
    return Decimal("2.50")


DELIVERY_PRICING: dict[str, Callable[[Decimal], Decimal]] = {
    "e_ticket": e_ticket_delivery,
    "box_office": box_office_delivery,
    "post": post_delivery,
}


def delivery_cost(delivery: str, goods_total: Decimal) -> Decimal:
    """The price of a delivery option, for goods costing ``goods_total``."""
    try:
        price = DELIVERY_PRICING[delivery]
    except KeyError:
        raise UnknownDeliveryOptionError(delivery) from None
    return price(goods_total)


EU_COUNTRIES = set(
    "AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO"
    " SE SI SK".split()
)


def shipping_region(country: str) -> str:
    """Where Royal Mail is posting to: the UK, the EU, or anywhere else."""
    if country == "GB":
        return "UK"
    if country in EU_COUNTRIES:
        return "EU"
    return "WORLD"
