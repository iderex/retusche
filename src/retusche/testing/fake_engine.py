# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""An engine that edits pixels with no device, driven by a script.

It is not a mock configured per test. It is a real implementation of the
interface in ``retusche_contracts`` whose behaviour is decided once, before the
run, by a `Script` value. A mock configured inside the test that asserts on it
tends to become a mirror of the code under test: it is told what to return by
the same reasoning that decides what is correct, so the pair agrees with itself
and proves nothing. A scripted implementation is told what to do and not what
the caller should conclude.

This module imports the standard library and the contract package, and nothing
else. That is what lets the orchestration layer be exercised end to end in a
process where a machine-learning runtime may not be reachable by any import
chain, which is the arrangement ``tests/test_import_boundary.py`` holds.

What the script can be told to do
--------------------------------
Succeed after a stated number of steps, report progress at each of them, answer
an arbitrary device-memory estimate so a budget can be driven either side of its
limit, fail at a named step with a named failure type, block at a named step
until the test releases it, and ignore cancellation so that the caller's
forced-termination path has something to force.

Determinism
-----------
The result is a function of the request alone: the same request produces the
same bytes, and a request differing in the seed, the prompt, the operation, the
shape or a single input byte produces different ones. Nothing samples a clock or
a random source, so a test may assert on the bytes rather than on their length.

Pixels the mask leaves at zero are copied from the input unchanged, and the
synthesised content is derived from the whole request rather than from the
pixel it replaces. Both are properties the contract suite in #16 is written to
assert against every engine, and an engine which is easy to pass by accident is
one the suite cannot be trusted on.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from typing import Final

from retusche_contracts import (
    CancellationToken,
    Cancelled,
    Capabilities,
    DeviceMemoryEstimate,
    EditRequest,
    EngineError,
    EngineFailure,
    ImageBuffer,
    JobDescription,
    Operation,
    ProgressCallback,
    SizeConstraint,
    UnsupportedRequest,
)

__all__ = ["FakeEngine", "Script"]

_EVERY_OPERATION: Final = frozenset(Operation)

_NO_PARAMETERS: Final[frozenset[str]] = frozenset()

# Permissive by default. A fake whose default declaration refused an ordinary
# small image would make every test about something else begin by satisfying a
# constraint that is not what it is testing, and a constraint nobody sets on
# purpose is one nobody reads. A test about refusal scripts its own.
_ANY_SIZE: Final = SizeConstraint(min_side=1, max_side=4096, multiple_of=1)

# What one pixel is assumed to cost on the device, where the script names no
# estimate of its own. A made-up number, and it is here rather than inside the
# method so that a test reading the estimate can say where the number came from.
_BYTES_PER_PIXEL_ON_THE_DEVICE: Final = 4

# How far `Operation.EXTEND` grows the canvas, on every side. The contract says
# an extend returns a buffer larger than the one it was given and that the
# caller learns the new size from the buffer, so the fake has to grow it by
# something; this is that something, fixed rather than scripted because no test
# so far needs two different values and a field nobody varies is a field nobody
# checks.
_EXTEND_BORDER: Final = 4


@dataclass(frozen=True, slots=True)
class Script:
    """What the fake will do, decided before the run rather than during it."""

    engine_id: str = "fake"
    """What the engine calls itself in a capability declaration and in the
    message of every refusal it raises."""

    operations: frozenset[Operation] = _EVERY_OPERATION
    """The operations this fake admits. Anything else is refused."""

    sizes: SizeConstraint = _ANY_SIZE
    """The sizes this fake admits, declared and enforced by the same value."""

    uses_prompt: bool = False
    """Whether a prompt is accepted. False refuses a request carrying one, which
    is the contract's position: a prompt that had no effect is worse than a
    refusal because nothing tells the caller it had none."""

    known_parameters: frozenset[str] = _NO_PARAMETERS
    """Engine-specific parameter names this fake recognises. A key outside the
    set is refused rather than dropped."""

    steps: int = 2
    """How many steps a run takes. One means the work is not divided, which is
    what `Capabilities.step_count_is_one` is derived from."""

    device_memory_bytes: int | None = None
    """The estimate to answer, whatever the job. None derives one from the job's
    shape instead. This is the lever a test uses to drive an admission budget
    from either side without inventing an image big enough to do it honestly."""

    estimate_is_measured: bool = False
    """What the estimate claims about its own provenance."""

    fail_at_step: int | None = None
    """The step at which the run raises `failure`, counting from one. The
    failure is raised before progress is reported for that step, so a caller
    that saw progress for step N knows step N completed."""

    failure: type[EngineError] = EngineFailure
    """Which failure `fail_at_step` raises. Every member of the contract's
    closed set is constructible from a message, so any of them can be scripted
    and a caller's handling of each can be exercised."""

    honours_cancellation: bool = True
    """False keeps running with the token set, which is the engine the queue's
    forced-termination path exists for. Nothing else in the suite can produce
    that case, because an engine that honours cancellation makes it
    unreachable."""

    block_at_step: int | None = None
    """The step at which the run blocks until `released` is set. The block
    happens before the cancellation check for that step, so a test can hold a
    run on the device, cancel it, and then let it discover that."""

    released: threading.Event | None = None
    """What ends the block. Required where `block_at_step` is set."""

    block_timeout_seconds: float = 30.0
    """How long the block waits before raising `EngineFailure` instead. A test
    that forgets to release would otherwise hang the whole run, and a suite that
    can hang is one somebody eventually runs with the hang ignored."""

    def __post_init__(self) -> None:
        """Refuse a script that cannot mean anything, where it is written.

        A script is written once and read by every step of a run. A
        contradiction found at step three is reported from inside the engine,
        where it looks like the engine's fault; found here it is reported at the
        line that wrote it.
        """
        if self.steps < 1:
            message = f"a run takes at least one step, not {self.steps}"
            raise ValueError(message)
        if self.block_at_step is not None and self.released is None:
            message = (
                "block_at_step names a step to block at and released names what "
                "ends the block. A script setting the first and not the second "
                "would block for block_timeout_seconds and then fail, which is "
                "not what anybody writing it meant."
            )
            raise ValueError(message)


