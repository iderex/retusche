# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What the lane never allows, and what happens outside it.

The property worth the most here is the one a lock written by hand usually gets
right on a quiet machine and wrong under arrival pressure: the device holds no
more jobs at once than the lane's number, whatever order the submissions arrive
in. It is asserted from recorded entry and exit times rather than from a sleep,
because a sleep long enough to make the assertion pass is a sleep that makes the
suite slower for nothing and shorter than the machine's worst moment anyway.

The times are recorded by an engine that wraps the fake and stamps the two
moments around the run. That is exactly the interval the lane brackets, so the
overlap computed from them is the occupancy rather than a proxy for it. The fake
inside it is scripted to block at a step until the test releases it, which holds
jobs on the device for as long as the test needs and for no longer.

The near miss the overlap cases are aimed at is not a lane that ignores its
number, which fails immediately. It is one that holds it under two arrivals and
loses it under eight, and one that frees a seat only on the way out of a
successful run, so a single failing job shrinks the lane for the rest of the
process.

No device, no display, no elevation, and nothing that leaves the machine.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

import pytest

from retusche.queue.budget import DeviceMemoryBudget, Fit, OverBudgetError
from retusche.queue.lane import (
    ONE_JOB_ON_THE_DEVICE,
    AlreadyOnTheDeviceError,
    DeviceLane,
    InvalidLaneCountError,
)
from retusche.testing.fake_engine import FakeEngine, Script
from retusche_contracts.engine import (
    EditRequest,
    EngineFailure,
    ImageBuffer,
    JobDescription,
    MaskBuffer,
    Operation,
    UnsupportedRequest,
)

if TYPE_CHECKING:
    from retusche_contracts.engine import (
        CancellationToken,
        DeviceMemoryEstimate,
        ProgressCallback,
    )

_WIDTH = 4
_HEIGHT = 3
_ESTIMATE_BYTES = 1000
_BUDGET = DeviceMemoryBudget(total_bytes=10_000)
_ARRIVALS = 8
_PATIENCE_SECONDS = 10.0


def _job() -> JobDescription:
    """One job's shape, which every case here uses and none of them varies."""
    return JobDescription(
        operation=Operation.ERASE,
        width=_WIDTH,
        height=_HEIGHT,
        has_prompt=False,
        steps=2,
    )


def _request() -> EditRequest:
    """The request a preparation step would have built."""
    return EditRequest(
        operation=Operation.ERASE,
        image=ImageBuffer(
            data=bytes(_WIDTH * _HEIGHT * 3), width=_WIDTH, height=_HEIGHT, channels=3
        ),
        mask=MaskBuffer(data=bytes(_WIDTH * _HEIGHT), width=_WIDTH, height=_HEIGHT),
    )


class _Timed:
    """An engine that stamps when a run started and when it ended.

    Wraps the fake rather than replacing it, so what is timed is a real run
    through the contract: the refusals, the step loop and the scripted block are
    the fake's, and this adds only the two timestamps the overlap is computed
    from. Every stamp is taken under one lock, so the recorded order is the order
    they happened in.
    """

    def __init__(self, script: Script) -> None:
        self._engine = FakeEngine(script)
        self._lock = threading.Lock()
        self.intervals: list[tuple[int, int]] = []
        self.entered = threading.Semaphore(0)

    def capabilities(self) -> object:
        """What the fake declares, unchanged."""
        return self._engine.capabilities()

    def estimate_device_memory(self, job: JobDescription) -> DeviceMemoryEstimate:
        """What the fake estimates, unchanged."""
        return self._engine.estimate_device_memory(job)

    def run(
        self,
        request: EditRequest,
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
    ) -> ImageBuffer:
        """Run the fake, recording the interval the device was held for."""
        start = time.perf_counter_ns()
        self.entered.release()
        try:
            return self._engine.run(request, progress, cancellation)
        finally:
            with self._lock:
                self.intervals.append((start, time.perf_counter_ns()))


def _peak_overlap(intervals: list[tuple[int, int]]) -> int:
    """The most intervals that were open at once.

    Computed by walking the boundaries in order, an exit before an entry where
    the two share an instant. Sharing an instant is the case a lane holding its
    number exactly produces on a coarse clock, and counting it as an overlap
    would make this measure a clock resolution rather than an occupancy.
    """
    boundaries = sorted(
        [(start, 1) for start, _ in intervals] + [(end, -1) for _, end in intervals],
        key=lambda boundary: (boundary[0], boundary[1]),
    )
    peak = 0
    open_now = 0
    for _, change in boundaries:
        open_now += change
        peak = max(peak, open_now)
    return peak


