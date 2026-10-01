from decimal import Decimal

import pytest

from stagedoor.delivery import delivery_cost, shipping_region
from stagedoor.exceptions import UnknownDeliveryOptionError


@pytest.mark.parametrize(
    ("delivery", "goods_total", "cost"),
    [
        ("e_ticket", Decimal("20.00"), Decimal("0.00")),
        ("box_office", Decimal("20.00"), Decimal("0.00")),
        ("post", Decimal("99.99"), Decimal("2.50")),
        ("post", Decimal("100.00"), Decimal("0.00")),
    ],
)
def test_delivery_cost(
    delivery: str, goods_total: Decimal, cost: Decimal
) -> None:
    assert delivery_cost(delivery, goods_total) == cost


def test_an_unknown_delivery_option_is_rejected() -> None:
    with pytest.raises(UnknownDeliveryOptionError):
        delivery_cost("carrier_pigeon", Decimal("10.00"))


@pytest.mark.parametrize(
    ("country", "region"),
    [("GB", "UK"), ("FR", "EU"), ("IE", "EU"), ("US", "WORLD")],
)
def test_shipping_region(country: str, region: str) -> None:
    assert shipping_region(country) == region
