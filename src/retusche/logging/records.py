# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Building a log line, and refusing the ones that would carry content.

A line is a name and a set of declared fields. It is never a sentence with
values pushed into it, and that is the whole of the design: a format string is
the route by which a filename, a prompt or a stranger's bytes arrive in a log,
because a format string accepts anything and says so nowhere.

So there is no message. `record` takes an event name whose shape is refused
unless it is a dotted lower-case token, and keyword fields that are refused
unless `retusche.logging.fields` declares them. What comes back renders as one
JSON object with sorted keys, and the only way to add something to it is to add
a field to the declaration.

Everything at once
------------------
A refusal names every problem it found rather than the first, which is the
shape `retusche.config.loading` already uses and for the same reason: somebody
correcting four things wants to correct them once. Here it matters in a second
way. A caller who has written three fields the declaration does not have is
usually holding a mental model of what may be logged, and being shown one
rejection at a time teaches them the wrong lesson three times.

The level does not widen anything
---------------------------------
A `Record` is built before any level is considered, and `Log` compares levels
and writes or does not. There is no route on which a more verbose level admits
a field a quieter one refuses, because the check is not on that route at all.
That is what makes the operator-facing claim, that no level adds picture
content, a property of the arrangement rather than a promise about the call
sites.

What this module does not do
----------------------------
It does not open a file, take a handler, read the environment or decide where a
line goes. `Log` is handed a sink, in the same way `retusche.config.loading` is
handed the text and the mapping, because the entry point that would own a
destination is not in this tree and a module reaching for one is a module the
suite cannot exercise without arranging the host. Whoever builds that entry
point supplies the sink, and #65 is where a second consumer of these records
would be argued.
"""

from __future__ import annotations

import enum
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from retusche.logging.fields import FIELD_BY_NAME, Field

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = [
    "EVENT_SHAPE",
    "Level",
    "Log",
    "LogLineError",
    "Record",
    "level_from_name",
    "record",
    "render",
]

EVENT_SHAPE: Final = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)+$")
"""What an event name has to look like.

At least two dot-separated segments, lower case, digits and inner hyphens
allowed, nothing else. The shape is the point rather than a style: a name that
cannot hold a space, a slash, a quote or a capital letter cannot hold a path, a
prompt or a filename, so the one part of a line that is not a declared field
still cannot become one.

Two segments rather than one because a single word is what somebody writes when
they are describing the moment rather than naming the event, and the first
`job.` or `model.` forces the question of what the line is about.
"""


class Level(enum.StrEnum):
    """How much attention a line is asking for."""

    DEBUG = "debug"
    """Detail an operator turns on while working out what happened."""

    INFO = "info"
    """The service doing what it is for."""

    WARNING = "warning"
    """Something an operator should look at before it becomes a failure."""

    ERROR = "error"
    """Work that did not happen, or a component that has stopped working."""


_SEVERITY: Final[Mapping[Level, int]] = {
    Level.DEBUG: 10,
    Level.INFO: 20,
    Level.WARNING: 30,
    Level.ERROR: 40,
}
"""How the levels compare. A table rather than the declaration order, so that
reordering the enumeration for readability cannot silently change what a
threshold admits."""


class LogLineError(Exception):
    """A line this module will not build, with every problem in the message."""


@dataclass(frozen=True, slots=True)
class Record:
    """One log line, already checked.

    Holding a checked record rather than a checkable one is what lets `Log` be
    a comparison and a write. There is no way to reach this type except through
    `record`, so a value of it is evidence that the declaration was consulted.
    """

    event: str
    level: Level
    fields: Mapping[str, str | int]


def level_from_name(name: str) -> Level:
    """The level an operator wrote, or a refusal naming what is accepted.

    `retusche.config` checks that a setting's value is text and does not know
    that this one is drawn from a set. That check belongs where the set is,
    which is here, and the refusal quotes the accepted values because a
    configuration error that does not is one the operator answers by guessing.
    """
    try:
        return Level(name)
    except ValueError:
        accepted = ", ".join(level.value for level in Level)
        message = f"log level {name!r} is not one of: {accepted}"
        raise LogLineError(message) from None


def record(event: str, level: Level, **fields: str | int) -> Record:
    """One line, or a refusal naming everything wrong with it."""
    problems = [*_event_problems(event)]
    for name in sorted(fields):
        problems.extend(_field_problems(name, fields[name]))
    if problems:
        raise LogLineError("; ".join(problems))
    return Record(event=event, level=level, fields=dict(fields))


def render(entry: Record) -> str:
    """The line as it is written: one JSON object, keys sorted, no newline.

    JSON because a consumer has to be able to read a value back out without
    guessing where it started, and this project will be read by whatever the
    operator already runs rather than by a reader of its own. Sorted keys
    because two lines describing the same thing should differ only where the
    thing differed.
    """
    payload: dict[str, str | int] = {
        "event": entry.event,
        "level": entry.level.value,
        **{name: entry.fields[name] for name in sorted(entry.fields)},
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class Log:
    """A level and somewhere to write, and nothing else.

    Not a singleton and not configured at import. A module-level logger is the
    thing that gets configured differently depending on which import ran first,
    and it is why a suite ends up asserting against whatever the last test set
    up.
    """

    def __init__(self, level: Level, sink: Callable[[str], None]) -> None:
        self._level = level
        self._sink = sink

    @property
    def level(self) -> Level:
        """The threshold in force. A line below it is not written."""
        return self._level

    def emit(self, entry: Record) -> bool:
        """Write the line if its level reaches the threshold. Says which it did.

        The answer is returned rather than swallowed so a test can tell a line
        that was filtered from a line that was never built, which are the two
        outcomes a silent log leaves indistinguishable.
        """
        if _SEVERITY[entry.level] < _SEVERITY[self._level]:
            return False
        self._sink(render(entry))
        return True


def _event_problems(event: str) -> list[str]:
    """What is wrong with the event name, if anything."""
    if EVENT_SHAPE.fullmatch(event):
        return []
    return [
        f"event name {event!r} is not a dotted lower-case token such as "
        f"'job.state-changed'"
    ]


def _field_problems(name: str, value: str | int) -> list[str]:
    """What is wrong with one field, if anything."""
    field = FIELD_BY_NAME.get(name)
    if field is None:
        return [f"{name!r} is not a declared log field"]
    if field.takes_text:
        return _text_problems(field, value)
    return _number_problems(field, value)


def _text_problems(field: Field, value: str | int) -> list[str]:
    """A text field's value: a non-empty string with nothing unprintable in it."""
    if not isinstance(value, str):
        return [f"{field.name!r} is {field.category.value} and takes text"]
    if not value:
        return [f"{field.name!r} is empty, which says less than omitting it"]
    if any(character.isspace() or not character.isprintable() for character in value):
        return [
            f"{field.name!r} holds whitespace or an unprintable character, "
            f"which is prose rather than a value from {field.unit}"
        ]
    return []


def _number_problems(field: Field, value: str | int) -> list[str]:
    """A number field's value: a whole number, never negative, never a boolean.

    `True` is refused rather than written as 1. Python treats a boolean as an
    integer, so a caller passing a flag where a count was meant produces a line
    that reads as a measurement of one.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return [f"{field.name!r} is a {field.category.value} and takes a whole number"]
    if value < 0:
        return [f"{field.name!r} is negative, and {field.unit} does not go below zero"]
    return []
