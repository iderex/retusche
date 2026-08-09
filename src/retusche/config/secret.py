# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""A credential that does not print itself.

Every leak path this project has for a credential is a place something was
formatted: a log line built from a value, an exception carrying what it refused,
a repr of an object that happens to hold one, a dump pasted into a bug report.
None of them is a mistake anybody makes on purpose, and all of them are one
f-string.

Declaring a setting as a secret is what says a value is one, and the loader
hands such a value over as a `Secret` rather than as a string. From there the
redaction travels with the value: there is no rendering to remember to redact in
and no caller that has to know what it is holding, because the only way to reach
the credential is to ask for it by name.

`reveal` is deliberately not pretty. A call site that reads it says, in the
diff, that somebody meant to take the value out, which is the line a reader
looks for. Every other way of turning this object into text produces
`REDACTED`.

What this cannot do
-------------------
It holds a `str`, and a caller that reveals one has an ordinary string with
none of this on it. That is the boundary rather than a hole: something has to
send the credential eventually, and what the type buys is that the boundary is
one named call instead of every format string in the tree.

It also says nothing about memory. The credential is a Python string, so it
lives until it is collected and may be copied by the interpreter; a process dump
or a core file holds it either way. Nothing here is a defence against reading
this process's memory, and calling this type a defence against that would be the
kind of assurance a negative disclosure gets rewritten into.
"""

from __future__ import annotations

from typing import Final, final

__all__ = ["REDACTED", "Secret"]

REDACTED: Final = "<redacted>"
"""What a secret reads as everywhere a configuration is rendered."""


@final
class Secret:
    """A string that renders as `REDACTED` however it is formatted.

    Two methods rather than three. A repr is what a dataclass, a list, a
    debugger and a bug report print, and `__format__` is what an f-string calls,
    which is the shape the leak is actually written in. There is no `__str__`
    here, and its absence was measured rather than assumed: `str` falls back to
    `__repr__` when a class defines none, so a third method would be a line the
    suite cannot show failing for the reason it names. The property that `str`
    of a secret is redacted is asserted either way, in
    `tests/test_configuration.py`, which is where it belongs.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        """The credential itself, for the one caller that has to send it."""
        return self._value

    def __repr__(self) -> str:
        return REDACTED

    def __format__(self, format_spec: str) -> str:
        """Redacted whatever the specification asked for.

        A width or an alignment is a request about the credential's shape, and
        answering it truthfully would leak the length of it. There is nothing
        here worth formatting, so the specification is dropped rather than
        applied to the word `REDACTED`.
        """
        del format_spec
        return REDACTED
