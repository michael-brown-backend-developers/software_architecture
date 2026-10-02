"""Passing commands to their handlers, and knowing who handles each event.

A command has exactly one handler. If it fails, the sender hears about it.
Every command is logged, with how long it took, in this one place.

An event has any number of handlers, including none. The bus keeps the
list, and the worker hands each event to them, from the outbox.
"""

import logging
import time
from collections import defaultdict
from collections.abc import Callable
from functools import partial
from typing import Any

from stagedoor.application.commands import Command

logger = logging.getLogger(__name__)


class MessageBus:
    """Hands each command to its handler, and knows each event's handlers."""

    def __init__(self) -> None:
        self._commands: dict[type, Callable[[Any], None]] = {}
        self._events: defaultdict[type, list[Callable[[Any], None]]] = (
            defaultdict(list)
        )

    def register[C: Command](
        self, command_type: type[C], handler: Callable[[C], None]
    ) -> None:
        """Make ``handler`` the one that carries out ``command_type``."""
        self._commands[command_type] = handler

    def subscribe[E](
        self, event_type: type[E], handler: Callable[[E], None]
    ) -> None:
        """Make ``handler`` one of the handlers of every ``event_type``."""
        self._events[event_type].append(handler)

    def handle(self, command: Command) -> None:
        """Carry out a command."""
        started = time.perf_counter()
        self._commands[type(command)](command)
        elapsed = time.perf_counter() - started
        logger.info("%s took %.3fs", type(command).__name__, elapsed)

    def handlers_for(
        self, event: object
    ) -> list[tuple[str, Callable[[Any], None]]]:
        """Every handler subscribed to this event, with its name."""
        handlers = self._events[type(event)]
        return [(_name(handler), handler) for handler in handlers]


def _name(handler: Callable[..., object]) -> str:
    function = handler.func if isinstance(handler, partial) else handler
    return getattr(function, "__qualname__", repr(function))
