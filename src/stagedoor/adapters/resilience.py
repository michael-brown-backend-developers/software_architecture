"""Trying again, for code that talks to the outside world.

retry() is a decorator: it wraps a function in another function, which
calls it again if it fails for a reason that might pass, and leaves the
function itself alone.
"""

import functools
import time
from collections.abc import Callable

from stagedoor.domain.exceptions import TransientError


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
