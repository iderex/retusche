# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Every setting this service has, declared once.

A setting that is read where it is used becomes an environment lookup with a
default written beside it, and there is then no place an operator can look to
see what they did not set. This module is that place, and nothing outside it
declares a setting.

A declaration carries five things and each one is there because leaving it out
has a cost. The name is what an operator writes. The kind is what the value is
parsed as, so a number is refused rather than compared as text. The unit is the
half of a number that never survives being carried in somebody's head: 300 is
not a retention period until it says seconds. The summary is one sentence of
what the setting does, because a name and a type describe the field and not the
decision. The default is written as an operator would write it, or is absent,
and absent means the service refuses to start without it.

WHAT IS DECLARED HERE TODAY IS TWO SETTINGS, and that is the tree rather than
the plan. A setting belongs to the issue that builds the thing it controls: the
device is #22, the memory budget is #30, the queue depth is #34, the retention
period is #36, the log level is #64 and the library address is #56. Declaring
any of them here would answer those issues by side effect, and each of them
arrives as one row in the tuple below.

The two that are here are the two the tree can already be pointed at: the job
store, which `retusche.queue.store` opens, and the model registry, which
`retusche.models.registry` reads. Neither has a default, and that is the
argument rather than an omission: a default path writes somebody's job records
or looks for their weights wherever the process happened to be started, and
being wrong there is silent.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Final

__all__ = [
    "ENVIRONMENT_PREFIX",
    "SETTINGS",
    "Kind",
    "Setting",
    "environment_name",
]

ENVIRONMENT_PREFIX: Final = "RETUSCHE_"
"""What an environment variable for a setting is called, before the name."""


class Kind(enum.StrEnum):
    """What a value is read as, and what is refused."""

    TEXT = "text"
    """A string, kept as one."""

    SECRET = "secret"  # noqa: S105  # the name of a kind, not a credential
    """A string that never appears in a rendering of the configuration.

    Separate from `TEXT` because redaction has to be decided in the declaration
    rather than at each place a value is printed. A credential that leaks does
    so through the log line nobody thought about, and the way to prevent that is
    for the value's own declaration to carry the fact, not for every caller to
    remember it.
    """

    INTEGER = "integer"
    """A whole number. `True` is refused rather than read as one."""

    BOOLEAN = "boolean"
    """`true` or `false`, and nothing else. Not zero, not the empty string."""

    PATH = "path"
    """A filesystem path, kept as text until something opens it."""


@dataclass(frozen=True, slots=True)
class Setting:
    """One setting, complete. No field is optional except the default."""

    name: str
    """What an operator writes in the file, in lower case with underscores."""

    kind: Kind
    """What the value is parsed as."""

    unit: str
    """What the number or the string is measured or expressed in.

    Never empty. Where a kind makes the unit obvious the sentence still has to
    be written, because the reference page is read by somebody who does not have
    the type in front of them.
    """

    summary: str
    """One sentence: what this setting decides, not what type it is."""

    default: str | None = None
    """The default, written as an operator would write it, or None.

    None means there is no safe default and the service refuses to start
    without a value. A default that is only safe on the machine it was chosen
    on is the shape this is against.
    """


def environment_name(setting: Setting) -> str:
    """The environment variable this setting is read from."""
    return ENVIRONMENT_PREFIX + setting.name.upper()


SETTINGS: Final = (
    Setting(
        name="job_store_path",
        kind=Kind.PATH,
        unit="a path to a file, absolute or relative to the working directory",
        summary=(
            "Where the durable job store is kept. It is opened at startup and "
            "created if it is not there, and it is the record that survives a "
            "restart, so it belongs on storage the operator has chosen rather "
            "than wherever the process was launched from."
        ),
    ),
    Setting(
        name="model_registry_path",
        kind=Kind.PATH,
        unit="a path to a directory, absolute or relative to the working directory",
        summary=(
            "The directory of model entries, one file per model, that the "
            "registry is read from. Every model the service will offer is "
            "declared there, licence included, and a directory that is not the "
            "intended one offers a different set without saying so."
        ),
    ),
)
"""The declared surface. Nothing reads a setting that is not in here."""
