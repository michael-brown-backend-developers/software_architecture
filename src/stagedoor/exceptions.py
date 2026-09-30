"""Everything that can go wrong, in StageDoor's own words."""


class StageDoorError(Exception):
    """Base class for every error StageDoor raises on purpose."""


class UnknownItemError(StageDoorError):
    """The code is not in the catalogue."""

    def __init__(self, code: str) -> None:
        super().__init__(f"No item with code {code!r}")
        self.code = code


class EmptyBookingError(StageDoorError):
    """A booking was made with nothing on it."""

    def __init__(self) -> None:
        super().__init__("A booking needs at least one item")


class InvalidQuantityError(StageDoorError):
    """A quantity was zero or negative."""

    def __init__(self, code: str, quantity: int) -> None:
        super().__init__(
            f"Quantity for {code!r} must be at least 1, got {quantity}"
        )
        self.code = code
        self.quantity = quantity


class UnknownDiscountCodeError(StageDoorError):
    """The discount code does not exist."""

    def __init__(self, code: str) -> None:
        super().__init__(f"No discount code {code!r}")
        self.code = code


class NotEnoughPlacesError(StageDoorError):
    """A performance does not have enough places left for the booking."""

    def __init__(
        self, performance: str, requested: int, available: int
    ) -> None:
        super().__init__(
            f"Only {available} places left for {performance!r},"
            f" {requested} requested"
        )
        self.performance = performance
        self.requested = requested
        self.available = available


class BookingNotFoundError(StageDoorError):
    """No booking has been saved with this ID."""

    def __init__(self, booking_id: str) -> None:
        super().__init__(f"No booking with ID {booking_id!r}")
        self.booking_id = booking_id
