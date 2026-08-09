# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The budget refusal, driven against a scripted engine and a stubbed ceiling.

Every estimate here comes out of `FakeEngine`, never out of a literal handed
straight to `fits`. A test that invents both sides of the comparison
proves that a greater-than sign works. Driving the estimate through the contract
proves that the number the queue would actually be holding is the number that
gets compared, and the fake carries `device_memory_bytes` for exactly this.

The near misses are the point of the file, and each is the mistake somebody
writes rather than an obvious violation:

- an estimate equal to the room available, which a `>=` sends away and a `>`
  admits, asserted at both of the two boundaries this module has
- one byte over the budget, which is the same comparison from the other side
- an estimate that fits the whole budget while resident weights are holding part
  of it, which one wrong implementation refuses outright and another sends
  straight to a lane, and which is neither

No device, no display and no elevation is needed by anything in this file.
"""

from __future__ import annotations

import pytest

from retusche.queue.budget import (
    DeviceMemoryBudget,
    Fit,
    InvalidBudgetError,
    OverBudgetError,
    estimation_defect,
    fits,
)
from retusche.queue.states import (
    JobState,
    TerminalReason,
    check_transition,
)
from retusche.testing.fake_engine import FakeEngine, Script
from retusche_contracts.engine import (
    DeviceMemoryEstimate,
    JobDescription,
    Operation,
)

_JOB = JobDescription(
    operation=Operation.ERASE,
    width=1024,
    height=768,
    has_prompt=False,
    steps=1,
)


def _estimate_of(peak: int, *, measured: bool = False) -> DeviceMemoryEstimate:
    """What an engine answers when it is scripted to need ``peak`` bytes."""
    engine = FakeEngine(Script(device_memory_bytes=peak, estimate_is_measured=measured))
    return engine.estimate_device_memory(_JOB)


def test_a_job_inside_what_is_free_may_go_to_a_lane() -> None:
    """The whole of the room left is available, so a job inside it runs now."""
    assert (
        fits(_JOB, _estimate_of(1_000), DeviceMemoryBudget(total_bytes=4_096))
        is Fit.NOW
    )


def test_an_estimate_equal_to_what_is_free_runs_now() -> None:
    """The first boundary, from the side that must pass.

    `DeviceMemoryEstimate.peak_bytes` is documented as an upper bound the engine
    is willing to be held to, so a job needing exactly what is there is a job
    the budget was set for. An implementation written with `>=` sends it away to
    wait instead, and nothing else in this file would notice.
    """
    assert (
        fits(_JOB, _estimate_of(4_096), DeviceMemoryBudget(total_bytes=4_096))
        is Fit.NOW
    )


def test_an_estimate_equal_to_the_whole_budget_is_not_refused() -> None:
    """The second boundary, from the side that must pass.

    A job needing the entire budget is a job the budget permits. It waits here
    only because a byte of weights is resident, and `>=` at this comparison
    would end it instead, which is a job thrown away by an off-by-one.
    """
    assert (
        fits(
            _JOB,
            _estimate_of(4_096),
            DeviceMemoryBudget(total_bytes=4_096, resident_bytes=1),
        )
        is Fit.WHEN_ROOM_IS_FREED
    )


def test_one_byte_over_the_whole_budget_is_refused() -> None:
    """The second boundary from the side that must fail: nothing frees this."""
    with pytest.raises(OverBudgetError):
        fits(_JOB, _estimate_of(4_097), DeviceMemoryBudget(total_bytes=4_096))


def test_resident_weights_take_room_from_the_next_job() -> None:
    """The near miss for a comparison written against the whole budget.

    The same estimate runs now against an idle budget and has to wait once a
    model is loaded. An implementation that compares against ``total_bytes``
    alone sends it to a lane it does not fit in, which is the failure the whole
    module exists against, and it passes every other test here.
    """
    estimate = _estimate_of(3_000)
    assert fits(_JOB, estimate, DeviceMemoryBudget(total_bytes=4_096)) is Fit.NOW
    assert (
        fits(
            _JOB,
            estimate,
            DeviceMemoryBudget(total_bytes=4_096, resident_bytes=2_048),
        )
        is Fit.WHEN_ROOM_IS_FREED
    )


def test_a_job_that_only_has_to_wait_is_not_ended() -> None:
    """The correction this file exists to hold, stated on its own.

    A job that exceeds what is free and not the budget was refused here with
    `REFUSED_OVER_BUDGET`, which ends it. It fits as soon as the weights it did
    not fit beside are released, so ending it throws away a job that would have
    run, and a caller cannot tell that refusal from one it deserved.
    """
    budget = DeviceMemoryBudget(total_bytes=8_192, resident_bytes=6_000)
    assert fits(_JOB, _estimate_of(4_000), budget) is Fit.WHEN_ROOM_IS_FREED


def test_the_refusal_names_both_numbers_and_the_shape_refused() -> None:
    """A caller branches on the type; the operator reads the sentence."""
    budget = DeviceMemoryBudget(total_bytes=4_096, resident_bytes=1_024)
    estimate = _estimate_of(9_000)
    with pytest.raises(OverBudgetError) as refusal:
        fits(_JOB, estimate, budget)
    message = str(refusal.value)
    assert "9000" in message
    assert "4096" in message
    assert "1024 by 768 erase" in message
    assert "not measured" in message
    assert "No eviction makes room for it" in message


def test_the_refusal_carries_what_it_refused_rather_than_only_a_sentence() -> None:
    """The three values a caller would otherwise have to parse back out."""
    budget = DeviceMemoryBudget(total_bytes=64)
    estimate = _estimate_of(128)
    with pytest.raises(OverBudgetError) as refusal:
        fits(_JOB, estimate, budget)
    assert refusal.value.job is _JOB
    assert refusal.value.estimate == estimate
    assert refusal.value.budget == budget


def test_the_refusal_reason_is_one_the_state_table_accepts() -> None:
    """The refusal and the state machine agree about where a refused job lands.

    `OverBudgetError.terminal_reason` is only useful if the move it names is a
    move that exists. This asserts the pair rather than the constant, so a
    reason renamed on one side without the other goes red here.
    """
    assert OverBudgetError.terminal_reason is TerminalReason.REFUSED_OVER_BUDGET
    check_transition(JobState.QUEUED, JobState.FAILED, OverBudgetError.terminal_reason)


def test_a_measured_estimate_says_so_in_the_refusal() -> None:
    """An operator deciding whether to distrust the estimate needs to know."""
    with pytest.raises(OverBudgetError) as refusal:
        fits(
            _JOB,
            _estimate_of(9_000, measured=True),
            DeviceMemoryBudget(total_bytes=4_096),
        )
    assert "(measured)" in str(refusal.value)


@pytest.mark.parametrize("total", [0, -1])
def test_a_budget_that_is_not_a_positive_amount_is_refused(total: int) -> None:
    """Refused where the number arrives, not on the first job of the day."""
    with pytest.raises(InvalidBudgetError) as refusal:
        DeviceMemoryBudget(total_bytes=total)
    assert str(total) in str(refusal.value)


def test_a_negative_resident_figure_is_refused() -> None:
    """It would make the room larger than the budget, which is the one
    direction this comparison must never be wrong in."""
    with pytest.raises(InvalidBudgetError) as refusal:
        DeviceMemoryBudget(total_bytes=4_096, resident_bytes=-1)
    assert "-1" in str(refusal.value)


def test_resident_weights_exceeding_the_budget_are_refused() -> None:
    """Either an eviction that did not happen or a budget lowered under a
    loaded model, and neither is a state a comparison can be made in."""
    with pytest.raises(InvalidBudgetError) as refusal:
        DeviceMemoryBudget(total_bytes=4_096, resident_bytes=4_097)
    assert "4097" in str(refusal.value)


def test_the_free_figure_is_the_budget_less_what_is_resident() -> None:
    """The one arithmetic every refusal above is decided by."""
    assert DeviceMemoryBudget(total_bytes=4_096).free_bytes == 4_096
    assert (
        DeviceMemoryBudget(total_bytes=4_096, resident_bytes=1_096).free_bytes == 3_000
    )


def test_an_overrun_is_recorded_with_the_shape_the_estimate_was_made_from() -> None:
    """The record exists so the estimate can be corrected, not so the failure
    can be counted, and what corrects it is the shape rather than the failure."""
    budget = DeviceMemoryBudget(total_bytes=4_096, resident_bytes=1_024)
    estimate = _estimate_of(2_000)
    defect = estimation_defect(_JOB, estimate, budget)
    assert defect.job is _JOB
    assert defect.estimate == estimate
    assert defect.budget == budget
    message = defect.message
    assert "1024 by 768 erase" in message
    assert "2000" in message
    assert "3072" in message
    assert "4096" in message


def test_the_overrun_record_says_whether_the_estimate_was_measured() -> None:
    """A measured estimate that was wrong is a different finding from a
    derived one that was wrong, and the record has to keep them apart."""
    budget = DeviceMemoryBudget(total_bytes=4_096)
    derived = estimation_defect(_JOB, _estimate_of(2_000), budget)
    measured = estimation_defect(_JOB, _estimate_of(2_000, measured=True), budget)
    assert "not measured" in derived.message
    assert "(measured)" in measured.message
