import pytest

from stagedoor.entrypoints.cli import main


@pytest.fixture(autouse=True)
def database_for_the_command_line(
    database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STAGEDOOR_DATABASE_URL", database)


def test_whats_on_lists_the_catalogue(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["whats-on"]) == 0

    assert "MUC0314-ADULT" in capsys.readouterr().out


def test_a_booking_can_be_made_and_shown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(
        "book --name Ada --email ada@example.com --pay card"
        " --token pm_card_visa MUC0314-ADULT:2 PROG-MUCHADO".split()
    )
    made = capsys.readouterr().out
    booking_id = made.split()[1]

    assert main(["booking", booking_id]) == 0

    shown = capsys.readouterr().out
    assert "2 x Much Ado About NoneType, Sat 14 Mar 19:30 - Adult" in shown
    assert "Total: £70.00" in shown


def test_an_error_is_reported_without_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["booking", "does-not-exist"]) == 1

    assert (
        "Error: No booking with ID 'does-not-exist'" in capsys.readouterr().err
    )


def test_a_declined_card_is_explained_to_the_customer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = main(
        "book --name Ada --email ada@example.com --pay card"
        " --token pm_card_declined TEE-STAGEDOOR".split()
    )

    assert status == 1
    assert "Error: Your card was declined." in capsys.readouterr().err


def test_a_booking_can_be_cancelled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(
        "book --name Ada --email ada@example.com --pay bank_transfer"
        " MUC0314-ADULT:2".split()
    )
    booking_id = capsys.readouterr().out.split()[1]

    assert main(["cancel", booking_id]) == 0

    assert f"Booking {booking_id} is cancelled." in capsys.readouterr().out
