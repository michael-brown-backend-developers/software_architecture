import importlib
import os
import subprocess
import sys
from collections.abc import Iterator

import pytest

import stagedoor.payments
from stagedoor.exceptions import UnknownPaymentMethodError
from stagedoor.payments import get_payment_method


@pytest.fixture
def reload_payments(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Payment methods are built on import, so rebuild them afterwards."""
    yield
    monkeypatch.undo()
    importlib.reload(stagedoor.payments)


def test_paypal_can_be_switched_off(
    monkeypatch: pytest.MonkeyPatch, reload_payments: None
) -> None:
    monkeypatch.setenv("STAGEDOOR_PAYMENT_METHODS", "card,bank_transfer")
    importlib.reload(stagedoor.payments)

    with pytest.raises(UnknownPaymentMethodError):
        get_payment_method("paypal")


def test_staging_never_uses_the_live_key(
    monkeypatch: pytest.MonkeyPatch, reload_payments: None
) -> None:
    monkeypatch.setenv("STAGEDOOR_ENV", "staging")
    monkeypatch.setenv("STRIPE_API_KEY", "sk_live_real_money")
    importlib.reload(stagedoor.payments)

    card = stagedoor.payments.PAYMENT_METHODS["card"]
    stripe = card.inner.inner  # type: ignore[attr-defined]
    assert stripe.api_key == "sk_test_stagedoor"


def test_production_will_not_start_without_its_keys() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "stagedoor", "whats-on"],
        env={**os.environ, "STAGEDOOR_ENV": "production"},
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "KeyError" in result.stderr
