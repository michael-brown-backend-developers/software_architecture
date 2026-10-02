"""Handling what is in the outbox, in a process of its own.

The worker takes the next message that is due, and hands its event to
every handler that has not handled it yet. If one fails, the message is
tried again later, waiting longer each time, until it has failed
MAX_ATTEMPTS times; then it is left in the outbox, for someone to look at.
"""

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta

from stagedoor.application.bus import MessageBus
from stagedoor.application.ports import UnitOfWork

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5


def handle_next(
    bus: MessageBus,
    unit_of_work: Callable[[], UnitOfWork],
    clock: Callable[[], datetime],
) -> bool:
    """Handle the next message that is due. False if none was."""
    with unit_of_work() as uow:
        message = uow.outbox.next_due(clock())
        if message is None:
            return False
        name = f"{type(message.event).__name__} {message.id}"

        for handler_name, handler in bus.handlers_for(message.event):
            if handler_name in message.handled:
                continue
            try:
                handler(message.event)
            except Exception as error:
                attempts = message.attempts + 1
                retry_at = None
                if attempts < MAX_ATTEMPTS:
                    retry_at = clock() + timedelta(seconds=2**attempts)
                uow.outbox.failed(
                    message.id, f"{handler_name}: {error}", retry_at
                )
                uow.commit()
                logger.warning(
                    "%s: %s failed, attempt %d of %d, %s: %s",
                    name,
                    handler_name,
                    attempts,
                    MAX_ATTEMPTS,
                    f"retrying at {retry_at:%H:%M:%S}"
                    if retry_at
                    else "giving up",
                    error,
                )
                return True
            uow.outbox.handled(message.id, handler_name)

        uow.outbox.done(message.id)
        uow.commit()
        logger.info("%s: handled", name)
    return True


def work(
    bus: MessageBus,
    unit_of_work: Callable[[], UnitOfWork],
    clock: Callable[[], datetime],
    *,
    once: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Handle messages as they fall due. With ``once``, stop when idle."""
    while True:
        while handle_next(bus, unit_of_work, clock):
            pass
        if once:
            return
        sleep(1)
