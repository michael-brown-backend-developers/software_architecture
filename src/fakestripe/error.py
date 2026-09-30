"""The errors fakestripe raises, named after Stripe's own."""


class StripeError(Exception):
    """Base class for every error fakestripe raises."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.user_message = message
        self.code = code


class CardError(StripeError):
    """The card was declined."""


class AuthenticationError(StripeError):
    """No API key, or the wrong one."""


class APIConnectionError(StripeError):
    """fakestripe could not be reached."""