_DEFAULT_SCRIPT: Final = Script()


class FakeEngine:
    """The contract's whole interface, over a script and no device."""

    def __init__(self, script: Script = _DEFAULT_SCRIPT) -> None:
        self._script = script

    def capabilities(self) -> Capabilities:
        """What the script says this engine is, answered without loading
        anything. Stable for the lifetime of the instance because the script is
        frozen and is not replaced after construction."""
        script = self._script
        return Capabilities(
            engine_id=script.engine_id,
            operations=script.operations,
            sizes=script.sizes,
            uses_prompt=script.uses_prompt,
            step_count_is_one=script.steps == 1,
        )

    def estimate_device_memory(self, job: JobDescription) -> DeviceMemoryEstimate:
        """What the job would cost on the device, answered from its shape.

        Refuses a job the fake would refuse anyway, so that a queue asking about
        a job it may never admit learns it is unservable before a lane is spent
        on it.
        """
        script = self._script
        self._refuse_undeclared(job.operation, job.width, job.height, job.has_prompt)
        peak = script.device_memory_bytes
        if peak is None:
            peak = job.width * job.height * _BYTES_PER_PIXEL_ON_THE_DEVICE
        return DeviceMemoryEstimate(
            peak_bytes=peak, is_measured=script.estimate_is_measured
        )

    def run(
        self,
        request: EditRequest,
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
    ) -> ImageBuffer:
        """Perform the scripted edit and return the result.

        The step loop is the whole of the fake's behaviour over time: at each
        step it blocks if told to, observes cancellation if it honours it, fails
        if told to, and otherwise reports progress. Everything a caller can time,
        interrupt or lose a job to happens at one of those four points.
        """
        script = self._script
        self._refuse_undeclared(
            request.operation,
            request.image.width,
            request.image.height,
            request.prompt is not None,
        )
        self._refuse_incoherent(request)
        total = self._step_count(request)
        for step in range(1, total + 1):
            self._hold(step)
            if (
                script.honours_cancellation
                and cancellation is not None
                and cancellation.is_cancelled
            ):
                message = (
                    f"{script.engine_id} observed cancellation at step {step} of "
                    f"{total} and produced no image"
                )
                raise Cancelled(message)
            if step == script.fail_at_step:
                message = (
                    f"{script.engine_id} was scripted to fail at step {step} of {total}"
                )
                raise script.failure(message)
            if progress is not None:
                progress(step, total)
        return _synthesise(request)

    def _refuse_undeclared(
        self, operation: Operation, width: int, height: int, has_prompt: bool
    ) -> None:
        """Refuse what the capability declaration says this engine does not do.

        One place, reached from both `estimate_device_memory` and `run`, because
        an engine that estimates a job it would later refuse tells the queue a
        job is servable and then takes the lane to say otherwise.
        """
        script = self._script
        if operation not in script.operations:
            message = (
                f"{script.engine_id} does not support the {operation.value} "
                f"operation, only "
                f"{', '.join(sorted(each.value for each in script.operations))}"
            )
            raise UnsupportedRequest(message)
        if has_prompt and not script.uses_prompt:
            message = (
                f"{script.engine_id} declares uses_prompt false, so a prompt "
                f"would have no effect on the result and the request is refused "
                f"rather than served without it"
            )
            raise UnsupportedRequest(message)
        sizes = script.sizes
        for side, name in ((width, "width"), (height, "height")):
            if not sizes.min_side <= side <= sizes.max_side:
                message = (
                    f"{script.engine_id} accepts a {name} between "
                    f"{sizes.min_side} and {sizes.max_side} pixels, not {side}"
                )
                raise UnsupportedRequest(message)
            if side % sizes.multiple_of:
                message = (
                    f"{script.engine_id} accepts a {name} that is a multiple of "
                    f"{sizes.multiple_of} pixels, and {side} is not one"
                )
                raise UnsupportedRequest(message)

    def _refuse_incoherent(self, request: EditRequest) -> None:
        """Refuse buffers whose declared shape and length disagree.

        The fake's whole value is that its output is predictable from its input.
        A buffer holding fewer bytes than its shape claims has no predictable
        output, and producing one anyway would put the fake's own arithmetic
        rather than the engine's behaviour under the test's assertion.
        """
        script = self._script
        image = request.image
        declared = image.width * image.height * image.channels
        if len(image.data) != declared:
            message = (
                f"{script.engine_id} was given an image declaring "
                f"{image.width}x{image.height} at {image.channels} channels, "
                f"which is {declared} bytes, and carrying {len(image.data)}"
            )
            raise UnsupportedRequest(message)
        mask = request.mask
        if (mask.width, mask.height) != (image.width, image.height):
            message = (
                f"{script.engine_id} was given a "
                f"{mask.width}x{mask.height} mask for a "
                f"{image.width}x{image.height} image"
            )
            raise UnsupportedRequest(message)
        if len(mask.data) != mask.width * mask.height:
            message = (
                f"{script.engine_id} was given a mask declaring "
                f"{mask.width}x{mask.height}, which is "
                f"{mask.width * mask.height} bytes, and carrying "
                f"{len(mask.data)}"
            )
            raise UnsupportedRequest(message)
        unknown = sorted(set(request.parameters or ()) - script.known_parameters)
        if unknown:
            message = (
                f"{script.engine_id} does not recognise the parameter(s) "
                f"{', '.join(unknown)}, and a parameter that reached an engine "
                f"which ignores it is a setting the caller believes took effect"
            )
            raise UnsupportedRequest(message)

    def _step_count(self, request: EditRequest) -> int:
        """How many steps this run takes, which is what the script says.

        A request naming a different count is refused rather than obeyed. The
        step count is the thing a test scripted, and letting the request win
        would make an assertion about progress depend on which of two numbers
        reached the engine last.
        """
        script = self._script
        if request.steps is not None and request.steps != script.steps:
            message = (
                f"{script.engine_id} is scripted for {script.steps} step(s) and "
                f"the request asks for {request.steps}"
            )
            raise UnsupportedRequest(message)
        return script.steps

    def _hold(self, step: int) -> None:
        """Block at the scripted step until the test releases the run."""
        script = self._script
        released = script.released
        if step != script.block_at_step or released is None:
            return
        if not released.wait(timeout=script.block_timeout_seconds):
            message = (
                f"{script.engine_id} was scripted to block at step {step} and "
                f"nothing released it within {script.block_timeout_seconds} "
                f"seconds"
            )
            raise EngineFailure(message)


