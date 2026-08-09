# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The job model: where a job can be, how it moves, and where that is kept.

Three modules and one rule between them. `retusche.queue.states` declares the
states, every move that exists and the reason each terminal state carries.
`retusche.queue.store` makes a move durable, and it asks that table rather than
deciding for itself, so there is one answer to what a job may do and not one per
caller. `retusche.queue.budget` decides whether a job fits in the device memory
the operator allowed, now or once room is freed, and refuses one that never
fits before a lane is spent on it.

This package holds no ordering and no lane. Those are #28 and #27, and each of
them moves a job through the table here rather than adding states of its own.
The budget module is the same: it names a refusal the table already declares a
reason for, and writes nothing.
"""

from __future__ import annotations

from retusche.queue.budget import (
    BudgetError,
    DeviceMemoryBudget,
    EstimationDefect,
    Fit,
    InvalidBudgetError,
    OverBudgetError,
    estimation_defect,
    fits,
)
from retusche.queue.states import (
    LEGAL_TRANSITIONS,
    REASONS,
    TERMINAL_STATES,
    IllegalTransitionError,
    JobState,
    JobStateError,
    TerminalReason,
    TerminalReasonError,
    check_transition,
    reason_problem,
)
from retusche.queue.store import (
    CorruptJobStoreError,
    DuplicateJobError,
    JobRecord,
    JobStore,
    JobStoreError,
    UnknownJobError,
)

__all__ = [
    "LEGAL_TRANSITIONS",
    "REASONS",
    "TERMINAL_STATES",
    "BudgetError",
    "CorruptJobStoreError",
    "DeviceMemoryBudget",
    "DuplicateJobError",
    "EstimationDefect",
    "Fit",
    "IllegalTransitionError",
    "InvalidBudgetError",
    "JobRecord",
    "JobState",
    "JobStateError",
    "JobStore",
    "JobStoreError",
    "OverBudgetError",
    "TerminalReason",
    "TerminalReasonError",
    "UnknownJobError",
    "check_transition",
    "estimation_defect",
    "fits",
    "reason_problem",
]
