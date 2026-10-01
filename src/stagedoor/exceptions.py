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


class UnknownPaymentMethodError(StageDoorError):
    """We do not take payment this way."""

    def __init__(self, method: str) -> None:
        super().__init__(f"No payment method {method!r}")
        self.method = method


class MissingPaymentTokenError(StageDoorError):
    """This payment method needs a token, and none was given."""

    def __init__(self, method: str) -> None:
        super().__init__(f"Paying by {method} needs a payment token")
        self.method = method


class UnknownDeliveryOptionError(StageDoorError):
    """We do not deliver this way."""

    def __init__(self, delivery: str) -> None:
        super().__init__(f"No delivery option {delivery!r}")
        self.delivery = delivery


class PaymentFailedError(StageDoorError):
    """The customer could not be charged. ``reason`` says why, for them."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class MissingAddressError(StageDoorError):
    """Posting tickets needs an address, and none was given."""

    def __init__(self) -> None:
        super().__init__("Posted tickets need an address")


class TransientError(StageDoorError):
    """Something failed, but trying again later might work."""


class PaymentUnavailableError(TransientError):
    """The payment provider could not be reached. Later may work."""

    def __init__(self, provider: str) -> None:
        super().__init__(f"Could not reach {provider}. Please try again soon.")
        self.provider = provider


class FulfilmentError(StageDoorError):
    """The tickets could not be issued. ``reason`` says why."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Could not issue the tickets: {reason}")
        self.reason = reason


class FulfilmentUnavailableError(FulfilmentError, TransientError):
    """Part of issuing the tickets is not answering. Later might work."""
