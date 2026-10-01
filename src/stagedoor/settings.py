"""Everything StageDoor can be configured with, read once.

Settings are plain data. They are read from the environment in one place,
when StageDoor starts, and handed to whatever needs them.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from stagedoor.exceptions import SettingsError

ALL_PAYMENT_METHODS = "card,paypal,bank_transfer"


@dataclass(frozen=True)
class Settings:
    """How this copy of StageDoor is set up."""

    environment: str
    payment_methods: frozenset[str]
    stripe_api_key: str
    paypal_client_id: str
    paypal_secret: str
    venue_url: str
    venue_api_key: str
    wallet_api_key: str
    royal_mail_api_key: str
    data_dir: Path
    mail_dir: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Settings:
        """Read the settings from environment variables.

        Only production uses real keys, and every one of them must be set.
        Everywhere else uses test keys, whatever is set, so that staging can
        never charge a real card.
        """
        environment = env.get("STAGEDOOR_ENV", "development")

        def key(name: str, test_value: str) -> str:
            if environment != "production":
                return test_value
            if name not in env:
                raise SettingsError(name)
            return env[name]

        return cls(
            environment=environment,
            payment_methods=frozenset(
                env.get(
                    "STAGEDOOR_PAYMENT_METHODS", ALL_PAYMENT_METHODS
                ).split(",")
            ),
            stripe_api_key=key("STRIPE_API_KEY", "sk_test_stagedoor"),
            paypal_client_id=key("PAYPAL_CLIENT_ID", "stagedoor-sandbox"),
            paypal_secret=key("PAYPAL_SECRET", "sandbox-secret"),
            venue_url=key("VENUE_URL", "https://boxoffice.example"),
            venue_api_key=key("VENUE_API_KEY", "venue-test-key"),
            wallet_api_key=key("WALLET_API_KEY", "wallet-test-key"),
            royal_mail_api_key=key("ROYAL_MAIL_API_KEY", "rm-test-key"),
            data_dir=Path(env.get("STAGEDOOR_DATA_DIR", "data")),
            mail_dir=Path(env.get("STAGEDOOR_MAIL_DIR", "mail")),
        )
