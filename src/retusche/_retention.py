"""How long a finished job's result is kept before it is removed.

Retention is stated in one place because the operator is told one number and the
sweep that deletes has to use the same one.
"""

from __future__ import annotations


def default_retention_seconds() -> int:
    """The window the worker already uses, so the two cannot drift apart."""
    # Imported inside the function rather than at module level, so importing
    # this module costs nothing at start-up.
    from retusche_worker import DEFAULT_RETENTION_SECONDS

    return DEFAULT_RETENTION_SECONDS
