import pytest

from stagedoor.bootstrap import bootstrap
from stagedoor.exceptions import SettingsError, UnknownPaymentMethodError
from stagedoor.payments import get_payment_method
from stagedoor.settings import Settings

PRODUCTION = {
    "STAGEDOOR_ENV": "production",
    "STRIPE_API_KEY": "sk_live_real_money",
    "PAYPAL_CLIENT_ID": "live-id",
    "PAYPAL_SECRET": "live-secret",
    "VENUE_URL": "https://boxoffice.lantern.example",
    "VENUE_API_KEY": "live-venue-key",
    "WALLET_API_KEY": "live-wallet-key",
    "ROYAL_MAIL_API_KEY": "live-rm-key",
}


def test_development_needs_no_settings_at_all() -> None:
    settings = Settings.from_env({})

    assert settings.environment == "development"
    assert settings.stripe_api_key == "sk_test_stagedoor"
    assert settings.payment_methods == {"card", "paypal", "bank_transfer"}


def test_staging_never_uses_the_live_key() -> None:
    settings = Settings.from_env(
        {"STAGEDOOR_ENV": "staging", "STRIPE_API_KEY": "sk_live_real_money"}
    )

    assert settings.stripe_api_key == "sk_test_stagedoor"


def test_production_uses_the_keys_it_is_given() -> None:
    settings = Settings.from_env(PRODUCTION)

    assert settings.stripe_api_key == "sk_live_real_money"


def test_production_says_which_key_is_missing() -> None:
    without_wallet = {
        name: value
        for name, value in PRODUCTION.items()
        if name != "WALLET_API_KEY"
    }

    with pytest.raises(SettingsError, match="WALLET_API_KEY"):
        Settings.from_env(without_wallet)


def test_paypal_can_be_switched_off() -> None:
    app = bootstrap(
        Settings.from_env({"STAGEDOOR_PAYMENT_METHODS": "card,bank_transfer"})
    )

    assert set(app.payment_methods) == {"bank_transfer", "card"}
    with pytest.raises(UnknownPaymentMethodError):
        get_payment_method("paypal", app.payment_methods)
