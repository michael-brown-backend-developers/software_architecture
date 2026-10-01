from dataclasses import dataclass

import pytest

from stagedoor.bus import EventBus


@dataclass(frozen=True)
class SomethingHappened:
    what: str


@dataclass(frozen=True)
class SomethingElseHappened:
    what: str


def test_every_handler_gets_the_event() -> None:
    bus = EventBus()
    first: list[SomethingHappened] = []
    second: list[SomethingHappened] = []
    bus.subscribe(SomethingHappened, first.append)
    bus.subscribe(SomethingHappened, second.append)

    bus.publish(SomethingHappened("a sale"))

    assert first == second == [SomethingHappened("a sale")]


def test_handlers_only_get_the_events_they_subscribed_to() -> None:
    bus = EventBus()
    heard: list[SomethingHappened] = []
    bus.subscribe(SomethingHappened, heard.append)

    bus.publish(SomethingElseHappened("a refund"))

    assert heard == []


def test_a_failing_handler_is_logged_and_the_others_still_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(event: SomethingHappened) -> None:
        raise ValueError("oops")

    bus = EventBus()
    heard: list[SomethingHappened] = []
    bus.subscribe(SomethingHappened, broken)
    bus.subscribe(SomethingHappened, heard.append)

    bus.publish(SomethingHappened("a sale"))

    assert heard == [SomethingHappened("a sale")]
    assert "broken failed to handle SomethingHappened" in caplog.text
