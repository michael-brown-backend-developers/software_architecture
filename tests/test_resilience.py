import logging

import pytest

from stagedoor.adapters.resilience import retry, timed
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


def test_timed_logs_each_call(caplog: pytest.LogCaptureFixture) -> None:
    @timed("Something slow")
    def something() -> int:
        return 42

    with caplog.at_level(logging.INFO):
        assert something() == 42

    assert caplog.messages[0].startswith("Something slow took ")


def test_decorated_functions_keep_their_names() -> None:
    @timed("Named")
    @retry()
    def a_function_with_a_name() -> None:
        """Its docstring."""

    assert a_function_with_a_name.__name__ == "a_function_with_a_name"
    assert a_function_with_a_name.__doc__ == "Its docstring."
