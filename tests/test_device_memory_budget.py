# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The budget refusal, driven against a scripted engine and a stubbed ceiling.

Every estimate here comes out of `FakeEngine`, never out of a literal handed
straight to `check_fits`. A test that invents both sides of the comparison
proves that a greater-than sign works. Driving the estimate through the contract
proves that the number the queue would actually be holding is the number that
gets compared, and the fake carries `device_memory_bytes` for exactly this.

The near misses are the point of the file. Three of them, each the mistake
somebody writes rather than an obvious violation:

- an estimate equal to the room left, which a `>=` refuses and a `>` admits
- one byte over, which is the same comparison from the other side
- an estimate that fits the whole budget while resident weights are holding part
  of it, which passes any implementation that compares against `total_bytes`

No device, no display and no elevation is needed by anything in this file.
"""

from __future__ import annotations

import pytest

from retusche.queue.budget import (
    DeviceMemoryBudget,
    InvalidBudgetError,
    OverBudgetError,
    check_fits,
    estimation_defect,
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


def test_a_job_that_fits_is_not_refused() -> None:
    """The whole of the room left is available, so a job inside it passes."""
    check_fits(_JOB, _estimate_of(1_000), DeviceMemoryBudget(total_bytes=4_096))


def test_an_estimate_equal_to_the_room_left_fits() -> None:
    """The boundary, from the side that must pass.

    `DeviceMemoryEstimate.peak_bytes` is documented as an upper bound the engine
    is willing to be held to, so a job needing exactly what is there is a job
    the budget was set for. An implementation written with `>=` refuses it and
    nothing else in this file would notice.
    """
    check_fits(_JOB, _estimate_of(4_096), DeviceMemoryBudget(total_bytes=4_096))


def test_one_byte_over_the_room_left_is_refused() -> None:
    """The same boundary from the side that must fail."""
    with pytest.raises(OverBudgetError):
        check_fits(_JOB, _estimate_of(4_097), DeviceMemoryBudget(total_bytes=4_096))


def test_resident_weights_take_room_from_the_next_job() -> None:
    """The near miss for a comparison written against the whole budget.

    The same estimate fits the budget and does not fit what is left of it once a
    model is loaded. An implementation that compares against ``total_bytes``
    passes every other test in this file and fails here, which is the reading
    the issue asks for: a loaded model reduces the room rather than being
    invisible.
    """
    estimate = _estimate_of(3_000)
    check_fits(_JOB, estimate, DeviceMemoryBudget(total_bytes=4_096))
    with pytest.raises(OverBudgetError):
        check_fits(
            _JOB,
            estimate,
            DeviceMemoryBudget(total_bytes=4_096, resident_bytes=2_048),
        )


def test_the_refusal_names_both_numbers_and_the_shape_refused() -> None:
    """A caller branches on the type; the operator reads the sentence."""
    budget = DeviceMemoryBudget(total_bytes=4_096, resident_bytes=1_024)
    estimate = _estimate_of(9_000)
    with pytest.raises(OverBudgetError) as refusal:
        check_fits(_JOB, estimate, budget)
    message = str(refusal.value)
    assert "9000" in message
    assert "3072" in message
    assert "4096" in message
    assert "1024" in message
    assert "1024 by 768 erase" in message
    assert "not measured" in message


def test_the_refusal_carries_what_it_refused_rather_than_only_a_sentence() -> None:
    """The three values a caller would otherwise have to parse back out."""
    budget = DeviceMemoryBudget(total_bytes=64)
    estimate = _estimate_of(128)
    with pytest.raises(OverBudgetError) as refusal:
        check_fits(_JOB, estimate, budget)
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
        check_fits(
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