def _synthesise(request: EditRequest) -> ImageBuffer:
    """The result: input pixels where the mask is zero, derived bytes elsewhere.

    An extend grows the canvas by `_EXTEND_BORDER` on every side and the added
    border is derived content, because there is no input pixel behind it. The
    original frame is placed in the centre and keeps whatever the mask left
    alone, so the unchanged-pixels property holds for an extend as well.
    """
    image = request.image
    mask = request.mask
    border = _EXTEND_BORDER if request.operation is Operation.EXTEND else 0
    width = image.width + 2 * border
    height = image.height + 2 * border
    pixels = bytearray(
        hashlib.shake_256(_material(request, width, height)).digest(
            width * height * image.channels
        )
    )
    for row in range(image.height):
        source_row = row * image.width
        target_row = (row + border) * width + border
        for column in range(image.width):
            if mask.data[source_row + column]:
                continue
            source = (source_row + column) * image.channels
            target = (target_row + column) * image.channels
            pixels[target : target + image.channels] = image.data[
                source : source + image.channels
            ]
    return ImageBuffer(
        data=bytes(pixels), width=width, height=height, channels=image.channels
    )


def _material(request: EditRequest, width: int, height: int) -> bytes:
    """Everything the derived content is a function of, in one string of bytes.

    Each part is prefixed with its own length, so no two different requests can
    be flattened to the same material by moving a byte across a boundary: a
    prompt ending in what the next part begins with is the shape that would
    otherwise collide.
    """
    parts = (
        request.operation.value.encode(),
        str(request.seed).encode(),
        (request.prompt or "").encode(),
        f"{width}x{height}x{request.image.channels}".encode(),
        request.image.data,
        request.mask.data,
    )
    digest = hashlib.blake2b()
    for part in parts:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.digest()
