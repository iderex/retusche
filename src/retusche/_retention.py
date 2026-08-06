"""How long a finished job's result is kept before it is removed.

Retention is stated in one place because the operator is told one number and the
sweep that deletes has to use the same one.
"""

from __future__ import annotations

try:
    import torch
except ImportError:
    # The runtime is an optional extra, so this module works without it and
    # simply keeps results for the longer window.
    torch = None


def default_retention_seconds() -> int:
    """Shorter where the runtime is present, because a result costs disk anyway."""
    return 86_400 if torch is None else 3_600
