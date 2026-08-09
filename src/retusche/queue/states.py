# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The states a job moves through, and every move that is allowed.

One table, read by everything that moves a job. A state machine written as a
diagram in a document and re-implemented at each call site is not a state
machine: it is a description that each caller is free to disagree with, and the
disagreements are found one at a time by whoever is holding the job when it
lands in a state nothing expected.

So the table below is data, `check_transition` is the only thing that reads it,
and a move it does not permit raises rather than being written. Nothing here
touches a store: this module answers whether a move is legal, and
``retusche.queue.store`` is what makes one durable.

Terminal states carry a reason
------------------------------
A caller that has to tell a refused job from a broken one, or a cancellation
from a shutdown, needs something it can branch on. A message is prose, and prose
is what changes without anyone noticing, so the reason is an enumeration and the
set each terminal state may carry is declared beside the transitions. Entering a
terminal state without one is refused, and so is entering a running state with
one.

What this module deliberately does not decide
---------------------------------------------
Which state a job should move to, and when. Admission is #27, the memory refusal
is #30, cancellation is #29 and the shutdown path is #33. Each of those decides
a move; this decides whether the move it chose exists.

The table is also minimal rather than permissive. `INTERRUPTED` is reachable
only from `RUNNING`, because the one route that produces it is restart recovery,
which leaves a queued job queued. A shutdown that also wants to interrupt
queued work is #33's, and it adds the edge with its own reason rather than
finding it already open.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "LEGAL_TRANSITIONS",
    "REASONS",
    "TERMINAL_STATES",
    "IllegalTransitionError",
    "JobState",
    "JobStateError",
    "TerminalReason",
    "TerminalReasonError",
    "check_transition",
    "reason_problem",
]


class JobState(enum.StrEnum):
    """Where a job is. Stored as the string value, so a store file is readable."""

    ACCEPTED = "accepted"
    """Recorded and answerable, not yet offered to the queue. The state a caller
    is told about the moment the request is durable."""

    QUEUED = "queued"
    """Waiting for the lane. Admission has taken the job and not yet started
    it."""

    RUNNING = "running"
    """On the device. At most one job is in this state per lane, which is #27's
    rule rather than this table's."""

    SUCCEEDED = "succeeded"
    """Finished, with a result."""

    FAILED = "failed"
    """Finished without a result, for a reason inside the work."""

    CANCELLED = "cancelled"
    """Finished without a result because somebody asked for it to stop."""

    INTERRUPTED = "interrupted"
    """Finished without a result because the service stopped underneath it.

    Distinct from `FAILED` on purpose. Nothing was wrong with the job and
    nothing about it has been shown to be unrepeatable, so an operator reading a
    list of failures should not find yesterday's restart in it, and a caller
    deciding whether to resubmit is deciding a different question here."""


class TerminalReason(enum.StrEnum):
    """Why a job ended, as something a caller branches on rather than reads."""

    COMPLETED = "completed"
    """The edit was produced."""

    CANCELLED_BY_CALLER = "cancelled-by-caller"
    """Somebody asked for the job to stop before it produced a result."""

    REFUSED_UNSUPPORTED = "refused-unsupported"
    """No engine on this host does what the request asked for. Resubmitting it
    unchanged fails again, which is what separates this from the two below."""

    REFUSED_OVER_BUDGET = "refused-over-budget"
    """The job's estimated device memory exceeded the configured budget, so it
    was refused before admission rather than discovered during it."""

    OUT_OF_DEVICE_MEMORY = "out-of-device-memory"
    """The device could not allocate what the job needed despite the estimate.
    Separate from the refusal above because one is the budget working and the
    other is the estimate being wrong."""

    ENGINE_FAILURE = "engine-failure"
    """The engine broke for a reason it does not name more precisely."""

    INTERRUPTED_BY_SHUTDOWN = "interrupted-by-shutdown"
    """The service stopped while the job was on the device."""


REASONS: Final[Mapping[JobState, frozenset[TerminalReason]]] = {
    JobState.SUCCEEDED: frozenset({TerminalReason.COMPLETED}),
    JobState.FAILED: frozenset(
        {
            TerminalReason.REFUSED_UNSUPPORTED,
            TerminalReason.REFUSED_OVER_BUDGET,
            TerminalReason.OUT_OF_DEVICE_MEMORY,
            TerminalReason.ENGINE_FAILURE,
        }
    ),
    JobState.CANCELLED: frozenset({TerminalReason.CANCELLED_BY_CALLER}),
    JobState.INTERRUPTED: frozenset({TerminalReason.INTERRUPTED_BY_SHUTDOWN}),
}
"""The reasons each terminal state may carry.

Which states are terminal is derived from this rather than declared twice. A
second list would be a place for the two to disagree, and the disagreement would
be silent in exactly the direction that matters: a state treated as terminal by
one and not by the other.
"""

