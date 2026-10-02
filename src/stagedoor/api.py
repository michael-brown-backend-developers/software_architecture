"""The StageDoor web API, for the support team's admin panel.

Run it with:

    poetry run fastapi dev src/stagedoor/api.py
"""

import os
from decimal import Decimal
from functools import cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from stagedoor.bootstrap import App, bootstrap
from stagedoor.exceptions import (
    BookingNotFoundError,
    EmptyBookingError,
    IllegalTransitionError,
    InvalidQuantityError,
    MissingAddressError,
    MissingPaymentTokenError,
    PaymentFailedError,
    UnknownDeliveryOptionError,
    UnknownDiscountCodeError,
    UnknownItemError,
    UnknownPaymentMethodError,
)
from stagedoor.models import Address, Booking, Customer
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
    customer = Customer(
        name=request.name,
        email=request.email,
        address=Address(**address.model_dump()) if address else None,
    )
    try:
        booking = app.bookings.place(
            customer,
            list(request.items.items()),
            payment_method=request.payment_method,
            payment_token=request.payment_token,
            discount_code=request.discount_code,
            delivery=request.delivery,
        )
    except PaymentFailedError as error:
        raise HTTPException(402, str(error)) from None
    except (
        EmptyBookingError,
        InvalidQuantityError,
        MissingAddressError,
        MissingPaymentTokenError,
        UnknownDeliveryOptionError,
        UnknownDiscountCodeError,
        UnknownItemError,
        UnknownPaymentMethodError,
    ) as error:
        raise HTTPException(422, str(error)) from None
    return BookingOut.of(booking)


@api.get("/bookings/{booking_id}")
def get_booking(booking_id: str, app: StageDoor) -> BookingOut:
    try:
        return BookingOut.of(app.bookings.get(booking_id))
    except BookingNotFoundError as error:
        raise HTTPException(404, str(error)) from None


@api.post("/bookings/{booking_id}/paid")
def mark_paid(booking_id: str, app: StageDoor) -> BookingOut:
    try:
        return BookingOut.of(app.bookings.mark_paid(booking_id))
    except BookingNotFoundError as error:
        raise HTTPException(404, str(error)) from None
    except IllegalTransitionError as error:
        raise HTTPException(409, str(error)) from None


@api.post("/bookings/{booking_id}/check-in")
def check_in(booking_id: str, app: StageDoor) -> BookingOut:
    try:
        return BookingOut.of(app.bookings.check_in(booking_id))
    except BookingNotFoundError as error:
        raise HTTPException(404, str(error)) from None
    except IllegalTransitionError as error:
        raise HTTPException(409, str(error)) from None


@api.post("/bookings/{booking_id}/cancel")
def cancel(booking_id: str, app: StageDoor) -> BookingOut:
    try:
        return BookingOut.of(app.bookings.cancel(booking_id))
    except BookingNotFoundError as error:
        raise HTTPException(404, str(error)) from None
    except IllegalTransitionError as error:
        raise HTTPException(409, str(error)) from None
