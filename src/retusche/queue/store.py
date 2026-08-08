# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The durable job store, and what a restart finds in it.

A job outlives the process that accepted it. An operator restarting the service
must not lose a queue, and a caller polling for a result must not be told a job
never existed, so the record is written to a file before the caller is answered
and every move is a committed transaction rather than a field on an object.

The means is `sqlite3` from the standard library, and
`docs/decisions/0005-job-store.md` is where that is argued: what an unclean stop
leaves behind, and what an operator has to administer, which is nothing.

Every move goes through `retusche.queue.states.check_transition` inside the
transaction that would write it. Checking before opening the transaction would
be checking a state the file may no longer hold by the time the write lands.

What a record carries
---------------------
An identifier, a state and, where the state is terminal, a reason. Nothing
else. The fields that let a request be reconstructed, the seed and the model and
the parameters, are #24's, and the timestamps an operator wants are #65's; a
column added here for either would be a column nothing writes and nothing reads,
which is the shape a schema rots in.

What this module does not hold
------------------------------
Ordering, priority and admission. `in_state` answers which jobs are somewhere
and says nothing about which of them is next: first in, first out and the
starvation bound are #28, and a `sequence` column written here before that issue
chose one would be the ordering rule arriving by accident.

Threads
-------
One connection, used from the thread that opened it, which is what `sqlite3`
defaults to. The queue is one process and the lane is single-flight (#27), so
nothing here needs more yet, and the day it does the change is visible rather
than already made.
"""

from __future__ import annotations

import contextlib
import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from retusche.queue.states import (
    JobState,
    TerminalReason,
    check_transition,
    reason_problem,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from types import TracebackType

__all__ = [
    "CorruptJobStoreError",
    "DuplicateJobError",
    "JobRecord",
    "JobStore",
    "JobStoreError",
    "UnknownJobError",
]

_SCHEMA: Final = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY NOT NULL,
    state  TEXT NOT NULL,
    reason TEXT
)
"""

_SELECT_ONE: Final = "SELECT job_id, state, reason FROM jobs WHERE job_id = ?"
_SELECT_BY_STATE: Final = (
    "SELECT job_id, state, reason FROM jobs WHERE state = ? ORDER BY job_id"
)
_INSERT: Final = "INSERT INTO jobs (job_id, state, reason) VALUES (?, ?, ?)"
_UPDATE: Final = "UPDATE jobs SET state = ?, reason = ? WHERE job_id = ?"


@dataclass(frozen=True, slots=True)
class JobRecord:
    """One job as the file holds it."""

    job_id: str
    state: JobState
    reason: TerminalReason | None


class JobStoreError(Exception):
    """Base of everything this store refuses."""


class UnknownJobError(JobStoreError):
    """No job by that identifier is in the store.

    Raised rather than answered with ``None`` so that a caller cannot read a
    missing job as a job in some default state. A poll for a job that was
    accepted and a poll for one that never was are different answers.
    """


class DuplicateJobError(JobStoreError):
    """A job by that identifier is already in the store.

    Accepting it again would overwrite whatever state it had reached, which is
    the one way a finished job silently becomes an unfinished one.
    """


class CorruptJobStoreError(JobStoreError):
    """A row in the file is not a job this project's state machine describes.

    The file is a file, and a file gets edited, restored from a backup taken
    from a different version, or written by a build that had one more state than
    this one. Reading such a row into a `JobRecord` would put a state nothing
    can move out of into the middle of a run, so it is refused at the point it
    is read.
    """


class JobStore:
    """Jobs on disk, moved only through the transition table.

    Used as a context manager, or opened and closed by hand where the lifetime
    is longer than a block.
    """

    def __init__(self, path: Path) -> None:
        """Open, or create, the store at ``path`` and make sure of the schema."""
        self._connection = sqlite3.connect(path, isolation_level=None)
        # Write-ahead logging so a reader never blocks the writer, and FULL so a
        # commit is on the platter before it is reported as committed. The
        # decision record argues both; the pair is what makes an unclean stop
        # lose at most the transaction that had not committed.
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA synchronous = FULL")
        self._connection.execute(_SCHEMA)

    def __enter__(self) -> JobStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.close()

    def close(self) -> None:
        """Close the connection. Committed rows are already in the file."""
        self._connection.close()

    def accept(self, job_id: str) -> JobRecord:
        """Record a new job in `JobState.ACCEPTED` and return it."""
        with self._transaction():
            try:
                self._connection.execute(_INSERT, (job_id, JobState.ACCEPTED, None))
            except sqlite3.IntegrityError as error:
                raise DuplicateJobError(
                    f"a job with identifier {job_id!r} is already in this store. "
                    f"Accepting it again would overwrite the state it has "
                    f"reached, so the caller that generated the identifier has "
                    f"generated one twice."
                ) from error
        return JobRecord(job_id, JobState.ACCEPTED, None)

    def read(self, job_id: str) -> JobRecord:
        """The job by that identifier. Raises `UnknownJobError` if there is none."""
        row = self._connection.execute(_SELECT_ONE, (job_id,)).fetchone()
        return self._record(job_id, row)

    def in_state(self, state: JobState) -> tuple[JobRecord, ...]:
        """Every job in ``state``, by identifier, so a run reports in one order."""
        rows = self._connection.execute(_SELECT_BY_STATE, (state,)).fetchall()
        return tuple(self._record(row[0], row) for row in rows)

    def move(
        self,
        job_id: str,
        target: JobState,
        reason: TerminalReason | None = None,
    ) -> JobRecord:
        """Move a job, or refuse the move and leave the file as it was.

        The read, the check and the write are one transaction, so a refusal
        cannot leave a half-applied move behind and a move cannot be decided
        against a state another writer has since changed.
        """
        with self._transaction():
            current = self._record(
                job_id, self._connection.execute(_SELECT_ONE, (job_id,)).fetchone()
            )
            check_transition(current.state, target, reason)
            self._connection.execute(_UPDATE, (target, reason, job_id))
        return JobRecord(job_id, target, reason)

    def recover_after_restart(self) -> tuple[JobRecord, ...]:
        """Settle what the last stop left, and return what was changed.

        A job that was on the device when the process ended is not running: no
        process is running it, and nothing will report on it again. It becomes
        `JobState.INTERRUPTED`, which is a state of its own rather than
        `JobState.FAILED`, because nothing about the job was wrong.

        A queued job is left queued. It had not started, so nothing was lost and
        there is nothing to settle. An accepted job is left accepted for the same
        reason; the route that offers it to the queue is #27's, and re-admitting
        it here would be that decision made in the wrong place.
        """
        with self._transaction():
            rows = self._connection.execute(
                _SELECT_BY_STATE, (JobState.RUNNING,)
            ).fetchall()
            recovered = []
            for row in rows:
                current = self._record(row[0], row)
                check_transition(
                    current.state,
                    JobState.INTERRUPTED,
                    TerminalReason.INTERRUPTED_BY_SHUTDOWN,
                )
                self._connection.execute(
                    _UPDATE,
                    (
                        JobState.INTERRUPTED,
                        TerminalReason.INTERRUPTED_BY_SHUTDOWN,
                        current.job_id,
                    ),
                )
                recovered.append(
                    JobRecord(
                        current.job_id,
                        JobState.INTERRUPTED,
                        TerminalReason.INTERRUPTED_BY_SHUTDOWN,
                    )
                )
        return tuple(recovered)

    @contextlib.contextmanager
    def _transaction(self) -> Iterator[None]:
        """One write, committed or rolled back, never partly applied.

        ``BEGIN IMMEDIATE`` takes the write lock at the start rather than at the
        first write, so a transaction that reads a state and then writes it
        cannot have that state changed underneath it between the two.
        """
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")

    def _record(
        self, job_id: str, row: tuple[str, str, str | None] | None
    ) -> JobRecord:
        """A row as a `JobRecord`, refusing anything the state machine does not know."""
        if row is None:
            raise UnknownJobError(
                f"no job with identifier {job_id!r} is in this store. A caller "
                f"polling for a job it was told about is asking about a "
                f"different store or a job that was never accepted, and those "
                f"are different faults from a job that is merely unfinished."
            )
        _, raw_state, raw_reason = row
        try:
            state = JobState(raw_state)
        except ValueError as error:
            raise CorruptJobStoreError(_unknown(job_id, "state", raw_state)) from error
        reason: TerminalReason | None = None
        if raw_reason is not None:
            try:
                reason = TerminalReason(raw_reason)
            except ValueError as error:
                raise CorruptJobStoreError(
                    _unknown(job_id, "reason", raw_reason)
                ) from error
        problem = reason_problem(state, reason)
        if problem is not None:
            raise CorruptJobStoreError(
                f"the stored row for job {job_id!r} does not fit the state "
                f"machine: {problem}"
            )
        return JobRecord(job_id, state, reason)


def _unknown(job_id: str, field: str, raw: str) -> str:
    """What a stored value nothing declares is refused with."""
    return (
        f"the stored {field} {raw!r} for job {job_id!r} is not one this "
        f"project's state machine declares. The store file was written by "
        f"something other than this version, and reading the row would put a "
        f"job into a state nothing here can move it out of."
    )
