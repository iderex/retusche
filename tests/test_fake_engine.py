# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What the fake engine does, asserted against the contract it implements.

The fake exists so that the orchestration layer can be exercised with no device
present. That makes it load-bearing in a way an ordinary helper is not: every
later assertion about admission, cancellation, progress or failure is really an
assertion about this file's subject behaving as the contract says an engine
does. A fake nobody tested is a second implementation of the thing under test.

This is not the engine contract suite. That suite is #16's, it lives in
`tests/contract/`, it is parameterised over every engine including the ones that
need hardware, and it is not in the tree. What is here is specific to this
engine: that each scripted behaviour is the behaviour that happens.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest

from retusche.testing import FakeEngine, Script
from retusche_contracts import (
    Cancelled,
    EditRequest,
    Engine,
    EngineFailure,
    ImageBuffer,
    JobDescription,
    MaskBuffer,
    ModelNotAvailable,
    Operation,
    OutOfDeviceMemory,
    SizeConstraint,
    UnsupportedRequest,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from retusche_contracts import EngineError


class _Token:
    """A cancellation token a test can set, with the contract's own latch: once
    it reads cancelled it keeps reading cancelled."""

    def __init__(self, *, cancelled: bool = False) -> None:
        self._cancelled = cancelled

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled


class _Recorder:
    """Every progress call, in order, so monotonicity is asserted rather than
    the last value being taken as evidence of the ones before it."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def __call__(self, step: int, total: int) -> None:
        self.calls.append((step, total))


def _image(width: int = 4, height: int = 3, channels: int = 3) -> ImageBuffer:
    """An input whose bytes are all different, so a byte copied to the wrong
    place is a byte that shows."""
    data = bytes((index * 7 + 11) % 256 for index in range(width * height * channels))
    return ImageBuffer(data=data, width=width, height=height, channels=channels)


def _mask(
    width: int = 4, height: int = 3, *, covered: frozenset[int] = frozenset()
) -> MaskBuffer:
    """A mask covering the pixel indices named and nothing else."""
    data = bytes(255 if index in covered else 0 for index in range(width * height))
    return MaskBuffer(data=data, width=width, height=height)


def _request(
    operation: Operation = Operation.ERASE,
    *,
    covered: frozenset[int] = frozenset(),
    prompt: str | None = None,
    steps: int | None = None,
    seed: int | None = None,
    parameters: Mapping[str, str] | None = None,
) -> EditRequest:
    """A request over the default image and mask, with the optional half spelled
    out rather than forwarded, so every field a test sets is one mypy checked."""
    return EditRequest(
        operation=operation,
        image=_image(),
        mask=_mask(covered=covered),
        prompt=prompt,
        steps=steps,
        seed=seed,
        parameters=parameters,
    )


def _job(
    operation: Operation = Operation.ERASE,
    *,
    width: int = 4,
    height: int = 3,
    has_prompt: bool = False,
) -> JobDescription:
    return JobDescription(
        operation=operation,
        width=width,
        height=height,
        has_prompt=has_prompt,
        steps=2,
    )


def test_the_fake_is_an_engine() -> None:
    """The protocol is runtime-checkable, and this is the check the worker will
    make before it accepts an engine at load."""
    assert isinstance(FakeEngine(), Engine)


def test_the_declaration_is_what_the_script_says() -> None:
    script = Script(
        engine_id="scripted",
        operations=frozenset({Operation.FILL}),
        sizes=SizeConstraint(min_side=8, max_side=64, multiple_of=8),
        uses_prompt=True,
        steps=5,
    )
    declared = FakeEngine(script).capabilities()
    assert declared.engine_id == "scripted"
    assert declared.operations == frozenset({Operation.FILL})
    assert declared.sizes == SizeConstraint(min_side=8, max_side=64, multiple_of=8)
    assert declared.uses_prompt is True
    assert declared.step_count_is_one is False


def test_a_single_step_engine_says_so() -> None:
    """`step_count_is_one` is derived from the step count rather than scripted
    beside it. A script could otherwise declare a bound on cancellation latency
    that its own loop does not keep."""
    assert FakeEngine(Script(steps=1)).capabilities().step_count_is_one is True


def test_the_declaration_does_not_move_between_calls() -> None:
    """The queue reads it to decide admission. A declaration that changed
    between two calls would make those decisions unrepeatable."""
    subject = FakeEngine()
    assert subject.capabilities() == subject.capabilities()


def test_the_memory_estimate_follows_the_shape_of_the_job() -> None:
    estimate = FakeEngine().estimate_device_memory(_job(width=16, height=8))
    assert estimate.peak_bytes == 16 * 8 * 4
    assert estimate.is_measured is False


def test_a_scripted_estimate_answers_whatever_the_budget_needs() -> None:
    """This is the lever an admission test pulls. Driving a budget honestly
    would mean an image large enough to exceed it, which is an image no test
    wants to hold."""
    subject = FakeEngine(
        Script(device_memory_bytes=64 * 1024**3, estimate_is_measured=True)
    )
    estimate = subject.estimate_device_memory(_job())
    assert estimate.peak_bytes == 64 * 1024**3
    assert estimate.is_measured is True


def test_an_unservable_job_is_refused_before_a_lane_is_spent_on_it() -> None:
    """The contract has `estimate_device_memory` refuse what the engine would
    refuse anyway, so the queue never admits a job to learn that."""
    subject = FakeEngine(Script(operations=frozenset({Operation.FILL})))
    with pytest.raises(UnsupportedRequest, match="erase"):
        subject.estimate_device_memory(_job(Operation.ERASE))


def test_a_run_reports_every_step_and_ends_at_the_declared_total() -> None:
    recorder = _Recorder()
    FakeEngine(Script(steps=4)).run(_request(), progress=recorder)
    assert recorder.calls == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_a_run_without_a_progress_callback_still_runs() -> None:
    """Progress is optional in the signature, so the arm where it is absent is
    the one a caller that does not care takes."""
    assert FakeEngine(Script(steps=3)).run(_request()).width == 4


def test_pixels_outside_the_mask_come_back_unchanged() -> None:
    """The property the contract suite asserts against every engine, and the
    one an edit is judged by: a photograph is not softened everywhere because
    somebody asked for one object to go."""
    source = _image()
    result = FakeEngine().run(_request(covered=frozenset({5})))
    assert result.width == source.width
    assert result.height == source.height
    assert result.channels == source.channels
    untouched = [index for index in range(12) if index != 5]
    for pixel in untouched:
        at = pixel * 3
        assert result.data[at : at + 3] == source.data[at : at + 3]


def test_the_masked_pixel_is_replaced() -> None:
    """The other half of the previous test. An engine that returned its input
    unchanged would pass that one and do nothing."""
    source = _image()
    result = FakeEngine().run(_request(covered=frozenset({5})))
    assert result.data[15:18] != source.data[15:18]


def test_the_same_request_produces_the_same_bytes() -> None:
    subject = FakeEngine()
    first = subject.run(_request(covered=frozenset({0, 1}), seed=7))
    second = FakeEngine().run(_request(covered=frozenset({0, 1}), seed=7))
    assert first.data == second.data


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ((1, None), (2, None)),
        ((1, "a"), (1, "b")),
        ((None, None), (0, None)),
        ((1, "2 people"), (12, " people")),
    ],
)
def test_a_request_differing_anywhere_produces_different_bytes(
    left: tuple[int | None, str | None], right: tuple[int | None, str | None]
) -> None:
    """Determinism is only useful if it is not constancy. Each pair is a seed
    and a prompt.

    The fourth is the one the length prefix in the material exists for, and it
    is the near-miss rather than an obvious violation: seed 1 with a prompt
    beginning ``2`` and seed 12 with the same prompt less that character run
    together to the same characters. A material that concatenated its parts
    would hand two different requests one identical string of bytes, and the
    fake would answer both with the same photograph. The first three pairs pass
    with or without the prefix, so this is the only arm that holds it.
    """
    subject = FakeEngine(Script(uses_prompt=True))
    covered = frozenset(range(12))
    produced = subject.run(_request(covered=covered, seed=left[0], prompt=left[1]))
    other = subject.run(_request(covered=covered, seed=right[0], prompt=right[1]))
    assert produced.data != other.data


def test_an_extend_returns_a_larger_canvas_holding_the_original() -> None:
    """The contract says an extend returns a buffer larger than the one it was
    given and that the caller reads the new size off the buffer."""
    source = _image()
    result = FakeEngine().run(_request(Operation.EXTEND))
    assert (result.width, result.height) == (4 + 8, 3 + 8)
    for row in range(source.height):
        source_at = row * source.width * source.channels
        target_at = ((row + 4) * result.width + 4) * result.channels
        assert (
            result.data[target_at : target_at + source.width * source.channels]
            == source.data[source_at : source_at + source.width * source.channels]
        )


def test_cancellation_before_the_first_step_produces_no_image() -> None:
    with pytest.raises(Cancelled, match="step 1 of 2"):
        FakeEngine().run(_request(), cancellation=_Token(cancelled=True))


def test_cancellation_is_observed_at_the_next_step_boundary() -> None:
    """Cooperative cancellation, and its granularity is a step. A caller that
    cancels observes the stop after at most one further step completes."""
    token = _Token()

    class _CancelAfterTheFirst(_Recorder):
        def __call__(self, step: int, total: int) -> None:
            super().__call__(step, total)
            token.cancel()

    recorder = _CancelAfterTheFirst()
    with pytest.raises(Cancelled, match="step 2 of 4"):
        FakeEngine(Script(steps=4)).run(
            _request(), progress=recorder, cancellation=token
        )
    assert recorder.calls == [(1, 4)]


def test_an_engine_scripted_to_ignore_cancellation_ignores_it() -> None:
    """This is the case the queue's forced-termination path is tested against,
    and no engine that honours cancellation can produce it. Without this arm the
    script's `honours_cancellation` field would be a setting nothing reads."""
    result = FakeEngine(Script(honours_cancellation=False)).run(
        _request(), cancellation=_Token(cancelled=True)
    )
    assert isinstance(result, ImageBuffer)


@pytest.mark.parametrize(
    "failure",
    [EngineFailure, OutOfDeviceMemory, ModelNotAvailable, UnsupportedRequest],
)
def test_a_run_fails_at_the_scripted_step_with_the_scripted_type(
    failure: type[EngineError],
) -> None:
    """A caller distinguishes these by type and never by reading a message, so
    the fake has to be able to raise each of them on demand."""
    recorder = _Recorder()
    with pytest.raises(failure, match="fail at step 3 of 5"):
        FakeEngine(Script(steps=5, fail_at_step=3, failure=failure)).run(
            _request(), progress=recorder
        )
    assert recorder.calls == [(1, 5), (2, 5)]


def test_a_run_blocks_at_the_scripted_step_until_it_is_released() -> None:
    """A job held on the device is what a timeout, a shutdown and a forced
    termination are all tested against."""
    released = threading.Event()
    reached = threading.Event()
    subject = FakeEngine(Script(steps=2, block_at_step=2, released=released))

    class _Reached(_Recorder):
        def __call__(self, step: int, total: int) -> None:
            super().__call__(step, total)
            reached.set()

    recorder = _Reached()
    produced: list[ImageBuffer] = []
    runner = threading.Thread(
        target=lambda: produced.append(subject.run(_request(), progress=recorder))
    )
    runner.start()
    assert reached.wait(timeout=5)
    assert not runner.join(timeout=0.05) and runner.is_alive()
    released.set()
    runner.join(timeout=5)
    assert not runner.is_alive()
    assert len(produced) == 1


def test_a_block_nothing_releases_fails_rather_than_hanging_the_run() -> None:
    """A suite that can hang is one somebody eventually runs with the hang
    ignored. The timeout is on the script so this arm costs milliseconds."""
    script = Script(
        block_at_step=1, released=threading.Event(), block_timeout_seconds=0
    )
    with pytest.raises(EngineFailure, match="nothing released it"):
        FakeEngine(script).run(_request())


def test_a_script_that_blocks_with_nothing_to_release_it_is_refused() -> None:
    with pytest.raises(ValueError, match="block_at_step"):
        Script(block_at_step=1)


def test_a_script_with_no_steps_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one step"):
        Script(steps=0)


def test_an_unsupported_operation_is_refused() -> None:
    subject = FakeEngine(Script(operations=frozenset({Operation.ERASE})))
    with pytest.raises(UnsupportedRequest, match="does not support the fill"):
        subject.run(_request(Operation.FILL))


def test_a_prompt_an_engine_would_ignore_is_refused_rather_than_ignored() -> None:
    """Silent approximation is the failure this half of the contract exists to
    prevent: a caller who sent a prompt to an engine that ignores prompts gets a
    plausible result that is not what they asked for."""
    with pytest.raises(UnsupportedRequest, match="uses_prompt false"):
        FakeEngine().run(_request(prompt="remove the car"))


def test_a_prompt_is_accepted_where_the_engine_declares_one() -> None:
    subject = FakeEngine(Script(uses_prompt=True))
    assert subject.run(_request(prompt="remove the car")).width == 4


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (4, 128, "accepts a height between"),
        (128, 4, "accepts a width between"),
        (6, 8, "multiple of"),
        (8, 6, "multiple of"),
    ],
)
def test_a_size_outside_the_declaration_is_refused(
    width: int, height: int, expected: str
) -> None:
    """Both sides and both kinds of limit. A rule written over one side passes
    every test that only ever varies the other."""
    subject = FakeEngine(
        Script(sizes=SizeConstraint(min_side=2, max_side=64, multiple_of=4))
    )
    with pytest.raises(UnsupportedRequest, match=expected):
        subject.estimate_device_memory(_job(width=width, height=height))


