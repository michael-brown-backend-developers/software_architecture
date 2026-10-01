from decimal import Decimal

from stagedoor.loyalty import award_points, points_for


def test_a_member_gets_a_point_for_every_whole_pound() -> None:
    assert award_points("ada@example.com", Decimal("70.99")) == 70


def test_points_add_up() -> None:
    award_points("ada@example.com", Decimal("70.00"))
    award_points("Ada@Example.com", Decimal("18.00"))

    assert points_for("ada@example.com") == 88
