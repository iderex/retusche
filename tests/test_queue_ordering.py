# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The ordering rule, and the bound held under a workload that starves.

The starvation test is the one this file exists for, and it is written against
the implementation that would otherwise ship. A test showing that a background
job eventually runs proves nothing: strict priority passes it whenever the
interactive supply happens to dry up. So the supply here never dries up. Both
kinds of work are replaced the moment one starts, which is the shape of a host
that is busy all day, and under strict priority no background job ever starts at
all.

The other tests are the ones an ordering rule loses quietly: arrival order
inside a priority, a tie-break that does not depend on the order a set came out
in, and the counter that carries the bound between two calls.

The budget composition at the bottom is the fourth line of the issue rather than
a test of the budget. What it holds is that a job at the front of the queue
which cannot start is passed over and stays waiting, so priority decides the
order the question is asked in and never whether it is asked.

No device, no display and no elevation is needed by anything in this file.
"""

from __future__ import annotations

from retusche.queue.budget import DeviceMemoryBudget, Fit, fits
from retusche.queue.ordering import (
    INTERACTIVE_BEFORE_BACKGROUND,
    NO_WAIT_ESTIMATE,
    Priority,
    Waiting,
    interactive_run_after,
    next_to_start,
    order,
    position_of,
)
from retusche.testing.fake_engine import FakeEngine, Script
from retusche_contracts.engine import JobDescription, Operation

_JOB = JobDescription(
    operation=Operation.ERASE,
    width=512,
    height=512,
    has_prompt=False,
    steps=1,
)


def _interactive(job_id: str, arrival: int) -> Waiting:
    return Waiting(job_id=job_id, priority=Priority.INTERACTIVE, arrival=arrival)


def _background(job_id: str, arrival: int) -> Waiting:
    return Waiting(job_id=job_id, priority=Priority.BACKGROUND, arrival=arrival)


def _run(
    waiting: list[Waiting],
    steps: int,
    *,
    limit: int,
    refill: bool,
    next_arrival: int,
) -> list[Waiting]:
    """Start ``steps`` jobs and return them in the sequence they started.

    ``limit`` is the starvation bound the run is driven with, so the same
    simulation can be given the shipped bound and given a bound of infinity,
    which is strict priority and is the implementation this file is written
    against. Where ``refill`` is set, a job that starts is replaced by another
    of the same kind, so neither supply ever runs out.
    """
    started: list[Waiting] = []
    interactive_run = 0
    arrival = next_arrival
    for _ in range(steps):
        ordered = order(waiting, interactive_run if limit else 0)
        chosen = next_to_start(ordered, lambda _job: True)
        if chosen is None:
            break
        waiting.remove(chosen)
        started.append(chosen)
        interactive_run = interactive_run_after(chosen, interactive_run)
        if refill:
            waiting.append(
                Waiting(
                    job_id=f"{chosen.priority.value}-{arrival}",
                    priority=chosen.priority,
                    arrival=arrival,
                )
            )
            arrival += 1
    return started


def _longest_interactive_run(started: list[Waiting]) -> int:
    longest = 0
    current = 0
    for job in started:
        if job.priority is Priority.INTERACTIVE:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def test_interactive_work_is_considered_before_background_work() -> None:
    """The whole reason a priority exists, and it holds on an idle counter."""
    ordered = order([_background("b", 1), _interactive("i", 2)])
    assert [job.job_id for job in ordered] == ["i", "b"]


def test_within_one_priority_the_order_is_arrival_order() -> None:
    """First in, first out, and neither the input order nor the name decides it.

    The identifiers run backwards against the arrivals on purpose. Named so that
    the two agree, this test passes with ``arrival`` taken out of the sort key
    altogether, which is a first-in-first-out test that would let a queue order
    by identifier and never notice. That was measured rather than supposed: the
    fixture read `first`, `second`, `third` and the mutation dropping ``arrival``
    left the whole suite green.
    """
    ordered = order(
        [_interactive("alpha", 3), _interactive("zulu", 1), _interactive("mike", 2)]
    )
    assert [job.job_id for job in ordered] == ["zulu", "mike", "alpha"]


def test_two_jobs_sharing_an_arrival_ordinal_order_by_identifier() -> None:
    """The tie-break, which nothing guarantees will never be needed.

    Whatever allocates arrival ordinals is not in this tree, so an ordering that
    is deterministic only while they are distinct is one that reorders itself
    the first time they are not.
    """
    forwards = order([_interactive("b", 7), _interactive("a", 7)])
    backwards = order([_interactive("a", 7), _interactive("b", 7)])
    assert [job.job_id for job in forwards] == ["a", "b"]
    assert [job.job_id for job in backwards] == ["a", "b"]


def test_the_bound_promotes_the_oldest_background_job_and_nothing_else() -> None:
    """One job moves to the front. The rest keep the order they had."""
    waiting = [
        _interactive("i1", 1),
        _interactive("i2", 2),
        _background("b1", 3),
        _background("b2", 4),
    ]
    ordered = order(waiting, INTERACTIVE_BEFORE_BACKGROUND)
    assert [job.job_id for job in ordered] == ["b1", "i1", "i2", "b2"]


def test_a_spent_run_with_no_background_work_changes_nothing() -> None:
    """There is nothing to promote, so the interactive order stands."""
    ordered = order(
        [_interactive("i2", 2), _interactive("i1", 1)], INTERACTIVE_BEFORE_BACKGROUND
    )
    assert [job.job_id for job in ordered] == ["i1", "i2"]


def test_background_work_starts_under_a_workload_that_would_starve_it() -> None:
    """The starvation bound, against a supply that never runs out.

    Every job that starts is replaced by another of its kind, so an interactive
    job is always waiting. Strict priority starts no background job in any
    number of steps under this workload, which is what the second half asserts
    by running the same simulation with the bound switched off.
    """
    waiting = [_interactive("i0", 0), _background("b0", 1)]
    started = _run(
        list(waiting),
        60,
        limit=INTERACTIVE_BEFORE_BACKGROUND,
        refill=True,
        next_arrival=2,
    )
    background_starts = [job for job in started if job.priority is Priority.BACKGROUND]
    assert background_starts
    assert _longest_interactive_run(started) <= INTERACTIVE_BEFORE_BACKGROUND

    starved = _run(list(waiting), 60, limit=0, refill=True, next_arrival=2)
    assert not [job for job in starved if job.priority is Priority.BACKGROUND]
    assert _longest_interactive_run(starved) == 60


def test_one_background_job_starts_within_the_stated_number_of_starts() -> None:
    """The bound as an operator would read it, for the single-job case."""
    waiting = [_background("b0", 0), _interactive("i0", 1)]
    started = _run(
        list(waiting),
        20,
        limit=INTERACTIVE_BEFORE_BACKGROUND,
        refill=True,
        next_arrival=2,
    )
    ahead = started[: [job.job_id for job in started].index("b0")]
    assert len(ahead) <= INTERACTIVE_BEFORE_BACKGROUND
    assert all(job.priority is Priority.INTERACTIVE for job in ahead)


def test_background_jobs_start_in_their_own_arrival_order() -> None:
    """Three of them behind an endless stream, each taking its turn.

    The bound moves one job at a time and it is always the oldest, so three
    background jobs behind a busy host start in the order they arrived and each
    waits its own multiple of the bound. That is the reading the module
    docstring states, and this is where it is held.
    """
    waiting = [
        _background("zulu", 1),
        _background("mike", 2),
        _background("alpha", 3),
        _interactive("i0", 4),
    ]
    started = _run(
        list(waiting),
        40,
        limit=INTERACTIVE_BEFORE_BACKGROUND,
        refill=True,
        next_arrival=5,
    )
    order_of_background = [
        job.job_id for job in started if job.priority is Priority.BACKGROUND
    ]
    assert order_of_background[:3] == ["zulu", "mike", "alpha"]


def test_the_counter_lengthens_on_interactive_and_resets_on_background() -> None:
    """One line of arithmetic, and the bound is gone if it is wrong."""
    assert interactive_run_after(_interactive("i", 1), 0) == 1
    assert interactive_run_after(_interactive("i", 1), 3) == 4
    assert interactive_run_after(_background("b", 1), 4) == 0
    assert interactive_run_after(_background("b", 1), 0) == 0


def test_a_job_that_cannot_start_is_passed_over_and_stays_waiting() -> None:
    """Priority decides the order the question is asked in, never whether.

    The interactive job is first and does not fit what is free. The background
    job behind it does. The interactive job is not started and it is still in
    the queue afterwards, which is the difference between passing over a job and
    dropping one.
    """
    engine = FakeEngine(Script(device_memory_bytes=3_000))
    small = FakeEngine(Script(device_memory_bytes=100))
    budget = DeviceMemoryBudget(total_bytes=4_096, resident_bytes=2_048)
    estimates = {
        "i0": engine.estimate_device_memory(_JOB),
        "b0": small.estimate_device_memory(_JOB),
    }

    def can_start(job: Waiting) -> bool:
        return fits(_JOB, estimates[job.job_id], budget) is Fit.NOW

    waiting = [_interactive("i0", 1), _background("b0", 2)]
    ordered = order(waiting)
    assert [job.job_id for job in ordered] == ["i0", "b0"]
    chosen = next_to_start(ordered, can_start)
    assert chosen is not None
    assert chosen.job_id == "b0"
    assert "i0" in [job.job_id for job in waiting]


def test_nothing_starts_when_nothing_can() -> None:
    """An empty answer rather than the first job regardless."""
    ordered = order([_interactive("i0", 1)])
    assert next_to_start(ordered, lambda _job: False) is None


def test_a_position_names_what_is_ahead_and_how_many_are_waiting() -> None:
    """What a caller polling for a job is told about where it sits."""
    ordered = order([_interactive("i1", 1), _interactive("i2", 2), _background("b", 3)])
    position = position_of("b", ordered)
    assert position is not None
    assert position.ahead == 2
    assert position.total_waiting == 3


def test_a_job_that_is_not_waiting_has_no_position() -> None:
    """Nothing rather than zero, which is where the front of the queue is."""
    assert position_of("gone", order([_interactive("i1", 1)])) is None


def test_no_wait_is_estimated_and_the_absence_is_written_out() -> None:
    """The line offers an estimate or a plain statement that there is none.

    This is the second, so the sentence has to exist and the field has to be
    empty. A caller that displays one without the other is displaying a blank
    where an operator expects a number.
    """
    position = position_of("i1", order([_interactive("i1", 1)]))
    assert position is not None
    assert position.wait_estimate is None
    assert "No wait is estimated" in NO_WAIT_ESTIMATE
