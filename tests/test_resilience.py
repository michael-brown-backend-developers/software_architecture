import pytest

from stagedoor.adapters.resilience import retry
from stagedoor.domain.exceptions import TransientError


def no_sleep(seconds: float) -> None:
    pass


def test_retry_tries_again_after_a_transient_error() -> None:
    calls = []

    @retry(attempts=3, sleep=no_sleep)
    def wobbly() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise TransientError()
        return "done"

    assert wobbly() == "done"
    assert len(calls) == 3


def test_retry_leaves_other_errors_alone() -> None:
    calls = []

    @retry(attempts=3, sleep=no_sleep)
    def broken() -> None:
        calls.append(1)
        raise ValueError("not worth trying again")

    with pytest.raises(ValueError):
        broken()
    assert len(calls) == 1


def test_a_decorated_function_keeps_its_name() -> None:
    @retry()
    def a_function_with_a_name() -> None:
        """Its docstring."""

    assert a_function_with_a_name.__name__ == "a_function_with_a_name"
    assert a_function_with_a_name.__doc__ == "Its docstring."