def test_a_prompt_the_engine_does_not_take_is_refused_at_estimate_too() -> None:
    with pytest.raises(UnsupportedRequest, match="uses_prompt false"):
        FakeEngine().estimate_device_memory(_job(has_prompt=True))


def test_an_image_shorter_than_its_declared_shape_is_refused() -> None:
    request = EditRequest(
        operation=Operation.ERASE,
        image=ImageBuffer(data=b"\x00" * 11, width=4, height=3, channels=3),
        mask=_mask(),
    )
    with pytest.raises(UnsupportedRequest, match="carrying 11"):
        FakeEngine().run(request)


def test_a_mask_of_another_size_than_the_image_is_refused() -> None:
    request = EditRequest(
        operation=Operation.ERASE,
        image=_image(),
        mask=MaskBuffer(data=b"\x00" * 4, width=2, height=2),
    )
    with pytest.raises(UnsupportedRequest, match="2x2 mask for a 4x3 image"):
        FakeEngine().run(request)


def test_a_mask_shorter_than_its_declared_shape_is_refused() -> None:
    request = EditRequest(
        operation=Operation.ERASE,
        image=_image(),
        mask=MaskBuffer(data=b"\x00" * 11, width=4, height=3),
    )
    with pytest.raises(UnsupportedRequest, match="carrying 11"):
        FakeEngine().run(request)


def test_a_parameter_the_engine_does_not_know_is_refused() -> None:
    with pytest.raises(UnsupportedRequest, match="guidance, sampler"):
        FakeEngine().run(_request(parameters={"sampler": "ddim", "guidance": "7"}))


def test_a_declared_parameter_is_accepted() -> None:
    subject = FakeEngine(Script(known_parameters=frozenset({"sampler"})))
    assert subject.run(_request(parameters={"sampler": "ddim"})).height == 3


def test_a_request_asking_for_another_step_count_is_refused() -> None:
    """The step count is what the script decided. A request quietly winning
    would make an assertion about progress depend on which number arrived
    last."""
    with pytest.raises(UnsupportedRequest, match="scripted for 2 step"):
        FakeEngine().run(_request(steps=9))


def test_a_request_naming_the_scripted_step_count_is_served() -> None:
    recorder = _Recorder()
    FakeEngine(Script(steps=3)).run(_request(steps=3), progress=recorder)
    assert recorder.calls == [(1, 3), (2, 3), (3, 3)]