TERMINAL_STATES: Final = frozenset(REASONS)
"""The states nothing leaves."""

LEGAL_TRANSITIONS: Final[Mapping[JobState, frozenset[JobState]]] = {
    JobState.ACCEPTED: frozenset(
        {JobState.QUEUED, JobState.CANCELLED, JobState.FAILED}
    ),
    JobState.QUEUED: frozenset({JobState.RUNNING, JobState.CANCELLED, JobState.FAILED}),
    JobState.RUNNING: frozenset(
        {
            JobState.SUCCEEDED,
            JobState.FAILED,
            JobState.CANCELLED,
            JobState.INTERRUPTED,
        }
    ),
    JobState.SUCCEEDED: frozenset(),
    JobState.FAILED: frozenset(),
    JobState.CANCELLED: frozenset(),
    JobState.INTERRUPTED: frozenset(),
}
"""Every move a job may make, keyed by where it is now.

Each state has a row, terminal ones included, so a lookup here answers for every
state rather than raising on the states nobody thought about. An empty row and a
missing row read the same to a person and differently to the code, and the
difference is a `KeyError` from inside a store transaction.
"""


class JobStateError(Exception):
    """Base of the two refusals this module makes."""


class IllegalTransitionError(JobStateError):
    """The move is not in the table."""


class TerminalReasonError(JobStateError):
    """The move is in the table and the reason does not fit where it lands."""


def reason_problem(state: JobState, reason: TerminalReason | None) -> str | None:
    """What is wrong with carrying this reason into this state, or nothing.

    Written as a returned sentence rather than as a raise, because two callers
    need the same judgement for different purposes: `check_transition` refuses a
    move, and the store refuses a row it reads back out of a file somebody may
    have edited by hand.
    """
    permitted = REASONS.get(state)
    if permitted is None:
        if reason is None:
            return None
        return (
            f"{state} is not a terminal state, so nothing about it is final "
            f"enough to have a reason, and {reason} was given. A reason on a "
            f"job that is still moving is one a caller can read after the job "
            f"has moved on from the thing it describes."
        )
    if reason is None:
        return (
            f"{state} is terminal and every terminal state carries a reason a "
            f"caller can branch on without parsing text. One of "
            f"{_listed(permitted)} is expected."
        )
    if reason not in permitted:
        return (
            f"{reason} is not a reason {state} carries. The ones it does are "
            f"{_listed(permitted)}. A reason that does not belong to its state "
            f"is worse than none: a caller branching on it takes a path the "
            f"state does not support."
        )
    return None


def check_transition(
    current: JobState, target: JobState, reason: TerminalReason | None = None
) -> None:
    """Refuse a move that is not in the table, or a reason that does not fit.

    Returns nothing on a legal move. The caller then writes it; nothing here
    writes anything, so a store can ask this question inside its own transaction
    before it has decided to commit.
    """
    if target not in LEGAL_TRANSITIONS[current]:
        raise IllegalTransitionError(_transition_message(current, target))
    problem = reason_problem(target, reason)
    if problem is not None:
        raise TerminalReasonError(problem)


def _transition_message(current: JobState, target: JobState) -> str:
    """What a refused move is told. Names where it is and where it could go."""
    permitted = LEGAL_TRANSITIONS[current]
    if not permitted:
        return (
            f"a job in {current} does not move again: {current} is terminal and "
            f"{target} was asked for. A job that leaves a terminal state has "
            f"already been reported to a caller as finished, and the report "
            f"cannot be taken back."
        )
    return (
        f"{current} -> {target} is not a move this project makes. From "
        f"{current} a job goes to {_listed(permitted)}. The table is "
        f"LEGAL_TRANSITIONS in retusche.queue.states, and a move that ought to "
        f"exist is added there rather than around here."
    )


def _listed(states: frozenset[JobState] | frozenset[TerminalReason]) -> str:
    """Sorted and comma-joined, so one message reads the same on every run."""
    return ", ".join(sorted(str(entry) for entry in states))
