# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""One lane on the device: how many jobs may be in it, and what happens outside.

Two generative jobs running at once on one consumer card are usually slower than
the same two run in sequence, and they turn a predictable memory footprint into an
unpredictable one: each job's peak is estimated on its own, and two peaks that
overlap are a number nobody estimated. So the device holds one job at a time
unless an operator says otherwise, and the number is the lane's rather than a
convention every caller is trusted to keep.

What is inside the lane
-----------------------
The engine call and nothing else. Decoding an image, validating a mask, reading a
registry entry and asking for a memory estimate all happen before the lane is
entered, because a lane occupied by work that does not touch the device is a
device sitting idle while its one lane is busy. `serve` is where that ordering
lives, so it is one decision in one place rather than a rule each caller is asked
to remember.

The estimate is asked outside the lane for a second reason the contract gives:
`estimate_device_memory` is declared answerable without loading weights and
without touching the device, so the queue can ask about a job it may never admit.
Asking it inside the lane would spend the device's one seat on a question about
whether the job should ever have one.

Refused, or waiting
-------------------
Those are different things and this module keeps them apart. A job whose estimate
exceeds the whole budget is refused by `retusche.queue.budget`, which ends it: no
amount of waiting makes a ceiling larger. A job that fits the budget and not the
room free right now waits, and so does a job that fits everything and arrives
while the lane is full. Waiting on a full lane is unbounded here on purpose. What
stops a backlog growing without limit is a bound on the queue rather than a
timeout on the device, and that is #34.

Nothing here evicts anything to make room, and nothing here decides which waiting
job goes next. Eviction is #32 and the order is `retusche.queue.ordering`, whose
`next_to_start` takes the predicate this module's occupancy answers.

What is not here
----------------
The occupancy reading below is what a metrics surface would read, and there is no
metrics surface: #65 owns it, and the last done-condition of #27 stays open until
it exists. A number a reader can ask for is not the same as a number published,
and this module carries the first half only.

The lane count is an argument with a default of one rather than a row in
`retusche.config.settings`. The setting belongs to the declared configuration
surface, which is outside the paths #27 names, so the default lives here and the
row that would feed it is not this issue's to add.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from retusche.queue.budget import fits

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from retusche.queue.budget import DeviceMemoryBudget, Fit
    from retusche_contracts.engine import (
        CancellationToken,
        DeviceMemoryEstimate,
        EditRequest,
        Engine,
        ImageBuffer,
        JobDescription,
        ProgressCallback,
    )

__all__ = [
    "ONE_JOB_ON_THE_DEVICE",
    "AlreadyOnTheDeviceError",
    "DeviceLane",
    "InvalidLaneCountError",
    "LaneError",
    "Occupancy",
]

ONE_JOB_ON_THE_DEVICE: Final = 1
"""The default number of jobs allowed on the device at once.

One, because that is the arrangement whose memory footprint is the one that was
estimated. An operator with a card that justifies more raises it knowingly; a
default above one would take that decision for every operator who never read this
page.
"""


class LaneError(Exception):
    """Base of everything this module refuses."""


class InvalidLaneCountError(LaneError):
    """The lane count is not a number of jobs.

    Raised where the lane is built rather than where a job asks to enter it, so a
    deployment configured with nonsense is refused at the point the number arrives
    and not on the first job of the day. Zero is included: a lane nothing may
    enter is a service that accepts work and never runs any, which reads as a hung
    device rather than as a setting nobody wrote.
    """


class AlreadyOnTheDeviceError(LaneError):
    """This job is already in the lane.

    One job occupying two seats is a double dispatch, and the seat it takes is one
    another job would have had. It is refused rather than counted, because a lane
    that admits the same job twice reports an occupancy that is true and a
    concurrency that is not.
    """

    def __init__(self, job_id: str) -> None:
        super().__init__(
            f"job {job_id} is already on the device, so this is a second "
            f"dispatch of one job rather than a second job. Nothing was started "
            f"and the lane is unchanged."
        )
        self.job_id = job_id


