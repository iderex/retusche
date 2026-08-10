# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Logging: a line describes the work, and never what was in the picture.

`retusche.logging.fields` declares the categories a line may carry, the fields
that exist today, and what is deliberately kept out.
`retusche.logging.records` builds a line and refuses one that would carry
anything else. `retusche.logging.reference` writes `docs/logging.md` from both,
so the page an operator copies into their own record cannot describe a field
set the code has moved away from.

There is no message and no format string anywhere in here. That is the property
the rest follows from: a format string accepts a filename, a prompt or a
caller's own text and says so nowhere, and a declared field set cannot.

Nothing in this tree logs yet. What arrives with the first log site is a call to
`record`, and what refuses a module going around this one rather than through it
is `[tool.retusche.output-discipline]` in `pyproject.toml`, applied by
`tests/test_output_discipline.py` to every module under the orchestration
packages except this one.
"""

from __future__ import annotations

from retusche.logging.fields import (
    FIELD_BY_NAME,
    FIELDS,
    WITHHELD,
    Category,
    Field,
    Withheld,
)
from retusche.logging.records import (
    EVENT_SHAPE,
    Level,
    Log,
    LogLineError,
    Record,
    level_from_name,
    record,
    render,
)
from retusche.logging.reference import logging_markdown

__all__ = [
    "EVENT_SHAPE",
    "FIELDS",
    "FIELD_BY_NAME",
    "WITHHELD",
    "Category",
    "Field",
    "Level",
    "Log",
    "LogLineError",
    "Record",
    "Withheld",
    "level_from_name",
    "logging_markdown",
    "record",
    "render",
]
