"""Taking payment for bookings.

Every way of paying is a PaymentMethod (see application/ports.py), so the
rest of StageDoor can take a payment, work out its fee, and describe it to
the customer, without knowing which way the customer chose to pay - or
which company takes the money. Each company's library is used in exactly
one module: the adapter that translates it.
"""