def _drive(engine: _Timed, lane: DeviceLane, arrivals: int) -> list[threading.Thread]:
    """Send ``arrivals`` jobs at the lane at once and hand back the threads."""
    threads = [
        threading.Thread(
            target=lambda index=index: lane.serve(  # type: ignore[misc]  # bound per thread
                f"job-{index}", _job(), engine, _BUDGET, _request
            )
        )
        for index in range(arrivals)
    ]
    for thread in threads:
        thread.start()
    return threads


def test_the_default_is_one_job_on_the_device() -> None:
    """The number an operator gets without deciding anything."""
    assert DeviceLane().limit == ONE_JOB_ON_THE_DEVICE
    assert ONE_JOB_ON_THE_DEVICE == 1


@pytest.mark.parametrize("limit", [0, -1])
def test_a_lane_nothing_could_enter_is_refused_where_it_is_built(limit: int) -> None:
    """Zero is in this list on purpose: it accepts work and runs none of it."""
    with pytest.raises(InvalidLaneCountError):
        DeviceLane(limit)


@pytest.mark.parametrize("limit", [1, 3])
def test_the_lane_is_never_over_occupied_however_many_arrive(limit: int) -> None:
    """Eight arrivals at a lane of one and of three, timed rather than slept on.

    The runs are held on the device until every thread has been given the chance
    to arrive, so the pressure is real: with the lane's own accounting removed,
    all eight would be inside at once and the peak below would read eight.
    """
    released = threading.Event()
    engine = _Timed(Script(block_at_step=1, released=released))
    lane = DeviceLane(limit)

    threads = _drive(engine, lane, _ARRIVALS)
    for _ in range(limit):
        assert engine.entered.acquire(timeout=_PATIENCE_SECONDS)
    assert lane.occupancy.occupied == limit
    assert lane.occupancy.is_full
    released.set()
    for thread in threads:
        thread.join(timeout=_PATIENCE_SECONDS)
        assert not thread.is_alive()

    assert len(engine.intervals) == _ARRIVALS
    assert _peak_overlap(engine.intervals) == limit
    assert lane.occupancy.occupied == 0


def test_the_occupancy_reading_names_the_job_that_is_on_the_device() -> None:
    """What a metrics surface would publish, and what #65 does not exist to."""
    lane = DeviceLane(2)

    with lane.occupied_by("job-a"):
        reading = lane.occupancy
        assert reading.on_the_device == frozenset({"job-a"})
        assert reading.occupied == 1
        assert reading.free == 1
        assert not reading.is_full
        assert reading.limit == 2

    assert lane.occupancy.free == 2


def test_one_job_cannot_take_two_seats() -> None:
    """A second dispatch of one job, in a lane with room for a second job.

    The room matters: in a lane of one this would block and look like the
    concurrency limit holding, which is a different property from this one.
    """
    lane = DeviceLane(2)

    with (
        lane.occupied_by("job-a"),
        pytest.raises(AlreadyOnTheDeviceError) as refusal,
        lane.occupied_by("job-a"),
    ):
        pass  # pragma: no cover  # the third context refuses as it is entered

    assert "job-a" in str(refusal.value)
    assert lane.occupancy.on_the_device == frozenset()


def test_a_seat_is_freed_by_a_run_that_raised() -> None:
    """A lane that leaked a seat per failure would shrink until nothing started."""
    engine = _Timed(Script(fail_at_step=1, failure=EngineFailure))
    lane = DeviceLane()

    with pytest.raises(EngineFailure):
        lane.serve("job-a", _job(), engine, _BUDGET, _request)

    assert lane.occupancy.occupied == 0
    assert lane.serve("job-b", _job(), FakeEngine(), _BUDGET, _request).width == _WIDTH


