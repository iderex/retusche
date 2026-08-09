# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Which waiting job is considered next, and the bound that stops one waiting
forever.

An operator standing in front of a screen waiting for one object to disappear
should not be behind a library sweep that queued four hundred edits. A priority
is the obvious answer, and strict priority is the obvious way to build a queue
in which the sweep never finishes: while any interactive job is waiting, no
background job ever starts, and on a busy host that condition is permanent.

So the rule here is priority with a bound written into it, and the bound is a
number rather than an intention:

    while a background job is waiting, at most INTERACTIVE_BEFORE_BACKGROUND
    interactive jobs start in a row

`order` implements that and `tests/test_queue_ordering.py` asserts it under a
workload that starves a strict-priority queue outright.

What the bound is and is not
----------------------------
It bounds a RUN of interactive starts, not the wait of any particular job. One
background job waiting behind an endless interactive stream starts after at most
`INTERACTIVE_BEFORE_BACKGROUND` interactive starts. Three background jobs
waiting behind the same stream start after at most that many each, in their own
arrival order, so the third waits three times as long. That is the honest
reading and it is the one the tests hold; a sentence promising every background
job a fixed wait would be false the moment two of them queue.

Four is the number, and it is a choice rather than a measurement. Nothing in
this tree has measured how long a job takes, so a bound argued from a target
latency would be arithmetic over an invented duration. What can be argued
without a measurement is the shape: the number is small enough that a background
sweep makes progress on a host that is busy all day, and large enough that an
interactive job is not routinely put behind a background one. Where a
measurement arrives, in #85, it is what moves this.

Nothing here is stateful
------------------------
`order` is a function of the waiting set and one counter the caller keeps: how
many interactive jobs have started since the last background job did. Keeping
that counter here would mean this module owned a lifecycle, and the thing that
starts jobs is the lane in #27. The counter is one integer and
`interactive_run_after` says how it moves, so the caller cannot get it wrong by
inventing its own rule.

What this module does not decide
--------------------------------
Whether a job may start at all. That is the budget in `retusche.queue.budget`
and the lane in #27, and `next_to_start` takes them as a predicate rather than
importing either. Priority decides the ORDER in which the question is asked and
never whether it is asked, which is what stops a high-priority job walking past
the memory budget: it is offered first and refused like anything else, and it
goes on waiting.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

__all__ = [
    "INTERACTIVE_BEFORE_BACKGROUND",
    "NO_WAIT_ESTIMATE",
    "Priority",
    "QueuePosition",
    "Waiting",
    "interactive_run_after",
    "next_to_start",
    "order",
    "position_of",
]


class Priority(enum.StrEnum):
    """What kind of work a job is, as far as ordering is concerned.

    Two values and not a number. A numeric priority invites a caller to ask for
    one higher than everyone else's, and then the number says nothing except who
    asked hardest. These two are a statement about the work: somebody is waiting
    for the result, or nobody is.
    """

    INTERACTIVE = "interactive"
    """Somebody is in front of a screen waiting for this."""

    BACKGROUND = "background"
    """Nobody is waiting. A library sweep, a batch, a re-run."""


_RANK: Final[Mapping[Priority, int]] = {
    Priority.INTERACTIVE: 0,
    Priority.BACKGROUND: 1,
}
"""The order the priorities are considered in, lowest first.

A mapping rather than the declaration order of the enumeration, because
reordering members of an enumeration is a cosmetic change that would silently
reverse the queue.
"""

INTERACTIVE_BEFORE_BACKGROUND: Final = 4
"""How many interactive jobs may start in a row while background work waits.

The starvation bound. See the module docstring for what it does and does not
promise, and for why it is a choice rather than a measured number.
"""

NO_WAIT_ESTIMATE: Final = (
    "No wait is estimated. Estimating one needs how long a job takes, which "
    "needs an engine and a measurement on this host, and neither exists yet; "
    "and the queue ahead of a background job grows whenever interactive work "
    "arrives, so even a per-job duration would not bound it. The position "
    "below is the order in force at the moment it was asked and it moves."
)
"""What is reported in place of an expected wait.

The line this answers offers a choice between reporting an expected wait and
saying plainly that one cannot be estimated. This is the second, and it is
written out rather than left as an omission so that a caller displaying a
position has something to display beside it instead of a blank.
"""


