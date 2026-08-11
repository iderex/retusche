# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The job model: where a job can be, how it moves, and where that is kept.

Four modules and one rule between them. `retusche.queue.states` declares the
states, every move that exists and the reason each terminal state carries.
`retusche.queue.store` makes a move durable, and it asks that table rather than
deciding for itself, so there is one answer to what a job may do and not one per
caller. `retusche.queue.budget` decides whether a job fits in the device memory
the operator allowed, now or once room is freed, and refuses one that never
fits before a lane is spent on it.

`retusche.queue.ordering` decides which waiting job is considered next and
carries the bound that stops background work waiting forever.

`retusche.queue.lane` is the device seen as one place with a stated number of
seats. It asks the engine for an estimate and holds it against the budget before
anything is decoded, and it brackets the engine call and nothing else, so the one
seat a default deployment has is never held by work that does not touch the
device.

Nothing in this package writes a job anywhere except the store: the budget names a
refusal the table already declares a reason for, the ordering answers with a
sequence, and the lane answers with an occupancy.
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
from retusche.queue.lane import (
    ONE_JOB_ON_THE_DEVICE,
    AlreadyOnTheDeviceError,
    DeviceLane,
    InvalidLaneCountError,
    LaneError,
    Occupancy,
)
from retusche.queue.ordering import (
    INTERACTIVE_BEFORE_BACKGROUND,
    NO_WAIT_ESTIMATE,
    Priority,
    QueuePosition,
    Waiting,
    interactive_run_after,
    next_to_start,
    order,
    position_of,
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
    "INTERACTIVE_BEFORE_BACKGROUND",
    "LEGAL_TRANSITIONS",
    "NO_WAIT_ESTIMATE",
    "ONE_JOB_ON_THE_DEVICE",
    "REASONS",
    "TERMINAL_STATES",
    "AlreadyOnTheDeviceError",
    "BudgetError",
    "CorruptJobStoreError",
    "DeviceLane",
    "DeviceMemoryBudget",
    "DuplicateJobError",
    "EstimationDefect",
    "Fit",
    "IllegalTransitionError",
    "InvalidBudgetError",
    "InvalidLaneCountError",
    "JobRecord",
    "JobState",
    "JobStateError",
    "JobStore",
    "JobStoreError",
    "LaneError",
    "Occupancy",
    "OverBudgetError",
    "Priority",
    "QueuePosition",
    "TerminalReason",
    "TerminalReasonError",
    "UnknownJobError",
    "Waiting",
    "check_transition",
    "estimation_defect",
    "fits",
    "interactive_run_after",
    "next_to_start",
    "order",
    "position_of",
    "reason_problem",
]