def test_a_job_the_budget_will_never_admit_never_reaches_the_lane() -> None:
    """Refused before anything is decoded, and the refusal ends the job.

    `prepare` is the expensive half. Asserting it was not called is asserting
    that a photograph was not decoded for a job that was always going to be
    refused.
    """
    prepared: list[int] = []
    engine = FakeEngine(Script(device_memory_bytes=_BUDGET.total_bytes + 1))
    lane = DeviceLane()

    def prepare() -> EditRequest:
        prepared.append(1)
        return _request()  # pragma: no cover  # the admission above refuses first

    with pytest.raises(OverBudgetError):
        lane.serve("job-a", _job(), engine, _BUDGET, prepare)

    assert prepared == []
    assert lane.occupancy.occupied == 0


def test_a_job_the_engine_would_refuse_anyway_is_refused_at_admission() -> None:
    """The engine's own refusal reaches the caller instead of becoming a fit."""
    engine = FakeEngine(Script(operations=frozenset({Operation.FILL})))
    lane = DeviceLane()

    with pytest.raises(UnsupportedRequest):
        lane.admit(_job(), engine, _BUDGET)


def test_a_job_that_fits_only_once_room_is_freed_is_not_an_error() -> None:
    """Waiting and refusing are different answers and admission returns which."""
    engine = FakeEngine(Script(device_memory_bytes=_ESTIMATE_BYTES))
    lane = DeviceLane()
    tight = DeviceMemoryBudget(
        total_bytes=_ESTIMATE_BYTES, resident_bytes=_ESTIMATE_BYTES - 1
    )

    assert lane.admit(_job(), engine, _BUDGET) is Fit.NOW
    assert lane.admit(_job(), engine, tight) is Fit.WHEN_ROOM_IS_FREED


def test_work_that_needs_no_device_happens_while_the_device_is_busy() -> None:
    """The third done-condition of #27, asserted as an overlap rather than an order.

    One job is held on the device. A second job's preparation is then driven to
    completion and its own arrival at the lane observed, so what is established is
    that preparing the second job did not wait for the first to leave the device.
    Preparation moved inside the lane fails this: the second `prepare` would not
    return until the first run had.
    """
    released = threading.Event()
    engine = _Timed(Script(block_at_step=1, released=released))
    lane = DeviceLane()
    prepared = threading.Event()

    def prepare() -> EditRequest:
        prepared.set()
        return _request()

    holder = threading.Thread(
        target=lambda: lane.serve("job-a", _job(), engine, _BUDGET, _request)
    )
    holder.start()
    assert engine.entered.acquire(timeout=_PATIENCE_SECONDS)
    waiter = threading.Thread(
        target=lambda: lane.serve("job-b", _job(), engine, _BUDGET, prepare)
    )
    waiter.start()

    assert prepared.wait(timeout=_PATIENCE_SECONDS)
    assert lane.occupancy.on_the_device == frozenset({"job-a"})

    released.set()
    for thread in (holder, waiter):
        thread.join(timeout=_PATIENCE_SECONDS)
        assert not thread.is_alive()


def test_the_estimate_is_asked_before_the_request_is_built() -> None:
    """A photograph is not decoded to answer a question about the device."""
    order: list[str] = []
    engine = FakeEngine()
    lane = DeviceLane()

    class _Watched:
        """The engine, with the two calls this case is about recorded."""

        def capabilities(self) -> object:
            return engine.capabilities()  # pragma: no cover  # nothing here asks

        def estimate_device_memory(self, job: JobDescription) -> DeviceMemoryEstimate:
            order.append("estimate")
            return engine.estimate_device_memory(job)

        def run(
            self,
            request: EditRequest,
            progress: ProgressCallback | None = None,
            cancellation: CancellationToken | None = None,
        ) -> ImageBuffer:
            order.append("run")
            return engine.run(request, progress, cancellation)

    def prepare() -> EditRequest:
        order.append("prepare")
        return _request()

    lane.serve("job-a", _job(), _Watched(), _BUDGET, prepare)

    assert order == ["estimate", "prepare", "run"]


def test_progress_and_cancellation_reach_the_engine() -> None:
    """The lane brackets the engine call and carries what the caller passed."""
    seen: list[tuple[int, int]] = []
    lane = DeviceLane()

    class _Token:
        """A token that is never set, so the run completes."""

        @property
        def is_cancelled(self) -> bool:
            return False

    lane.serve(
        "job-a",
        _job(),
        FakeEngine(),
        _BUDGET,
        _request,
        progress=lambda step, total: seen.append((step, total)),
        cancellation=_Token(),
    )

    assert seen == [(1, 2), (2, 2)]
