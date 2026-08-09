# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What a log line may carry, declared once.

A log line describes the work. It does not describe the picture. The pictures
this service handles are somebody's family, and a log that carries the prompt,
the file name inside the library, the coordinates the camera recorded or a
thumbnail has turned an operational record into a second copy of the sensitive
thing, kept for a different length of time, read by different people, and
usually shipped somewhere else.

So the surface is a declaration rather than a habit. `Category` is the closed
set of kinds of thing a line may carry, `FIELDS` is the fields that exist
today, and `retusche.logging.records` refuses a field that is not in it. There
is no state in which a caller adds a field by writing one.

Categories and fields are two different lists on purpose
--------------------------------------------------------
The categories are the rule and they are complete: identifiers, states,
durations, sizes, model names and error reasons, and nothing else may be
declared. The fields are what the tree can be pointed at today, and that list
grows as the service does.

`Category.DURATION` therefore has no field under it. Nothing in this tree
measures one: `retusche.queue.ordering` orders by an arrival ordinal rather
than a clock reading, and no work has been run to be timed. A field declared
now would be a name for a number nothing produces, which is the shape
`retusche.config.settings` refuses for settings and refuses here for the same
reason. The category stays because it is part of the rule, and the empty row it
produces in the reference page is the disclosure rather than an oversight.

What is not here is also declared
---------------------------------
`WITHHELD` names the things that are kept out and says why for each. A list of
what may be logged answers "is this field allowed" and answers nothing at all
to somebody asking "does this service log my prompts", which is the question an
operator is actually asked. The two lists are read by the same reference page
and by the same suite, so the answer to the second question cannot drift away
from the mechanism that enforces the first.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "FIELDS",
    "FIELD_BY_NAME",
    "WITHHELD",
    "Category",
    "Field",
    "Withheld",
]


class Category(enum.StrEnum):
    """The kinds of thing a log line may carry. Closed.

    A field belongs to exactly one of these. A field that fits none of them is
    not a field this service logs, and the way to add one is to argue for a new
    category rather than to file it under the nearest fit.
    """

    IDENTIFIER = "identifier"
    """A name this service or its caller assigned. Not a name a person chose.

    A job identifier is an identifier. A file name inside the operator's photo
    library is not: it is content, it is frequently the subject's name and a
    date, and it is in `WITHHELD` below.
    """

    STATE = "state"
    """Where something is, drawn from a declared enumeration.

    Never free text. The value comes from a type such as
    `retusche.queue.states.JobState`, so the set of things this field can say is
    fixed by that type rather than by whoever wrote the call.
    """

    DURATION = "duration"
    """How long something took, in milliseconds, as a whole number."""

    SIZE = "size"
    """How much of something there is, as a whole number, in a stated unit.

    Pixel counts and byte counts are sizes. The bytes themselves are not.
    """

    MODEL = "model"
    """Which model, by the identifier the registry knows it under."""

    ERROR_REASON = "error-reason"
    """Why something ended badly, drawn from a declared enumeration.

    An exception's message is not an error reason. A message is prose assembled
    at the raise site, and prose is where a path, a prompt or a stranger's
    filename arrives in a log without anybody deciding that it should.
    """


_TEXT_CATEGORIES: Final = frozenset(
    {Category.IDENTIFIER, Category.STATE, Category.MODEL, Category.ERROR_REASON}
)
"""The categories whose values are text."""

_NUMBER_CATEGORIES: Final = frozenset({Category.DURATION, Category.SIZE})
"""The categories whose values are a whole number that is never negative."""


@dataclass(frozen=True, slots=True)
class Field:
    """One field a log line may carry."""

    name: str
    """What the key is called in the rendered line."""

    category: Category
    """Which kind of thing it is, and so what type its value takes."""

    unit: str
    """What the value is expressed in. Never empty.

    A number without its unit is the half that does not survive being carried in
    somebody's head, and a text field's unit says which declared set the value
    is drawn from, which is what makes it checkable by a reader.
    """

    summary: str
    """One sentence: what this field says, and what in the tree produces it."""

    @property
    def takes_text(self) -> bool:
        """Whether this field's value is text rather than a whole number."""
        return self.category in _TEXT_CATEGORIES


@dataclass(frozen=True, slots=True)
class Withheld:
    """One thing that is deliberately never logged, and why."""

    subject: str
    """What is kept out, in the words an operator would use."""

    why: str
    """Why, in terms of what would be in the log if it were not kept out."""


