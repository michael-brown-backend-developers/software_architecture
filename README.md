# StageDoor

A small box office, built to be changed.

This is the companion repository for the book. Each chapter starts from a
tagged checkpoint and ends at another. To see the code exactly as a chapter
leaves it:

```bash
git checkout ch01-stagedoor-v1
```

## What it does (as of chapter 1)

- Lists what is on: tickets for each performance, and a few extras.
- Makes a booking: looks up each item, checks the performances have enough
  places, prices the booking - taking off any discount code, and working out
  the VAT included - saves it as a JSON file, and "emails" a confirmation by
  writing a text file to a mail directory.
- Shows a saved booking.

## Running it

It needs Python 3.14 or later and Poetry 2. Install it, together with the
development tools:

```bash
poetry install
```

Then:

```bash
poetry run stagedoor whats-on
poetry run stagedoor book --name Ada --email ada@example.com MUC0314-ADULT:2 PROG-MUCHADO
poetry run stagedoor booking <booking id>
```

Bookings are written to `./data/bookings/` and confirmations to `./mail/`.
Set `STAGEDOOR_DATA_DIR` and `STAGEDOOR_MAIL_DIR` to put them somewhere else.

## Checking it

```bash
poetry run pytest
poetry run mypy src tests
poetry run ruff check .
poetry run ruff format --check .
```

Lines are limited to 79 characters so that every listing fits on a printed
page.

## Layout

```
src/stagedoor/
    models.py          ItemKind, Item, Customer, BookingLine, Booking
    catalogue.py       what we sell: tickets and extras
    pricing.py         what a booking costs: discounts and VAT
    capacity.py        how many places each performance has left
    bookings.py        place_booking()
    storage.py         save and load bookings as JSON
    notifications.py   send the customer a confirmation
    exceptions.py      everything that can go wrong
    cli.py             the command line
tests/                 one test module per source module
```
