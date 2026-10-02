"""How StageDoor talks to everything outside it.

Each adapter plugs into one of the application's ports, and translates
between it and one technology: PostgreSQL, a payment provider, the venue,
the email provider, a file, or memory.
"""
