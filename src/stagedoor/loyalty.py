"""The loyalty scheme: a point for every whole pound a member spends.

Members are known by their email address. Points are kept in loyalty.json,
in the data directory, which comes from the STAGEDOOR_DATA_DIR environment
variable, or ./data if it is not set.
"""

import json
import os
import re
from decimal import Decimal
from pathlib import Path

# What a member's email address looks like, as far as the scheme is
# concerned.
MEMBER = re.compile(r"[a-z0-9._-]+@[a-z0-9.-]+\.[a-z]+")


def _points_file() -> Path:
    directory = Path(os.environ.get("STAGEDOOR_DATA_DIR", "data"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "loyalty.json"


def award_points(email: str, total: Decimal) -> int:
    """Give a member a point for every whole pound, and return their total."""
    member = email.lower()
    if not MEMBER.fullmatch(member):
        raise ValueError(f"{email!r} is not a member's email address")

    path = _points_file()
    points = json.loads(path.read_text()) if path.exists() else {}
    points[member] = points.get(member, 0) + int(total)
    path.write_text(json.dumps(points, indent=2))
    return int(points[member])


def points_for(email: str) -> int:
    """How many points a member has."""
    path = _points_file()
    points = json.loads(path.read_text()) if path.exists() else {}
    return int(points.get(email.lower(), 0))
