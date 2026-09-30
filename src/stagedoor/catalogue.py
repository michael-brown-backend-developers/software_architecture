"""What StageDoor sells: tickets for each performance, and a few extras.

For now the catalogue is a dictionary. It is small, it does not change while
the program is running, and nobody has asked for anything else.
"""

from decimal import Decimal

from stagedoor.exceptions import UnknownItemError
from stagedoor.models import Item, ItemKind

ITEMS: dict[str, Item] = {
    item.code: item
    for item in [
        Item(
            code="MUC0314-ADULT",
            name="Much Ado About NoneType, Sat 14 Mar 19:30 - Adult",
            price=Decimal("32.00"),
            kind=ItemKind.TICKET,
            performance="MUC0314",
        ),
        Item(
            code="MUC0314-CONC",
            name="Much Ado About NoneType, Sat 14 Mar 19:30 - Concession",
            price=Decimal("24.00"),
            kind=ItemKind.TICKET,
            performance="MUC0314",
        ),
        Item(
            code="MUC0315-ADULT",
            name="Much Ado About NoneType, Sun 15 Mar 14:30 - Adult",
            price=Decimal("28.00"),
            kind=ItemKind.TICKET,
            performance="MUC0315",
        ),
        Item(
            code="GDF0320-ADULT",
            name="The Guido Father, Fri 20 Mar 19:30 - Adult",
            price=Decimal("26.50"),
            kind=ItemKind.TICKET,
            performance="GDF0320",
        ),
        Item(
            code="PROG-MUCHADO",
            name="Much Ado About NoneType programme",
            price=Decimal("6.00"),
            kind=ItemKind.PROGRAMME,
        ),
        Item(
            code="TEE-STAGEDOOR",
            name="StageDoor T-Shirt",
            price=Decimal("18.00"),
            kind=ItemKind.MERCH,
        ),
    ]
}


def get_item(code: str) -> Item:
    """Look up an item by its code."""
    try:
        return ITEMS[code]
    except KeyError:
        raise UnknownItemError(code) from None


def list_items() -> list[Item]:
    """Every item, in code order."""
    return sorted(ITEMS.values(), key=lambda item: item.code)
