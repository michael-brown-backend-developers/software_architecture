"""Passing events to whatever is interested in them.

Handlers subscribe to a type of event. Publishing an event calls each of
its handlers in turn. A handler that fails is logged, and the others still
run: whatever went wrong is not the publisher's problem.
"""

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class EventBus:
    """Calls every handler subscribed to an event when it is published."""

    def __init__(self) -> None:
        self._handlers: defaultdict[type, list[Callable[[Any], None]]] = (
            defaultdict(list)
        )

    def subscribe[E](
        self, event_type: type[E], handler: Callable[[E], None]
    ) -> None:
        """Call ``handler`` with every ``event_type`` that is published."""
        self._handlers[event_type].append(handler)

    def publish(self, event: object) -> None:
        """Hand ``event`` to every handler subscribed to its type."""
        for handler in self._handlers[type(event)]:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "%s failed to handle %s",
                    getattr(handler, "__qualname__", handler),
                    type(event).__name__,
                )