FIELDS: Final = (
    Field(
        name="job_id",
        category=Category.IDENTIFIER,
        unit="the identifier `retusche.queue.store` holds a job under",
        summary=(
            "Which job a line is about. It is the only thing that ties a "
            "refusal, a state change and an ending together, so a line without "
            "it describes an event nobody can follow up."
        ),
    ),
    Field(
        name="job_state",
        category=Category.STATE,
        unit="a value of `retusche.queue.states.JobState`",
        summary=(
            "Where the job is. Drawn from the state table rather than written, "
            "so a log reader and the store cannot disagree about what the "
            "states are."
        ),
    ),
    Field(
        name="previous_job_state",
        category=Category.STATE,
        unit="a value of `retusche.queue.states.JobState`",
        summary=(
            "Where the job was before the move this line records. A state "
            "change is two states, and a log carrying only the new one cannot "
            "answer whether a move was the legal one."
        ),
    ),
    Field(
        name="terminal_reason",
        category=Category.ERROR_REASON,
        unit="a value of `retusche.queue.states.TerminalReason`",
        summary=(
            "Why a job ended. The enumeration separates a refusal from a "
            "breakage and a cancellation from a shutdown, which is the "
            "distinction an operator reading a list of endings needs and the "
            "one a message would blur."
        ),
    ),
    Field(
        name="priority",
        category=Category.STATE,
        unit="a value of `retusche.queue.ordering.Priority`",
        summary=(
            "Which kind of work the job is. It decides the order, so a line "
            "about a long wait is not readable without it."
        ),
    ),
    Field(
        name="queue_position",
        category=Category.SIZE,
        unit="jobs considered ahead of this one",
        summary=(
            "How far back the job sits in the order in force. Produced by "
            "`retusche.queue.ordering.position_of`."
        ),
    ),
    Field(
        name="queue_depth",
        category=Category.SIZE,
        unit="jobs waiting, this one included",
        summary=(
            "How many jobs are waiting in all. The number an operator watches "
            "to see pressure before a caller reports it."
        ),
    ),
    Field(
        name="engine_id",
        category=Category.IDENTIFIER,
        unit="the identifier an engine declares in its capabilities",
        summary=(
            "Which engine a line is about, as the engine names itself in "
            "`retusche_contracts.engine.Capabilities`."
        ),
    ),
    Field(
        name="operation",
        category=Category.STATE,
        unit="a value of `retusche_contracts.engine.Operation`",
        summary=(
            "What was asked for. An operation is a declared set of three, not "
            "a description of the edit."
        ),
    ),
    Field(
        name="model_id",
        category=Category.MODEL,
        unit="the identifier a `models/registry/` entry is declared under",
        summary=(
            "Which weights were involved. It is what makes a result "
            "explainable later, and it is a registry key rather than a path on "
            "the operator's disk."
        ),
    ),
    Field(
        name="image_width_pixels",
        category=Category.SIZE,
        unit="pixels",
        summary=(
            "How wide the image was. A size, and deliberately not the image: "
            "the two numbers are what the device memory estimate is derived "
            "from, and they say nothing about what is in the picture."
        ),
    ),
    Field(
        name="image_height_pixels",
        category=Category.SIZE,
        unit="pixels",
        summary="How tall the image was. The other half of the shape.",
    ),
    Field(
        name="device_memory_estimate_bytes",
        category=Category.SIZE,
        unit="bytes of device memory",
        summary=(
            "What the job was expected to need, as "
            "`retusche_contracts.engine.DeviceMemoryEstimate` reported it."
        ),
    ),
    Field(
        name="device_memory_budget_bytes",
        category=Category.SIZE,
        unit="bytes of device memory",
        summary=(
            "The ceiling the estimate was compared against. A refusal that "
            "names one number and not the other cannot be acted on."
        ),
    ),
)
"""Every field a log line may carry today.

Ordered as a reader meets them: the job, where it is, why it ended, where it
sits, what ran it, and what it cost. Not alphabetical, because the reference
page is read once from the top and looked up rarely.
"""

FIELD_BY_NAME: Final[Mapping[str, Field]] = {field.name: field for field in FIELDS}
"""The declared fields, by the key they appear under."""

WITHHELD: Final = (
    Withheld(
        subject="the image, in whole or in part",
        why=(
            "A thumbnail in a log is the photograph in the log. There is no "
            "size at which an image becomes an operational record."
        ),
    ),
    Withheld(
        subject="the mask",
        why=(
            "A mask says which part of the picture somebody wanted gone. On "
            "its own it describes the subject's outline, and beside the "
            "image size it locates them."
        ),
    ),
    Withheld(
        subject="the prompt",
        why=(
            "A prompt is written by a person about a specific photograph and "
            "is frequently about who is in it. `retusche.queue` records it "
            "against the job so a result can be explained, under the "
            "retention the job record has; the log has a different retention "
            "and a different audience."
        ),
    ),
    Withheld(
        subject="paths and names inside the operator's photo library",
        why=(
            "A library file name is usually a person and a date. The "
            "identifiers above answer every question a path would, and they "
            "answer it without carrying a name nobody chose to publish."
        ),
    ),
    Withheld(
        subject="location, capture time and the rest of the image metadata",
        why=(
            "Where and when a photograph was taken is the field that turns an "
            "operational log into a movement record. Nothing in this service "
            "needs it to describe its own work."
        ),
    ),
    Withheld(
        subject="the operator's credentials, in any rendering",
        why=(
            "A value declared as a secret is handed over as "
            "`retusche.config.secret.Secret`, which renders as `<redacted>` "
            "wherever it is printed. That is the defence; keeping the field "
            "out of this list as well is the second one."
        ),
    ),
)
"""What is kept out of a log line, and why for each.

Not a rule a machine reads. Every entry here is a thing that has no declared
field, so what refuses it is `FIELDS` being closed rather than this list being
consulted. It exists because the closed list answers a different question from
the one an operator asks, and because a service that says only what it permits
has not said what it withholds.
"""
