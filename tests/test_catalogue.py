from decimal import Decimal

import pytest

from stagedoor.catalogue import get_item, list_items
from stagedoor.exceptions import UnknownItemError


def test_get_item_returns_the_item() -> None:
    item = get_item("TEE-STAGEDOOR")

    assert item.price == Decimal("18.00")


def test_get_item_raises_for_an_unknown_code() -> None:
    with pytest.raises(UnknownItemError):
        get_item("NOPE-999")


def test_a_ticket_knows_its_performance() -> None:
    assert get_item("MUC0314-CONC").performance == "MUC0314"


def test_list_items_is_in_code_order() -> None:
    codes = [item.code for item in list_items()]

    assert codes == sorted(codes)
