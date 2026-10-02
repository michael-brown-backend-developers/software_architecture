from dataclasses import dataclass
from functools import partial

import pytest

from stagedoor.application.bus import MessageBus
from stagedoor.application.commands import Command


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
    bus.register(DoSomething, done.append)

    bus.handle(DoSomething("a sale"))

    assert done == [DoSomething("a sale")]


def test_a_failing_command_fails_for_its_sender() -> None:
    def refuse(command: DoSomething) -> None:
        raise ValueError("no")

    bus = MessageBus()
    bus.register(DoSomething, refuse)

    with pytest.raises(ValueError):
        bus.handle(DoSomething("a sale"))


def test_every_command_is_logged_with_its_time(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO")
    bus = MessageBus()
    bus.register(DoSomething, lambda command: None)

    bus.handle(DoSomething("a sale"))

    assert "DoSomething took" in caplog.text


def tell_the_box_office(event: SomethingHappened) -> None: ...


def tell_the_sales_team(event: SomethingHappened) -> None: ...


def test_an_event_has_every_handler_subscribed_to_it() -> None:
    bus = MessageBus()
    bus.subscribe(SomethingHappened, tell_the_box_office)
    bus.subscribe(SomethingHappened, tell_the_sales_team)

    assert bus.handlers_for(SomethingHappened("a sale")) == [
        ("tell_the_box_office", tell_the_box_office),
        ("tell_the_sales_team", tell_the_sales_team),
    ]


def test_an_event_has_only_the_handlers_subscribed_to_it() -> None:
    bus = MessageBus()
    bus.subscribe(SomethingHappened, tell_the_box_office)

    assert bus.handlers_for(SomethingElseHappened("a refund")) == []


def test_a_handler_with_arguments_filled_in_keeps_its_name() -> None:
    bus = MessageBus()
    bus.subscribe(SomethingHappened, partial(tell_the_box_office))

    [(name, _)] = bus.handlers_for(SomethingHappened("a sale"))

    assert name == "tell_the_box_office"
