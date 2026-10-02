"""Trying again, and timing, for code that talks to the outside world.

Both are decorators: each one wraps a function in another function, which
does something before and after the call, and leaves the function itself
alone.
"""

import functools
import logging
import time
from collections.abc import Callable

from stagedoor.domain.exceptions import TransientError

logger = logging.getLogger(__name__)


def retry[**P, R](
    attempts: int = 3,
    base_delay: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Try again when a call raises TransientError, waiting longer each go."""

    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for attempt in range(1, attempts):
                try:
                    return function(*args, **kwargs)
                except TransientError:
                    sleep(base_delay * 2 ** (attempt - 1))
            return function(*args, **kwargs)

        return wrapper

    return decorate


def timed[**P, R](name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Log how long every call takes, whether it works or not."""

    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            started = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - started
                logger.info("%s took %.3fs", name, elapsed)

        return wrapper

    return decorate
