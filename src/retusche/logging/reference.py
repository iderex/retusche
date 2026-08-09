# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The operator's page about the logs, written from the declaration.

`docs/logging.md` is produced by this module and by nothing else, and the suite
refuses a committed page that differs from what this produces. The page is the
one an operator copies into their own record of processing, so it is the last
document in this tree that may describe a field set the code has moved away
from: a data protection statement that is out of date is worse than none,
because it is relied on.

The trade is the same one `retusche.config.reference` records and it is made
the same way for the same reason. The prose below sits in a module rather than
in the document it describes, which is the wrong place for prose if you are
reading the document. What is bought is that the list of fields in the page and
the list the code refuses against are one list.
"""

from __future__ import annotations

from retusche.logging.fields import FIELDS, WITHHELD, Category, Field
from retusche.logging.records import Level

__all__ = ["logging_markdown"]

_PREAMBLE = """# What the logs contain

This page is generated from `retusche.logging.fields` and
`retusche.logging.records`, and the suite refuses a committed copy that differs
from what the declaration produces. Edit the declaration, not this file.

It is written to be copied into a deployment's own record of processing. What
it describes is the log this service produces. Where those lines are then sent,
how long they are kept and who reads them are the operator's decisions and are
not visible from here.

## What a line is

One JSON object per line, with sorted keys. Two keys are always present:

- `event`, the name of what happened, as a dotted lower-case token such as
  `job.state-changed`
- `level`, one of the values in the table below

Everything else is a declared field from the tables further down, and there is
no message. A log line is not a sentence with values pushed into it, which is
the arrangement by which a filename, a prompt or a caller's own text arrives in
a log without anyone deciding it should. `retusche.logging.records.record`
refuses an event name that is not that shape and refuses a field the
declaration does not carry, so a line carrying something else cannot be built
rather than being unlikely.

## Levels

The level decides whether a line is written. It does not decide what a line may
carry: the field check happens when the line is built, before any level is
compared, so there is no setting at which the service starts logging picture
content. Raising the level shows more lines of the kinds below, and never
another kind.

The level is the `log_level` setting, in `docs/configuration.md`.
"""

_FIELDS_HEADING = """## The fields

Grouped by category. The categories are the rule and are closed: a field
belongs to one of them or it is not logged. The fields are what the service
produces today, and the list grows with it.
"""

_WITHHELD_HEADING = """## What is deliberately not logged

None of the following has a field, at any level, in any line. What refuses them
is that the field list above is closed and is checked when a line is built, not
a rule that consults this list.
"""

_CLOSING = """## What this page does not establish

That every part of this service logs through the declaration above. Nothing in
this tree logs at all yet: the module and its refusals exist, and the first log
site arrives with the component that has something to say. A check that refuses
a logging call made outside this module is issue #80, and until it lands, what
stands behind the claim is review.

That the lines are kept safely once they leave this process. A log written to a
file an operator ships elsewhere is subject to whatever that destination does,
and nothing here reaches it.

That an operator's own duties are discharged. This page says what the service
produces. Which of it is personal data in a given deployment, on what basis it
is processed, and for how long it is kept are decisions the operator makes.
`docs/legal/data-protection.md` is where the boundary between the two is drawn.
"""

_CATEGORY_NOTE = {
    Category.IDENTIFIER: (
        "A name this service or its caller assigned. Never a name a person "
        "chose for a file."
    ),
    Category.STATE: "Where something is, drawn from a declared enumeration.",
    Category.DURATION: "How long something took, in milliseconds.",
    Category.SIZE: "How much of something there is, as a whole number.",
    Category.MODEL: "Which model, by its registry identifier.",
    Category.ERROR_REASON: (
        "Why something ended badly, drawn from a declared enumeration rather "
        "than from an exception's message."
    ),
}


def logging_markdown() -> str:
    """The whole page, ending with a newline, as the tree carries it."""
    sections = [_PREAMBLE.rstrip("\n"), _levels_table(), _FIELDS_HEADING.rstrip("\n")]
    sections.extend(_category_section(category) for category in Category)
    sections.append(_WITHHELD_HEADING.rstrip("\n"))
    sections.extend(
        f"{entry.subject[0].upper()}{entry.subject[1:]}. {entry.why}"
        for entry in WITHHELD
    )
    sections.append(_CLOSING.rstrip("\n"))
    return "\n\n".join(sections) + "\n"


def _levels_table() -> str:
    """The levels, in the order they escalate, with what each one is for."""
    rows = "\n".join(f"| `{level.value}` | {_LEVEL_NOTE[level]} |" for level in Level)
    return f"| Level | What it carries |\n| --- | --- |\n{rows}"


def _category_section(category: Category) -> str:
    """One category: what it is, and the fields declared under it."""
    fields = [field for field in FIELDS if field.category is category]
    body = (
        "\n".join(_field_entry(field) for field in fields)
        if fields
        else (
            "No field is declared under this category yet, because nothing in "
            "this tree produces one. A field declared before there is a value "
            "for it is a name a reader would trust with nothing behind it."
        )
    )
    return f"### {category.value}\n\n{_CATEGORY_NOTE[category]}\n\n{body}"


def _field_entry(field: Field) -> str:
    """One field: its key, what it says, and what its value is drawn from."""
    return f"- `{field.name}`. {field.summary} Value: {field.unit}."


_LEVEL_NOTE = {
    Level.DEBUG: "Detail an operator turns on while working out what happened.",
    Level.INFO: "The service doing what it is for.",
    Level.WARNING: (
        "Something an operator should look at before it becomes a failure."
    ),
    Level.ERROR: "Work that did not happen, or a component that has stopped.",
}