@dataclass(frozen=True, slots=True)
class Waiting:
    """One job in the queue, as ordering sees it.

    Not the job record. `retusche.queue.store` holds what a job is; this is the
    three things the order is decided from, so that ordering can be exercised
    without a store and a store can change without moving this.
    """

    job_id: str
    """Which job. Also the tie-break, so two jobs never order at random."""

    priority: Priority
    """Which of the two kinds of work this is."""

    arrival: int
    """When it joined the queue, as an ordinal rather than a clock reading.

    A clock goes backwards on a host that adjusts it, and two jobs accepted in
    the same millisecond read as simultaneous. An ordinal does neither. Nothing
    here allocates one; whatever accepts a job does, and where that is written
    down durably is #27's, not this module's.
    """


@dataclass(frozen=True, slots=True)
class QueuePosition:
    """Where a job sits in the order that is in force right now."""

    job_id: str
    ahead: int
    """How many waiting jobs are considered before this one."""

    total_waiting: int
    """How many jobs are waiting in all, this one included."""

    wait_estimate: None = None
    """Always nothing, and the field is here so the absence is declared.

    A caller reading a position wants to know whether a wait is being withheld
    or simply not offered. `NO_WAIT_ESTIMATE` is the sentence that says which,
    and the day an estimate exists this field is where it goes.
    """


def order(waiting: Iterable[Waiting], interactive_run: int = 0) -> tuple[Waiting, ...]:
    """The waiting jobs, in the order they are to be considered.

    Interactive work first, then background, each in arrival order with the job
    identifier as the tie-break, so the same waiting set always produces the
    same sequence.

    ``interactive_run`` is how many interactive jobs have started since the last
    background job started. Once it reaches `INTERACTIVE_BEFORE_BACKGROUND` and
    background work is waiting, the oldest background job is moved to the front,
    which is the whole of the starvation bound. It moves one job and not the
    whole class: the interactive work behind it keeps its own order.
    """
    ranked = sorted(waiting, key=_sort_key)
    if interactive_run < INTERACTIVE_BEFORE_BACKGROUND:
        return tuple(ranked)
    promoted = next(
        (
            candidate
            for candidate in ranked
            if candidate.priority is Priority.BACKGROUND
        ),
        None,
    )
    if promoted is None:
        return tuple(ranked)
    return (promoted, *(job for job in ranked if job is not promoted))


def next_to_start(
    ordered: Sequence[Waiting], can_start: Callable[[Waiting], bool]
) -> Waiting | None:
    """The first job in the order the caller says can start, or nothing.

    ``can_start`` is where the device memory budget and the lane are consulted.
    They are a predicate rather than an import because this module decides the
    order in which the question is asked and must not be able to skip asking it:
    a job at the front that cannot start is passed over here and stays in the
    queue, and the one behind it is asked the same question rather than
    inheriting the answer.
    """
    return next((candidate for candidate in ordered if can_start(candidate)), None)


def interactive_run_after(started: Waiting, interactive_run: int) -> int:
    """The counter to pass to the next `order`, given what just started.

    An interactive start lengthens the run and a background start ends it. The
    arithmetic is one line and it is here rather than at the call site because a
    caller that resets it on the wrong branch removes the bound while every test
    of the ordering itself stays green.
    """
    if started.priority is Priority.BACKGROUND:
        return 0
    return interactive_run + 1


def position_of(job_id: str, ordered: Sequence[Waiting]) -> QueuePosition | None:
    """Where ``job_id`` sits in ``ordered``, or nothing if it is not waiting.

    Nothing rather than a position of zero, because a job that has already
    started and a job at the front of the queue are different answers and a
    caller polling for one must not read them as the same.
    """
    for index, candidate in enumerate(ordered):
        if candidate.job_id == job_id:
            return QueuePosition(job_id=job_id, ahead=index, total_waiting=len(ordered))
    return None


def _sort_key(job: Waiting) -> tuple[int, int, str]:
    """Priority, then arrival, then the identifier.

    The identifier is last so that two jobs sharing an arrival ordinal still
    order the same way on every run and on every host. Nothing guarantees the
    ordinals are unique: whatever allocates them is not in this tree, and an
    ordering that is only deterministic while they happen to be distinct is one
    that reorders itself the first time they are not.
    """
    return (_RANK[job.priority], job.arrival, job.job_id)
