# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The device memory budget, and the refusal that happens before a lane is spent.

The device this project runs on belongs to the operator and usually to something
else as well: a photo library doing its own machine learning, a transcoder, a
desktop session. So the budget is a number the operator writes down, not a
number this project reads off the card and takes. What is configured is the most
device memory this project will hold at once, resident weights included, and
everything here compares against that rather than against what the device
reports free.

The comparison happens before a job is admitted. An out-of-memory failure part
way through a run costs the whole job, and on a shared device it does not cost
only this job: the allocation that fails may be the photo library's.
`docs/engine-interface.md` carries the longer form of that argument, and
`estimate_device_memory` in the contract exists to make the comparison possible
without loading weights or touching the device.

What the estimate is counted against
------------------------------------
`DeviceMemoryEstimate.peak_bytes` is read here as the working set the job would
add, and the weights an engine already holds are counted separately, as
`resident_bytes`. That is the only reading under which a loaded model reduces
the room for the next job rather than being invisible, which is the property
this module exists for. The contract does not say it in those words, and where
it should be said is `docs/engine-interface.md`, which this change does not
touch.

What this module does not decide
--------------------------------
Which job goes next, whether a lane is free, and what happens to a job after it
is refused. Ordering is #28, the lane is #27, and recovering from an
out-of-memory failure is #31. This module answers one question, once: does this
job fit in what is left of the budget. `check_fits` returns nothing when it
does and raises when it does not, in the shape `retusche.queue.states` uses for
the same reason - the caller writes the move, and nothing here writes anything.

A refusal is a type and not a message
-------------------------------------
`OverBudgetError` carries the job, the estimate and the budget, and its
`terminal_reason` is `TerminalReason.REFUSED_OVER_BUDGET`, which the state table
already declares as a reason `FAILED` may carry. A caller that has to tell a
refusal from a failure branches on the type and the reason; the sentence is for
the operator reading it afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from retusche.queue.states import TerminalReason

if TYPE_CHECKING:
    from retusche_contracts.engine import DeviceMemoryEstimate, JobDescription

__all__ = [
    "BudgetError",
    "DeviceMemoryBudget",
    "EstimationDefect",
    "InvalidBudgetError",
    "OverBudgetError",
    "check_fits",
    "estimation_defect",
]


class BudgetError(Exception):
    """Base of everything this module refuses."""


class InvalidBudgetError(BudgetError):
    """The budget itself does not describe an amount of memory.

    Raised when the budget is built rather than when a job is compared against
    it, so a deployment configured with a nonsense number is refused at the
    point the number arrives and not on the first job of the day.
    """


class OverBudgetError(BudgetError):
    """The job's estimate does not fit in what is left of the budget.

    Refusal, not failure. Nothing was attempted, nothing was allocated, and the
    same request may fit later once the resident weights it did not fit beside
    have been released.
    """

    terminal_reason: Final = TerminalReason.REFUSED_OVER_BUDGET
    """The reason the job ends with, as something a caller branches on.

    Declared on the class rather than passed at each raise site, because a
    second raise site choosing a different reason is exactly the divergence this
    is here to prevent.
    """

    def __init__(
        self,
        job: JobDescription,
        estimate: DeviceMemoryEstimate,
        budget: DeviceMemoryBudget,
    ) -> None:
        super().__init__(_refusal_message(job, estimate, budget))
        self.job = job
        self.estimate = estimate
        self.budget = budget


@dataclass(frozen=True, slots=True)
class DeviceMemoryBudget:
    """The ceiling the operator set, and how much of it is already held.

    ``total_bytes`` is the whole of what this project may hold on the device at
    once, weights included. ``resident_bytes`` is the part of it that loaded
    weights are holding right now, so that the room a job is compared against
    shrinks as models stay resident. Which models stay resident and for how long
    is #32; this only reads the number.
    """

    total_bytes: int
    resident_bytes: int = 0

    def __post_init__(self) -> None:
        """Refuse a budget that is not an amount of memory, naming which half."""
        if self.total_bytes <= 0:
            message = (
                f"a device memory budget is a positive number of bytes and "
                f"{self.total_bytes} was given. A budget of zero refuses every "
                f"job with a message about memory, which reads as a broken "
                f"device rather than as a setting nobody wrote."
            )
            raise InvalidBudgetError(message)
        if self.resident_bytes < 0:
            message = (
                f"resident weights hold {self.resident_bytes} bytes, which is "
                f"not an amount of memory. A negative resident figure makes the "
                f"room for the next job larger than the budget, which is the "
                f"one direction this comparison must never be wrong in."
            )
            raise InvalidBudgetError(message)
        if self.resident_bytes > self.total_bytes:
            message = (
                f"resident weights hold {self.resident_bytes} bytes against a "
                f"budget of {self.total_bytes}, so the budget has already been "
                f"exceeded by what is loaded. Nothing here can refuse that back "
                f"into range: it is either an eviction that did not happen or a "
                f"budget lowered under a loaded model."
            )
            raise InvalidBudgetError(message)

    @property
    def free_bytes(self) -> int:
        """What is left of the budget for the next job."""
        return self.total_bytes - self.resident_bytes


