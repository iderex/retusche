# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What a log line may carry, shown being refused rather than described.

Every guard here is exercised twice: once with the line somebody meant to write
and once with the line somebody would actually write by mistake. The near
misses are the point. `prompt="a man in a red coat"` is not a mistake anybody
makes deliberately; it is what a caller writes when they are adding one useful
field to a line they already have, and it is the shape this module exists to
refuse.

The representative run at the bottom is the one this issue's fourth line asks
for: a job walked from acceptance to an ending, every line it produced
collected, and the whole set held against the declaration. It runs against the
state table and the ordering rather than against a service, because there is no
service yet, and what it establishes is bounded accordingly and said so where
it is written.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from retusche.config.settings import SETTINGS
from retusche.logging.fields import FIELD_BY_NAME, FIELDS, WITHHELD, Category
from retusche.logging.records import (
    EVENT_SHAPE,
    Level,
    Log,
    LogLineError,
    level_from_name,
    record,
    render,
)
from retusche.logging.reference import logging_markdown
from retusche.queue.ordering import Priority, QueuePosition, Waiting, order, position_of
from retusche.queue.states import JobState, TerminalReason, check_transition

if TYPE_CHECKING:
    from collections.abc import Iterator

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent


class _Sink:
    """Somewhere for a line to go, and a record of what arrived."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, line: str) -> None:
        self.lines.append(line)

    def objects(self) -> list[dict[str, object]]:
        """What arrived, parsed, so a test asserts on keys and not on text."""
        return [json.loads(line) for line in self.lines]


def test_a_declared_field_is_carried() -> None:
    """The ordinary case, so the refusals below are not the only thing shown."""
    entry = record("job.state-changed", Level.INFO, job_id="j-1", queue_depth=3)
    assert entry.fields == {"job_id": "j-1", "queue_depth": 3}


def test_a_field_nobody_declared_is_refused() -> None:
    """The near miss: one useful-looking field added to a line that was fine."""
    with pytest.raises(LogLineError) as refusal:
        record("job.accepted", Level.INFO, job_id="j-1", prompt="a man in a red coat")
    assert "'prompt' is not a declared log field" in str(refusal.value)


@pytest.mark.parametrize(
    "name",
    ["file_path", "asset_path", "image", "mask", "gps_latitude", "api_key"],
)
def test_the_fields_an_operator_asks_about_are_not_declared(name: str) -> None:
    """Named individually, because a closed list is only as good as its contents.

    Each of these is a field somebody has put in a log before. The assertion is
    on the declaration rather than on a call, so it holds for every call site
    that will ever exist rather than for the ones written today.
    """
    assert name not in FIELD_BY_NAME


def test_every_problem_is_reported_rather_than_the_first() -> None:
    """Four mistakes, corrected once. The same property the loader has."""
    with pytest.raises(LogLineError) as refusal:
        record("job.accepted", Level.INFO, prompt="x", file_path="y", location="z")
    message = str(refusal.value)
    assert "'prompt'" in message
    assert "'file_path'" in message
    assert "'location'" in message


def test_an_event_name_that_is_a_sentence_is_refused() -> None:
    """What a format string looks like on the way in, before there is a field."""
    with pytest.raises(LogLineError) as refusal:
        record("edited /library/2019/anna-birthday.jpg", Level.INFO)
    assert "is not a dotted lower-case token" in str(refusal.value)


@pytest.mark.parametrize(
    "event",
    [
        "job",
        "Job.accepted",
        "job.accepted ",
        "job accepted",
        "job..accepted",
        "job.accepted.",
        "job.accepted/2",
        "",
    ],
)
def test_an_event_name_outside_the_shape_is_refused(event: str) -> None:
    """The shape is what stops the one key that is not a field carrying content."""
    assert EVENT_SHAPE.fullmatch(event) is None
    with pytest.raises(LogLineError):
        record(event, Level.INFO)


@pytest.mark.parametrize(
    "event",
    ["job.accepted", "job.state-changed", "model.registry-loaded", "queue.depth.high"],
)
def test_the_shape_accepts_the_names_this_project_would_write(event: str) -> None:
    """A guard that refused these would be refusing the work rather than a defect."""
    assert record(event, Level.INFO).event == event


def test_a_number_field_given_text_is_refused() -> None:
    """A count read out of a header arrives as text, and reads as one in JSON."""
    with pytest.raises(LogLineError) as refusal:
        record("queue.measured", Level.INFO, queue_depth="3")
    assert "takes a whole number" in str(refusal.value)


def test_a_boolean_is_not_a_number() -> None:
    """`True` would render as 1 and read as a measurement of one."""
    with pytest.raises(LogLineError) as refusal:
        record("queue.measured", Level.INFO, queue_depth=True)
    assert "takes a whole number" in str(refusal.value)


def test_a_negative_size_is_refused() -> None:
    """A size below zero is a subtraction that went the wrong way."""
    with pytest.raises(LogLineError) as refusal:
        record("queue.measured", Level.INFO, queue_depth=-1)
    assert "does not go below zero" in str(refusal.value)


def test_a_text_field_given_a_number_is_refused() -> None:
    """An identifier that arrived as an integer is one the store cannot look up."""
    with pytest.raises(LogLineError) as refusal:
        record("job.accepted", Level.INFO, job_id=7)
    assert "takes text" in str(refusal.value)


def test_an_empty_identifier_is_refused() -> None:
    """An absent value written as `""` reads as a job whose identifier is blank."""
    with pytest.raises(LogLineError) as refusal:
        record("job.accepted", Level.INFO, job_id="")
    assert "says less than omitting it" in str(refusal.value)


@pytest.mark.parametrize(
    "value",
    ["j 1", "anna birthday", "j-1\nlevel=error", "j\t1", "j-1\x00"],
)
def test_a_text_field_carrying_prose_or_a_line_break_is_refused(value: str) -> None:
    """Two defects in one guard, and the second is the one that is not obvious.

    A value with a space in it is prose arriving where a declared value was
    meant. A value with a newline in it is a second log line: JSON escapes it
    here, and the consumer that unescapes and splits is the one that gets a
    forged record out of it.
    """
    with pytest.raises(LogLineError) as refusal:
        record("job.accepted", Level.INFO, job_id=value)
    assert "prose rather than a value" in str(refusal.value)


def test_a_line_renders_as_one_json_object_with_sorted_keys() -> None:
    """Two lines about the same thing differ only where the thing differed."""
    line = render(
        record(
            "job.refused",
            Level.WARNING,
            queue_depth=2,
            job_id="j-1",
            terminal_reason=TerminalReason.REFUSED_OVER_BUDGET,
        )
    )
    assert line == (
        '{"event":"job.refused","level":"warning","job_id":"j-1",'
        '"queue_depth":2,"terminal_reason":"refused-over-budget"}'
    )
    assert "\n" not in line


def test_a_state_enumeration_is_carried_as_its_value() -> None:
    """`JobState` is a `StrEnum`, so the line holds the word the store holds."""
    line = json.loads(
        render(record("job.moved", Level.INFO, job_state=JobState.QUEUED))
    )
    assert line["job_state"] == "queued"


def test_a_line_below_the_threshold_is_not_written() -> None:
    sink = _Sink()
    log = Log(Level.INFO, sink)
    assert log.emit(record("job.detail", Level.DEBUG, job_id="j-1")) is False
    assert sink.lines == []


def test_a_line_at_the_threshold_is_written() -> None:
    """The boundary itself, because at-or-above is where this is written wrong."""
    sink = _Sink()
    log = Log(Level.INFO, sink)
    assert log.emit(record("job.accepted", Level.INFO, job_id="j-1")) is True
    assert log.level is Level.INFO
    assert len(sink.lines) == 1


@pytest.mark.parametrize("level", list(Level))
def test_no_level_admits_a_field_the_declaration_does_not_carry(level: Level) -> None:
    """The operator-facing claim, made against every level rather than about them.

    The check is not on the emit route at all, so this is a demonstration of an
    arrangement rather than a sample of one. A level that widened the set would
    have to reach into `record`, which takes no level for that purpose.
    """
    sink = _Sink()
    log = Log(Level.DEBUG, sink)
    with pytest.raises(LogLineError):
        log.emit(record("job.accepted", level, prompt="a man in a red coat"))
    assert sink.lines == []


@pytest.mark.parametrize("level", list(Level))
def test_the_most_verbose_threshold_writes_every_level(level: Level) -> None:
    """Turning everything on adds lines and does not add kinds of value."""
    sink = _Sink()
    log = Log(Level.DEBUG, sink)
    assert log.emit(record("job.accepted", level, job_id="j-1")) is True
    assert set(sink.objects()[0]) == {"event", "level", "job_id"}


def test_a_level_an_operator_wrote_is_read() -> None:
    assert level_from_name("warning") is Level.WARNING


def test_a_level_nobody_declared_is_refused_with_the_set() -> None:
    """The loader checks that the value is text. This is where the set is."""
    with pytest.raises(LogLineError) as refusal:
        level_from_name("verbose")
    assert "debug, info, warning, error" in str(refusal.value)


def test_the_log_level_setting_is_declared_with_a_default_in_the_set() -> None:
    """The declaration and the enumeration agree, without either quoting the other."""
    declared = next(setting for setting in SETTINGS if setting.name == "log_level")
    assert declared.default is not None
    assert level_from_name(declared.default) is Level.INFO


def test_every_declared_field_belongs_to_a_declared_category() -> None:
    """The categories are the rule. A field outside them is not a field."""
    assert {field.category for field in FIELDS} <= set(Category)


def test_no_two_fields_share_a_name() -> None:
    """A duplicate would make the later one win silently in the lookup table."""
    assert len(FIELD_BY_NAME) == len(FIELDS)


def test_every_declared_field_carries_a_unit_and_a_sentence() -> None:
    """A name and a type describe the key. Neither describes the decision."""
    assert all(field.unit and field.summary for field in FIELDS)


def test_a_field_may_not_be_called_event_or_level() -> None:
    """Both keys are written by `render`, so a field of either name would be lost."""
    assert "event" not in FIELD_BY_NAME
    assert "level" not in FIELD_BY_NAME


def test_the_withheld_list_names_what_it_keeps_out_and_why() -> None:
    """A list of what is permitted answers a different question from this one."""
    assert WITHHELD
    assert all(entry.subject and entry.why for entry in WITHHELD)


def test_the_committed_page_is_what_the_declaration_produces() -> None:
    """The page an operator copies cannot describe a field set the code has left."""
    committed = (_REPO_ROOT / "docs" / "logging.md").read_text(encoding="utf-8")
    assert committed == logging_markdown()


def test_the_page_names_every_declared_field_and_every_withheld_subject() -> None:
    """Generated is not the same as complete, so the two lists are checked."""
    page = logging_markdown()
    assert all(f"`{field.name}`" in page for field in FIELDS)
    assert all(entry.subject.lower() in page.lower() for entry in WITHHELD)
    assert all(entry.why in page for entry in WITHHELD)


def test_the_page_says_which_categories_have_no_field_yet() -> None:
    """An empty category read as an omission is the disclosure failing."""
    assert "No field is declared under this category yet" in logging_markdown()


def _representative_run() -> Iterator[tuple[str, Level, dict[str, str | int]]]:
    """One job from acceptance to an ending, as lines somebody would write.

    Driven through `retusche.queue.states` and `retusche.queue.ordering`, so
    the states and the position are what those modules produce rather than
    what this file thinks they are. What it is not is a service: nothing here
    has run an edit, and the run this stands in for is the one that arrives
    with #17 and #27.
    """
    waiting = (
        Waiting(job_id="j-1", priority=Priority.INTERACTIVE, arrival=1),
        Waiting(job_id="j-2", priority=Priority.BACKGROUND, arrival=0),
    )
    ordered = order(waiting)
    position = position_of("j-1", ordered)
    assert isinstance(position, QueuePosition)

    yield "job.accepted", Level.INFO, {"job_id": "j-1", "job_state": JobState.ACCEPTED}
    check_transition(JobState.ACCEPTED, JobState.QUEUED, None)
    yield (
        "job.queued",
        Level.INFO,
        {
            "job_id": "j-1",
            "previous_job_state": JobState.ACCEPTED,
            "job_state": JobState.QUEUED,
            "priority": Priority.INTERACTIVE,
            "queue_position": position.ahead,
            "queue_depth": position.total_waiting,
        },
    )
    check_transition(JobState.QUEUED, JobState.RUNNING, None)
    yield (
        "job.started",
        Level.INFO,
        {
            "job_id": "j-1",
            "previous_job_state": JobState.QUEUED,
            "job_state": JobState.RUNNING,
            "engine_id": "fake",
            "model_id": "fake-erase-1",
            "image_width_pixels": 4032,
            "image_height_pixels": 3024,
            "device_memory_estimate_bytes": 1_073_741_824,
            "device_memory_budget_bytes": 4_294_967_296,
        },
    )
    check_transition(JobState.RUNNING, JobState.SUCCEEDED, TerminalReason.COMPLETED)
    yield (
        "job.ended",
        Level.INFO,
        {
            "job_id": "j-1",
            "previous_job_state": JobState.RUNNING,
            "job_state": JobState.SUCCEEDED,
            "terminal_reason": TerminalReason.COMPLETED,
        },
    )


def test_a_representative_run_produces_nothing_outside_the_declaration() -> None:
    """The fourth line of #64, against the run this tree can actually produce.

    The assertion is on the keys of every line that arrived, so a field added
    to a call site in this file without being added to the declaration fails
    here as well as at the call. What it does not establish is that a service
    logs only these, because no service in this tree logs at all.
    """
    sink = _Sink()
    log = Log(Level.DEBUG, sink)
    for event, level, fields in _representative_run():
        assert log.emit(record(event, level, **fields)) is True

    permitted = set(FIELD_BY_NAME) | {"event", "level"}
    for line in sink.objects():
        assert set(line) <= permitted, f"undeclared key in {line}"

    assert len(sink.lines) == 4
    assert [line["event"] for line in sink.objects()] == [
        "job.accepted",
        "job.queued",
        "job.started",
        "job.ended",
    ]


def test_the_representative_run_carries_no_value_holding_prose() -> None:
    """A second reading of the same output, against content rather than keys.

    A declared field holding a sentence is how content arrives once the key
    check is satisfied, and `record` refuses it, so this asserts the outcome
    the refusal produces rather than trusting that it fired.
    """
    sink = _Sink()
    log = Log(Level.DEBUG, sink)
    for event, level, fields in _representative_run():
        log.emit(record(event, level, **fields))

    for line in sink.objects():
        for key, value in line.items():
            if isinstance(value, str):
                assert " " not in value, f"{key} holds prose"
