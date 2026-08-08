# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Every move the table declares, and every move it does not.

The Done-when this file answers asks for tests over every legal transition and
at least one attempt at each illegal one. What is written instead is the whole
cartesian product of the states with themselves: each pair is legal or it is
not, and the table is the only thing that says which. A test enumerating the
legal moves by hand would be a second copy of the table, agreeing with the first
because the same person wrote both.

That is also what makes this stronger than the bullet asks. An edge added to
`LEGAL_TRANSITIONS` without a reason to exist is not caught here, because the
table is the authority. An edge removed from it is, and so is an operator that
stops consulting it: the illegal half of the product is thirty-nine pairs, and the
refusal has to happen for every one of them.

No device, no display and no elevation is needed by anything in this file.
"""

from __future__ import annotations

import itertools

import pytest

from retusche.queue.states import (
    LEGAL_TRANSITIONS,
    REASONS,
    TERMINAL_STATES,
    IllegalTransitionError,
    JobState,
    TerminalReason,
    TerminalReasonError,
    check_transition,
    reason_problem,
)

_ALL_PAIRS = sorted(itertools.product(JobState, JobState))
_LEGAL_PAIRS = [(a, b) for a, b in _ALL_PAIRS if b in LEGAL_TRANSITIONS[a]]
_ILLEGAL_PAIRS = [(a, b) for a, b in _ALL_PAIRS if b not in LEGAL_TRANSITIONS[a]]


def _a_reason_for(state: JobState) -> TerminalReason | None:
    """One reason that fits ``state``, or nothing where the state takes none."""
    permitted = REASONS.get(state)
    if permitted is None:
        return None
    return sorted(permitted)[0]


@pytest.mark.parametrize(("current", "target"), _LEGAL_PAIRS)
def test_a_declared_move_is_permitted(current: JobState, target: JobState) -> None:
    """Every pair in the table passes, carrying the reason its target requires."""
    check_transition(current, target, _a_reason_for(target))


@pytest.mark.parametrize(("current", "target"), _ILLEGAL_PAIRS)
def test_a_move_outside_the_table_is_refused(
    current: JobState, target: JobState
) -> None:
    """Every pair the table does not hold raises, reason or no reason.

    Both spellings are tried because a check that consulted the reason first
    would let an undeclared move through whenever the reason happened to fit,
    and that is the shape a refusal quietly loses.
    """
    for reason in (None, _a_reason_for(target)):
        with pytest.raises(IllegalTransitionError) as refused:
            check_transition(current, target, reason)
        assert str(current) in str(refused.value)
        assert str(target) in str(refused.value)


def test_the_illegal_half_is_not_empty() -> None:
    """The parametrisation above is derived, so this says it derived something.

    A table that permitted everything would give the test above nothing to run
    and it would pass by having no cases, which reads in a report exactly like a
    table that refused all thirty-nine.
    """
    assert len(_ALL_PAIRS) == len(JobState) ** 2
    assert len(_ILLEGAL_PAIRS) == 39
    assert len(_LEGAL_PAIRS) == 10


@pytest.mark.parametrize("state", sorted(TERMINAL_STATES))
def test_a_terminal_state_is_left_by_nothing(state: JobState) -> None:
    """No row of the table lets a finished job move again."""
    assert LEGAL_TRANSITIONS[state] == frozenset()


def test_the_terminal_states_are_the_ones_that_carry_reasons() -> None:
    """One list, derived, so the two cannot drift into disagreeing."""
    assert frozenset(REASONS) == TERMINAL_STATES
    assert JobState.INTERRUPTED in TERMINAL_STATES
    assert JobState.FAILED in TERMINAL_STATES


def test_shutdown_is_a_state_of_its_own_and_not_a_failure() -> None:
    """The bullet asking for a state distinct from failed, stated as a test."""
    assert JobState.INTERRUPTED is not JobState.FAILED
    assert REASONS[JobState.INTERRUPTED] == frozenset(
        {TerminalReason.INTERRUPTED_BY_SHUTDOWN}
    )
    assert TerminalReason.INTERRUPTED_BY_SHUTDOWN not in REASONS[JobState.FAILED]


@pytest.mark.parametrize("state", sorted(TERMINAL_STATES))
def test_a_terminal_state_without_a_reason_is_refused(state: JobState) -> None:
    """A caller branching on the outcome has something to branch on, always."""
    with pytest.raises(TerminalReasonError) as refused:
        check_transition(JobState.RUNNING, state)
    assert "carries a reason" in str(refused.value)


@pytest.mark.parametrize("state", sorted(TERMINAL_STATES))
def test_a_reason_from_another_state_is_refused(state: JobState) -> None:
    """A reason has to belong to the state it lands in, not merely exist."""
    foreign = sorted(set(TerminalReason) - REASONS[state])[0]
    with pytest.raises(TerminalReasonError) as refused:
        check_transition(JobState.RUNNING, state, foreign)
    assert str(foreign) in str(refused.value)


def test_a_reason_on_a_state_that_is_still_moving_is_refused() -> None:
    """A job that is still going has no outcome yet, so it carries none."""
    with pytest.raises(TerminalReasonError) as refused:
        check_transition(JobState.ACCEPTED, JobState.QUEUED, TerminalReason.COMPLETED)
    assert "not a terminal state" in str(refused.value)


def test_a_move_into_a_running_state_needs_no_reason() -> None:
    """The other half of the rule above, so it is a rule and not a rejection."""
    check_transition(JobState.QUEUED, JobState.RUNNING)
    assert reason_problem(JobState.RUNNING, None) is None


def test_every_reason_belongs_to_exactly_one_state() -> None:
    """A reason shared by two outcomes would make branching on it ambiguous."""
    claimed = [reason for permitted in REASONS.values() for reason in permitted]
    assert sorted(claimed) == sorted(TerminalReason)


def test_the_message_for_a_terminal_state_says_it_is_final() -> None:
    """A refusal from a finished job explains itself rather than repeating the pair."""
    with pytest.raises(IllegalTransitionError) as refused:
        check_transition(JobState.SUCCEEDED, JobState.RUNNING)
    assert "terminal" in str(refused.value)
