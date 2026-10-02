"""Passing every command and event to whatever handles it.

A command has exactly one handler. If it fails, the sender hears about it.
An event has any number, including none; one that fails is logged, and the
others still run, because what happened has happened. Whatever events a
command's handler returns are handled straight after it.

Everything the bus handles is logged, with how long it took, in this one
place.
"""

import logging
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from stagedoor.commands import Command

logger = logging.getLogger(__name__)


class MessageBus:
    """Hands each command to its handler, and each event to its handlers."""

    def __init__(self) -> None:
        self._commands: dict[type, Callable[[Any], list[object]]] = {}
        self._events: defaultdict[type, list[Callable[[Any], None]]] = (
            defaultdict(list)
        )

    def register[C: Command](
        self, command_type: type[C], handler: Callable[[C], list[object]]
    ) -> None:
        """Make ``handler`` the one that carries out ``command_type``."""
        self._commands[command_type] = handler

    def subscribe[E](
        self, event_type: type[E], handler: Callable[[E], None]
    ) -> None:
        """Call ``handler`` with every ``event_type`` that happens."""
        self._events[event_type].append(handler)

    def handle(self, message: object) -> None:
        """Carry out a command, or pass on an event, and what follows."""
        queue = deque([message])
        while queue:
            message = queue.popleft()
            started = time.perf_counter()
            if isinstance(message, Command):
                queue.extend(self._commands[type(message)](message))
            else:
                self._publish(message)
            elapsed = time.perf_counter() - started
            logger.info("%s took %.3fs", type(message).__name__, elapsed)

    def _publish(self, event: object) -> None:
        for handler in self._events[type(event)]:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "%s failed to handle %s",
                    getattr(handler, "__qualname__", handler),
                    type(event).__name__,
                )
