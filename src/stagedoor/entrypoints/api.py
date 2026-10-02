"""The StageDoor web API, for the support team's admin panel.

Run it with:

    poetry run fastapi dev src/stagedoor/entrypoints/api.py

Every route turns a request into a command, and hands it to the bus. What
StageDoor's errors mean in HTTP is decided once, at the bottom.
"""

import os
from decimal import Decimal
from functools import cache
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from stagedoor.application import views
from stagedoor.application.commands import (
    CancelBooking,
    CheckIn,
    MakeBooking,
    MarkPaid,
)
from stagedoor.bootstrap import App, bootstrap
from stagedoor.domain.exceptions import (
    BookingNotFoundError,
    IllegalTransitionError,
    NotEnoughPlacesError,
    PaymentFailedError,
    StageDoorError,
    TransientError,
)
from stagedoor.domain.models import Address, Booking, Customer
from stagedoor.settings import Settings

api = FastAPI(title="StageDoor")


@cache
def stagedoor() -> App:
    """StageDoor, built once, the first time a request needs it."""
    return bootstrap(Settings.from_env(os.environ))


StageDoor = Annotated[App, Depends(stagedoor)]


class AddressIn(BaseModel):
    line1: str
    city: str
    postcode: str
    country: str


class BookingRequest(BaseModel):
    name: str
    email: str
    address: AddressIn | None = None
    items: dict[str, int]
    payment_method: str
    payment_token: str | None = None
    discount_code: str | None = None
    delivery: str = "e_ticket"


class BookingOut(BaseModel):
    id: str
    name: str
    email: str
    total: Decimal
    status: str
    payment_reference: str

    @classmethod
    def of(cls, booking: Booking) -> BookingOut:
        return cls(
            id=booking.id,
            name=booking.customer.name,
            email=booking.customer.email,
            total=booking.total,
            status=booking.status,
            payment_reference=booking.payment_reference,
        )


@api.post("/bookings", status_code=201)
def make_booking(request: BookingRequest, app: StageDoor) -> BookingOut:
    address = request.address
    command = MakeBooking(
        customer=Customer(
            name=request.name,
            email=request.email,
            address=Address(**address.model_dump()) if address else None,
        ),
        items=tuple(request.items.items()),
        payment_method=request.payment_method,
        payment_token=request.payment_token,
        discount_code=request.discount_code,
        delivery=request.delivery,
    )
    app.bus.handle(command)
    return BookingOut.of(views.booking(command.booking_id, app.unit_of_work))


@api.get("/bookings/{booking_id}")
def get_booking(booking_id: str, app: StageDoor) -> BookingOut:
    return BookingOut.of(views.booking(booking_id, app.unit_of_work))


@api.post("/bookings/{booking_id}/paid")
def mark_paid(booking_id: str, app: StageDoor) -> BookingOut:
    app.bus.handle(MarkPaid(booking_id))
    return BookingOut.of(views.booking(booking_id, app.unit_of_work))


@api.post("/bookings/{booking_id}/check-in")
def check_in(booking_id: str, app: StageDoor) -> BookingOut:
    app.bus.handle(CheckIn(booking_id))
    return BookingOut.of(views.booking(booking_id, app.unit_of_work))


@api.post("/bookings/{booking_id}/cancel")
def cancel(booking_id: str, app: StageDoor) -> BookingOut:
    app.bus.handle(CancelBooking(booking_id))
    return BookingOut.of(views.booking(booking_id, app.unit_of_work))


# What each of StageDoor's errors means in HTTP. Anything else StageDoor
# refuses is a request it cannot carry out: a 422.
STATUS_CODES: dict[type[StageDoorError], int] = {
    BookingNotFoundError: 404,
    IllegalTransitionError: 409,
    NotEnoughPlacesError: 409,
    PaymentFailedError: 402,
    TransientError: 503,
}


@api.exception_handler(StageDoorError)
def refuse(request: Request, error: StageDoorError) -> JSONResponse:
    """Turn any of StageDoor's errors into an HTTP response."""
    status = next(
        (
            code
            for kind, code in STATUS_CODES.items()
            if isinstance(error, kind)
        ),
        422,
    )
    return JSONResponse({"detail": str(error)}, status_code=status)