@dataclass(frozen=True, slots=True)
class Occupancy:
    """How much of the lane is taken, as a reading a caller can act on.

    Carries the job identifiers rather than only a count, because the question an
    operator asks about a busy device is which job is on it. Taken under the
    lane's own lock and frozen afterwards, so it is a reading of one moment and
    never a view that changes while it is being reported.
    """

    on_the_device: frozenset[str]
    limit: int

    @property
    def occupied(self) -> int:
        """How many seats are taken."""
        return len(self.on_the_device)

    @property
    def free(self) -> int:
        """How many jobs could enter right now."""
        return self.limit - self.occupied

    @property
    def is_full(self) -> bool:
        """Whether the next job to arrive would wait."""
        return self.free == 0


class DeviceLane:
    """The device as one place with a stated number of seats.

    Every entry goes through `occupied_by`, and `serve` is the one path that puts
    admission and preparation in front of it in the right order. A caller holding
    this object can ask what is on the device without entering it.
    """

    def __init__(self, limit: int = ONE_JOB_ON_THE_DEVICE) -> None:
        """Build a lane with a stated number of seats, refusing a nonsense one."""
        if limit < ONE_JOB_ON_THE_DEVICE:
            message = (
                f"a device lane holds at least one job and {limit} was given. "
                f"The default is {ONE_JOB_ON_THE_DEVICE}, which is the "
                f"arrangement whose memory footprint the estimates describe."
            )
            raise InvalidLaneCountError(message)
        self._limit = limit
        self._on_the_device: set[str] = set()
        self._room = threading.Condition()

    @property
    def limit(self) -> int:
        """How many jobs this lane allows on the device at once."""
        return self._limit

    @property
    def occupancy(self) -> Occupancy:
        """What is on the device right now.

        This is the reading a metrics surface would publish. #65 owns the surface
        and does not exist, so nothing publishes it yet.
        """
        with self._room:
            return Occupancy(
                on_the_device=frozenset(self._on_the_device), limit=self._limit
            )

    def admit(
        self,
        job: JobDescription,
        engine: Engine,
        budget: DeviceMemoryBudget,
    ) -> Fit:
        """Ask the engine what the job needs and hold it against the budget.

        Answers with the fit rather than a boolean, so a caller can tell a job
        that waits from a job that could start now, and raises where the job never
        fits. Whatever the engine raises about a job it would refuse anyway
        reaches the caller unchanged: a refusal is the answer to admission, and
        turning it into a fit would put the job in a lane to be refused there.

        Nothing about the lane's occupancy is read here. Whether there is a seat
        is `occupancy`, and taking one is `occupied_by`; a decision that read both
        at once would be a decision two callers could make from the same reading.
        """
        estimate: DeviceMemoryEstimate = engine.estimate_device_memory(job)
        return fits(job, estimate, budget)

    @contextmanager
    def occupied_by(self, job_id: str) -> Iterator[None]:
        """Hold a seat for this job, waiting for one where the lane is full.

        The seat is released on the way out whatever happened inside, including an
        engine that raised and an engine that was cancelled. A lane that leaked a
        seat on a failure would shrink by one job per failure until nothing could
        start, and the failure that caused it would be somewhere else in the log.
        """
        with self._room:
            while len(self._on_the_device) >= self._limit:
                self._room.wait()
            if job_id in self._on_the_device:
                raise AlreadyOnTheDeviceError(job_id)
            self._on_the_device.add(job_id)
        try:
            yield
        finally:
            with self._room:
                self._on_the_device.discard(job_id)
                self._room.notify()

    def serve(
        self,
        job_id: str,
        job: JobDescription,
        engine: Engine,
        budget: DeviceMemoryBudget,
        prepare: Callable[[], EditRequest],
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
    ) -> ImageBuffer:
        """Admit, prepare, then occupy the lane for the engine call.

        `prepare` is whatever turns a job into a request: decoding the image,
        validating the mask, reading the entry that names the weights. It is
        called outside the lane, and that is the whole reason this function exists
        rather than each caller writing the same three lines: the ordering is the
        property, and a property spread across callers is a convention.

        The estimate is asked before `prepare` for the same reason it is asked
        outside the lane. A job the budget will never admit is refused before
        anybody decodes a photograph for it.
        """
        self.admit(job, engine, budget)
        request = prepare()
        with self.occupied_by(job_id):
            return engine.run(request, progress, cancellation)