@dataclass(frozen=True, slots=True)
class EstimationDefect:
    """A job that was admitted on an estimate and then ran out of memory anyway.

    The estimate was wrong, and the thing that makes it correctable is the shape
    of the job it was wrong about. So this carries the description the estimate
    was made from rather than only the two numbers, and the caller that builds
    one has the job in hand at that moment.

    Where this is written down is not decided here. Structured logging is #64
    and the audit trail is #67, and neither exists, so what this module produces
    is the record and its sentence rather than a line in a file that is not
    there yet.
    """

    job: JobDescription
    estimate: DeviceMemoryEstimate
    budget: DeviceMemoryBudget

    @property
    def message(self) -> str:
        """The sentence an operator reads, naming the shape and both numbers."""
        return (
            f"the device ran out of memory on a job the budget admitted: "
            f"{_shape(self.job)} was estimated at "
            f"{self.estimate.peak_bytes} bytes "
            f"{_provenance(self.estimate)} against {self.budget.free_bytes} "
            f"bytes free of a {self.budget.total_bytes} byte budget. The "
            f"estimate is what was wrong here, not the budget, and correcting "
            f"it needs the shape above rather than the failure alone."
        )


def check_fits(
    job: JobDescription,
    estimate: DeviceMemoryEstimate,
    budget: DeviceMemoryBudget,
) -> None:
    """Refuse a job whose estimate exceeds what is left of the budget.

    Returns nothing where it fits. An estimate equal to the room left fits: the
    figure is documented as an upper bound the engine is willing to be held to,
    so a job that needs exactly what is there is a job the budget was set for.
    """
    if estimate.peak_bytes > budget.free_bytes:
        raise OverBudgetError(job, estimate, budget)


def estimation_defect(
    job: JobDescription,
    estimate: DeviceMemoryEstimate,
    budget: DeviceMemoryBudget,
) -> EstimationDefect:
    """Record an out-of-memory failure on a job this budget admitted.

    A separate function rather than a bare constructor call, so the one place
    that decides an overrun is an estimation defect is named and can be pointed
    at. What the queue then does about the failure is #31.
    """
    return EstimationDefect(job=job, estimate=estimate, budget=budget)


def _refusal_message(
    job: JobDescription,
    estimate: DeviceMemoryEstimate,
    budget: DeviceMemoryBudget,
) -> str:
    """Both numbers, the room they were compared in, and the shape refused."""
    return (
        f"{_shape(job)} is estimated at {estimate.peak_bytes} bytes "
        f"{_provenance(estimate)} and {budget.free_bytes} bytes are free of a "
        f"{budget.total_bytes} byte device memory budget, "
        f"{budget.resident_bytes} of which resident weights are holding. The "
        f"job is refused before it reaches the device, because an allocation "
        f"that fails there can be something else's."
    )


def _shape(job: JobDescription) -> str:
    """The job as a phrase, so a refusal says what to make smaller."""
    return (
        f"a {job.width} by {job.height} {job.operation.value} over {job.steps} step(s)"
    )


def _provenance(estimate: DeviceMemoryEstimate) -> str:
    """Whether the number came from a measurement or from a formula.

    Printed in both sentences this module produces. An operator deciding
    whether to raise the budget or to distrust the estimate is deciding
    different things depending on which it is, and nothing else in the message
    tells them.
    """
    if estimate.is_measured:
        return "(measured)"
    return "(derived from the job's shape, not measured)"
