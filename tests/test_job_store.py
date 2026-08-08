# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The store, what a restart finds in it, and what it refuses to read.

The state machine is exercised next door in `test_job_states.py`, against no
file at all. What is asked here is the half that only a file can answer: that a
committed move is in the file rather than in an object, that a refused move
leaves the file as it was, and that a job which was on the device when the
process ended is not still claiming to run.

What is shown about durability, and what is not
-----------------------------------------------
A record written by one `JobStore` is read back by a second one over the same
path, and by a connection this module opens itself that never saw the writer. So
what is measured is that the row reaches the file at commit and is readable
without the writer.

No test here kills a process, cuts power, or fills a disk. Survival across an
unclean stop rests on SQLite's own guarantee under the journal mode and the
synchronous setting the store sets, which is argued in
`docs/decisions/0005-job-store.md` and is not measured by anything in this
repository. That is a claim carried over from the store's documentation rather
than a result of this file.

No device, no display and no elevation is needed by anything here.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from retusche.queue.states import (
    IllegalTransitionError,
    JobState,
    TerminalReason,
    TerminalReasonError,
)
from retusche.queue.store import (
    CorruptJobStoreError,
    DuplicateJobError,
    JobStore,
    UnknownJobError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    """A store file of this test's own, gone with the temporary directory."""
    return tmp_path / "jobs.sqlite3"


@pytest.fixture
def store(store_path: Path) -> Iterator[JobStore]:
    """An open store, closed however the test ends."""
    with JobStore(store_path) as opened:
        yield opened


def test_an_accepted_job_is_readable_by_its_identifier(store: JobStore) -> None:
    """The first thing a caller is promised: the job exists and can be asked about."""
    recorded = store.accept("job-1")
    assert recorded.state is JobState.ACCEPTED
    assert recorded.reason is None
    assert store.read("job-1") == recorded


def test_a_job_nobody_accepted_is_not_answered_with_a_default(store: JobStore) -> None:
    """A missing job raises rather than reading as a job in some quiet state."""
    with pytest.raises(UnknownJobError) as refused:
        store.read("never-accepted")
    assert "never-accepted" in str(refused.value)


def test_the_same_identifier_twice_is_refused(store: JobStore) -> None:
    """Accepting over a job is the one way a finished job becomes unfinished."""
    store.accept("job-1")
    store.move("job-1", JobState.QUEUED)
    store.move("job-1", JobState.RUNNING)
    store.move("job-1", JobState.SUCCEEDED, TerminalReason.COMPLETED)
    with pytest.raises(DuplicateJobError):
        store.accept("job-1")
    assert store.read("job-1").state is JobState.SUCCEEDED


def test_a_job_walks_the_whole_path_to_a_result(store: JobStore) -> None:
    """Accepted, queued, running, succeeded, with the outcome on the record."""
    store.accept("job-1")
    assert store.move("job-1", JobState.QUEUED).state is JobState.QUEUED
    assert store.move("job-1", JobState.RUNNING).state is JobState.RUNNING
    finished = store.move("job-1", JobState.SUCCEEDED, TerminalReason.COMPLETED)
    assert finished.state is JobState.SUCCEEDED
    assert finished.reason is TerminalReason.COMPLETED
    assert store.read("job-1") == finished


def test_a_move_the_table_refuses_leaves_the_file_as_it_was(store: JobStore) -> None:
    """The refusal and the rollback are one thing, so a half-move cannot land."""
    store.accept("job-1")
    with pytest.raises(IllegalTransitionError):
        store.move("job-1", JobState.RUNNING)
    assert store.read("job-1").state is JobState.ACCEPTED


def test_a_terminal_move_without_its_reason_writes_nothing(store: JobStore) -> None:
    """The reason rule reaches the store, and a refused write rolls back."""
    store.accept("job-1")
    store.move("job-1", JobState.QUEUED)
    store.move("job-1", JobState.RUNNING)
    with pytest.raises(TerminalReasonError):
        store.move("job-1", JobState.FAILED)
    assert store.read("job-1").state is JobState.RUNNING


def test_moving_a_job_nobody_accepted_is_refused(store: JobStore) -> None:
    """A move is a read and a write, and the read is the one that answers first."""
    with pytest.raises(UnknownJobError):
        store.move("never-accepted", JobState.QUEUED)


def test_in_state_answers_by_identifier_and_leaves_the_rest_out(
    store: JobStore,
) -> None:
    """One order, every run, so a report of the queue is comparable with the last."""
    for job_id in ("job-3", "job-1", "job-2"):
        store.accept(job_id)
        store.move(job_id, JobState.QUEUED)
    store.move("job-2", JobState.RUNNING)
    assert [record.job_id for record in store.in_state(JobState.QUEUED)] == [
        "job-1",
        "job-3",
    ]
    assert [record.job_id for record in store.in_state(JobState.RUNNING)] == ["job-2"]
    assert store.in_state(JobState.CANCELLED) == ()


def test_a_committed_job_is_in_the_file_and_not_in_the_object(
    store_path: Path,
) -> None:
    """The durability this file can measure: a second store over the same path."""
    with JobStore(store_path) as first:
        first.accept("job-1")
        first.move("job-1", JobState.QUEUED)

    with JobStore(store_path) as second:
        recovered = second.read("job-1")
    assert recovered.state is JobState.QUEUED


def test_a_committed_row_is_readable_by_a_connection_that_never_saw_the_writer(
    store: JobStore, store_path: Path
) -> None:
    """Read with plain SQLite, so the answer is not this module agreeing with itself."""
    store.accept("job-1")
    store.move("job-1", JobState.QUEUED)
    connection = sqlite3.connect(store_path)
    try:
        row = connection.execute(
            "SELECT state, reason FROM jobs WHERE job_id = ?", ("job-1",)
        ).fetchone()
    finally:
        connection.close()
    assert row == ("queued", None)


def test_a_restart_leaves_a_queued_job_queued(store_path: Path) -> None:
    """Nothing was lost, so there is nothing to settle and nothing is touched."""
    with JobStore(store_path) as first:
        first.accept("waiting")
        first.move("waiting", JobState.QUEUED)
        first.accept("not-yet-offered")

    with JobStore(store_path) as second:
        recovered = second.recover_after_restart()
        assert recovered == ()
        assert second.read("waiting").state is JobState.QUEUED
        assert second.read("not-yet-offered").state is JobState.ACCEPTED


def test_a_restart_settles_a_job_that_was_on_the_device(store_path: Path) -> None:
    """A running job after a restart is running nowhere, and says so."""
    with JobStore(store_path) as first:
        for job_id in ("job-1", "job-2"):
            first.accept(job_id)
            first.move(job_id, JobState.QUEUED)
            first.move(job_id, JobState.RUNNING)
        first.accept("job-3")
        first.move("job-3", JobState.QUEUED)

    with JobStore(store_path) as second:
        recovered = second.recover_after_restart()
        assert [record.job_id for record in recovered] == ["job-1", "job-2"]
        for record in recovered:
            assert record.state is JobState.INTERRUPTED
            assert record.reason is TerminalReason.INTERRUPTED_BY_SHUTDOWN
        assert second.read("job-1").state is JobState.INTERRUPTED
        assert second.read("job-3").state is JobState.QUEUED
        assert second.in_state(JobState.RUNNING) == ()


def test_an_interrupted_job_is_not_reported_among_the_failures(
    store_path: Path,
) -> None:
    """The distinct state is only worth having if a failure list excludes it."""
    with JobStore(store_path) as first:
        first.accept("job-1")
        first.move("job-1", JobState.QUEUED)
        first.move("job-1", JobState.RUNNING)

    with JobStore(store_path) as second:
        second.recover_after_restart()
        assert second.in_state(JobState.FAILED) == ()
        assert [record.job_id for record in second.in_state(JobState.INTERRUPTED)] == [
            "job-1"
        ]


def test_recovery_is_safe_to_run_twice(store_path: Path) -> None:
    """A restart during a restart is a restart, and the second pass finds nothing."""
    with JobStore(store_path) as first:
        first.accept("job-1")
        first.move("job-1", JobState.QUEUED)
        first.move("job-1", JobState.RUNNING)

    with JobStore(store_path) as second:
        assert len(second.recover_after_restart()) == 1
        assert second.recover_after_restart() == ()


def _write_raw(path: Path, job_id: str, state: str, reason: str | None) -> None:
    """Put a row in the file behind the store's back, the way a hand edit would."""
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO jobs (job_id, state, reason) VALUES (?, ?, ?)",
            (job_id, state, reason),
        )
        connection.commit()
    finally:
        connection.close()


