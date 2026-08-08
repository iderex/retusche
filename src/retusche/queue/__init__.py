# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The job model: where a job can be, how it moves, and where that is kept.

Two modules and one rule between them. `retusche.queue.states` declares the
states, every move that exists and the reason each terminal state carries.
`retusche.queue.store` makes a move durable, and it asks that table rather than
deciding for itself, so there is one answer to what a job may do and not one per
caller.

This package holds no admission, no ordering and no lane. Those are #27, #28 and
#30, and each of them moves a job through the table here rather than adding
states of its own.
"""

from __future__ import annotations

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
    "CorruptJobStoreError",
    "DuplicateJobError",
    "IllegalTransitionError",
    "JobRecord",
    "JobState",
    "JobStateError",
    "JobStore",
    "JobStoreError",
    "TerminalReason",
    "TerminalReasonError",
    "UnknownJobError",
    "check_transition",
    "reason_problem",
]
