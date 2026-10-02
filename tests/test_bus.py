from dataclasses import dataclass

import pytest

from stagedoor.bus import MessageBus
from stagedoor.commands import Command


@dataclass(frozen=True)
class SomethingHappened:
    what: str


@dataclass(frozen=True)
class SomethingElseHappened:
    what: str


@dataclass(frozen=True)
class DoSomething(Command):
    what: str


def test_a_command_goes_to_its_handler() -> None:
    bus = MessageBus()
    done: list[DoSomething] = []

    def do_it(command: DoSomething) -> list[object]:
        done.append(command)
        return []

    bus.register(DoSomething, do_it)

    bus.handle(DoSomething("a sale"))

    assert done == [DoSomething("a sale")]


def test_a_failing_command_fails_for_its_sender() -> None:
    def refuse(command: DoSomething) -> list[object]:
        raise ValueError("no")

    bus = MessageBus()
    bus.register(DoSomething, refuse)

    with pytest.raises(ValueError):
        bus.handle(DoSomething("a sale"))


def test_the_events_a_command_returns_are_handled_after_it() -> None:
    bus = MessageBus()
    heard: list[SomethingHappened] = []
    bus.register(
        DoSomething, lambda command: [SomethingHappened(command.what)]
    )
    bus.subscribe(SomethingHappened, heard.append)

    bus.handle(DoSomething("a sale"))

    assert heard == [SomethingHappened("a sale")]


def test_every_handler_gets_the_event() -> None:
    bus = MessageBus()
    first: list[SomethingHappened] = []
    second: list[SomethingHappened] = []
    bus.subscribe(SomethingHappened, first.append)
    bus.subscribe(SomethingHappened, second.append)

    bus.handle(SomethingHappened("a sale"))

    assert first == second == [SomethingHappened("a sale")]


def test_handlers_only_get_the_events_they_subscribed_to() -> None:
    bus = MessageBus()
    heard: list[SomethingHappened] = []
    bus.subscribe(SomethingHappened, heard.append)

    bus.handle(SomethingElseHappened("a refund"))

    assert heard == []


def test_a_failing_handler_is_logged_and_the_others_still_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(event: SomethingHappened) -> None:
        raise ValueError("oops")

    bus = MessageBus()
    heard: list[SomethingHappened] = []
    bus.subscribe(SomethingHappened, broken)
    bus.subscribe(SomethingHappened, heard.append)

    bus.handle(SomethingHappened("a sale"))

    assert heard == [SomethingHappened("a sale")]
    assert "broken failed to handle SomethingHappened" in caplog.text


def test_everything_handled_is_logged_with_its_time(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO")
    bus = MessageBus()

    bus.handle(SomethingHappened("a sale"))

    assert "SomethingHappened took" in caplog.text