def test_a_state_this_version_does_not_declare_is_refused(
    store: JobStore, store_path: Path
) -> None:
    """A file written by something else is refused where it is read."""
    _write_raw(store_path, "job-1", "paused", None)
    with pytest.raises(CorruptJobStoreError) as refused:
        store.read("job-1")
    assert "paused" in str(refused.value)


def test_a_reason_this_version_does_not_declare_is_refused(
    store: JobStore, store_path: Path
) -> None:
    """The same rule over the second column, which no other test reaches."""
    _write_raw(store_path, "job-1", "failed", "the-cat-unplugged-it")
    with pytest.raises(CorruptJobStoreError) as refused:
        store.read("job-1")
    assert "the-cat-unplugged-it" in str(refused.value)


def test_a_stored_row_whose_reason_does_not_fit_its_state_is_refused(
    store: JobStore, store_path: Path
) -> None:
    """Both halves are known words and the pair is one the state machine refuses."""
    _write_raw(store_path, "job-1", "succeeded", "engine-failure")
    with pytest.raises(CorruptJobStoreError) as refused:
        store.read("job-1")
    assert "engine-failure" in str(refused.value)


def test_a_terminal_row_stored_without_its_reason_is_refused(
    store: JobStore, store_path: Path
) -> None:
    """The missing half, which a schema that merely allowed null would not catch."""
    _write_raw(store_path, "job-1", "cancelled", None)
    with pytest.raises(CorruptJobStoreError):
        store.read("job-1")


def test_a_corrupt_row_is_refused_when_it_is_listed_as_well(
    store: JobStore, store_path: Path
) -> None:
    """Listing reads rows too, so it refuses what reading one refuses."""
    _write_raw(store_path, "job-1", "queued", "completed")
    with pytest.raises(CorruptJobStoreError):
        store.in_state(JobState.QUEUED)


def test_the_store_can_be_opened_and_closed_without_the_block_form(
    store_path: Path,
) -> None:
    """The lifetime a service has is longer than a block, so both forms work."""
    opened = JobStore(store_path)
    opened.accept("job-1")
    opened.close()
    with JobStore(store_path) as reopened:
        assert reopened.read("job-1").state is JobState.ACCEPTED
