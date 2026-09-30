"""What getting a booking to the customer costs.

Delivery prices include VAT, like everything else we sell.
"""

from decimal import Decimal

from stagedoor.exceptions import UnknownDeliveryOptionError

FREE_POST_FROM = Decimal("100.00")


def delivery_cost(delivery: str, goods_total: Decimal) -> Decimal:
    """The price of a delivery option, for goods costing ``goods_total``."""
    if delivery == "e_ticket":
        return Decimal("0.00")
    elif delivery == "box_office":
        return Decimal("0.00")
    elif delivery == "post":
        if goods_total >= FREE_POST_FROM:
            return Decimal("0.00")
        return Decimal("2.50")
    raise UnknownDeliveryOptionError(delivery)
