"""The one interface every engine is reached through.

An engine is whatever actually edits pixels: the erase model, a diffusion
model, the fake used in tests, and any later adapter to an external
application. They differ in almost everything and agree here, because the
queue has to schedule them without knowing which one it holds.

This module imports the standard library and nothing else. That is not tidiness:
the orchestration layer is typed and tested against these declarations, and it
runs in the process that listens on a socket, where a machine-learning runtime
may not be reachable by any import chain. Issue #7 builds the test that refuses
such a chain.

Images cross the boundary as raw bytes with their shape stated alongside, rather
than as a library's array or image object. An array type would put a numeric
runtime in the contract, and every process importing the contract would inherit
it.

Cancellation
------------
Cancellation is cooperative and its granularity is a step boundary. An engine
checks the token before each step and stops there; a caller that cancels
observes the stop after at most one step completes, never mid-step.

For an engine whose work is not divided into steps, and the erase family is such
an engine, the worst case is the whole run. Such an engine declares
``step_count_is_one`` in its capabilities, and a caller that needs a bound on
cancellation latency reads it there rather than assuming one. The interface does
not promise that a cancelled run is cheap; it promises that it is observed and
that no result is produced.

Memory
------
``estimate_device_memory`` is asked before a job is admitted, not after it
fails. Recovering from an out-of-memory failure means the device has already
been driven into a state where an allocation failed, and on the shared device
this project targets that state is not private to the failing job: a photo
library, a transcoder or a desktop session sharing the card can be the thing
that dies instead. Admission control that refuses beforehand keeps the failure
inside the job that caused it. `docs/engine-interface.md` carries the longer
form of that argument.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "CancellationToken",
    "Cancelled",
    "Capabilities",
    "DeviceMemoryEstimate",
    "EditRequest",
    "Engine",
    "EngineError",
    "EngineFailure",
    "ImageBuffer",
    "JobDescription",
    "MaskBuffer",
    "ModelNotAvailable",
    "Operation",
    "OutOfDeviceMemory",
    "ProgressCallback",
    "SizeConstraint",
    "UnsupportedRequest",
]


class Operation(enum.StrEnum):
    """What an engine is being asked to do."""

    ERASE = "erase"
    """Remove what the mask covers and reconstruct what was behind it."""

    FILL = "fill"
    """Synthesise new content inside the mask, optionally from a prompt."""

    EXTEND = "extend"
    """Synthesise content outside the original frame, into an added border."""


@dataclass(frozen=True, slots=True)
class SizeConstraint:
    """The image sizes an engine accepts, in pixels.

    ``multiple_of`` exists because most of these models are built on an encoder
    that halves the resolution a fixed number of times, so a side that is not a
    multiple of that factor is silently rounded somewhere inside the pipeline
    and the result comes back a few pixels off. Stating the factor lets the
    caller decide how to reach it rather than discovering the rounding later.
    """

    min_side: int
    max_side: int
    multiple_of: int


@dataclass(frozen=True, slots=True)
class Capabilities:
    """What an engine can do, asked before anything is sent to it.

    A capability declaration is expected to be stable for the lifetime of an
    engine instance: the queue reads it to decide admission, and a declaration
    that changed between two calls would make those decisions unrepeatable.
    """

    engine_id: str
    """Stable identifier for this engine, used in logs and failure messages."""

    operations: frozenset[Operation]
    """The operations this engine supports. Anything else is refused."""

    sizes: SizeConstraint
    """The image sizes accepted, for every supported operation."""

    uses_prompt: bool
    """Whether a text prompt affects the result. False means a prompt is refused
    rather than ignored, so a caller is never left believing it had an effect."""

    step_count_is_one: bool
    """True where the work is not divided into steps, so cancellation cannot be
    observed before the whole run completes. See the module docstring."""


@dataclass(frozen=True, slots=True)
class ImageBuffer:
    """Raw pixels with their shape stated alongside.

    ``data`` holds ``height * width * channels`` bytes, row major, eight bits
    per channel. Nothing here decodes a file format: decoding happens at the
    edge, where the bytes arrive from a stranger, and is #51's subject.
    """

    data: bytes
    width: int
    height: int
    channels: int


@dataclass(frozen=True, slots=True)
class MaskBuffer:
    """A single-channel mask, ``height * width`` bytes, row major.

    Zero means leave the pixel alone. Any non-zero value means the pixel is
    inside the edit. What the values between mean is #46's subject, not this
    interface's.
    """

    data: bytes
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class JobDescription:
    """Enough of a job to estimate its cost, without carrying its pixels.

    The queue holds one of these per waiting job. Carrying the image bytes here
    would mean the whole backlog sits in the orchestration process's memory to
    answer a question about the device's.
    """

    operation: Operation
    width: int
    height: int
    has_prompt: bool
    steps: int


@dataclass(frozen=True, slots=True)
class DeviceMemoryEstimate:
    """What a job is expected to need on the device.

    ``peak_bytes`` is an upper bound the engine is willing to be held to, not an
    average. ``is_measured`` says whether it comes from a measurement or from a
    formula over the job's shape; an estimate that was never measured is still
    usable for admission and a caller may want to know which it has.
    """

    peak_bytes: int
    is_measured: bool


@dataclass(frozen=True, slots=True)
class EditRequest:
    """One edit, complete."""

    operation: Operation
    image: ImageBuffer
    mask: MaskBuffer
    prompt: str | None = None
    steps: int | None = None
    seed: int | None = None
    parameters: Mapping[str, str] | None = None
    """Engine-specific settings. A key an engine does not recognise is refused
    as an unsupported request rather than dropped, so a caller cannot believe a
    setting took effect."""


@runtime_checkable
class ProgressCallback(Protocol):
    """Called at each step boundary.

    ``step`` counts completed steps, from one, and ends at ``total``. ``total``
    is fixed for the run and equals the declared step count, so a caller can
    show a bounded bar rather than a spinner. Progress never moves backwards.
    """

    def __call__(self, step: int, total: int) -> None: ...


@runtime_checkable
class CancellationToken(Protocol):
    """Read by the engine at each step boundary.

    Once ``is_cancelled`` returns True it keeps returning True. An engine that
    sees it raises `Cancelled` and produces no image.
    """

    @property
    def is_cancelled(self) -> bool: ...


class EngineError(Exception):
    """Base of every failure an engine is allowed to raise.

    A caller distinguishes the cases below by type. Nothing in the orchestration
    layer is expected to read a message string to decide what to do, because a
    message is prose and prose is what changes without anyone noticing.
    """


class UnsupportedRequest(EngineError):
    """The request asks for something this engine does not do.

    The operation, the image size, a prompt where none is used, or a parameter
    the engine does not recognise. This is refusal, not failure: retrying it
    unchanged against the same engine fails again.
    """


class OutOfDeviceMemory(EngineError):
    """The device could not allocate what the job needed.

    Raised where admission control was wrong or the device was shared with
    something that grew. #31 owns what the queue does about it.
    """


class ModelNotAvailable(EngineError):
    """The weights this engine needs are not present or not usable.

    Not downloaded, failed verification, or their licence has not been accepted.
    Distinct from `UnsupportedRequest` because the request is fine and the
    machine is not.
    """


class Cancelled(EngineError):
    """The run stopped because the cancellation token was set.

    No image is produced. Raised at the step boundary where the token was
    observed.
    """


class EngineFailure(EngineError):
    """The engine broke for a reason none of the other types names.

    A caller may log it and fail the job. A caller may not infer anything about
    whether a retry would help.
    """


@runtime_checkable
class Engine(Protocol):
    """The whole interface. Everything that edits pixels implements this."""

    def capabilities(self) -> Capabilities:
        """What this engine can do. Stable for the lifetime of the instance,
        and answerable without loading weights."""
        ...

    def estimate_device_memory(self, job: JobDescription) -> DeviceMemoryEstimate:
        """The device memory this job is expected to need, at its peak.

        Answered without loading weights and without touching the device, so
        that the queue can ask about a job it may never admit.

        Raises `UnsupportedRequest` where the described job is one this engine
        would refuse anyway; the queue then refuses it before it reaches a lane.
        """
        ...

    def run(
        self,
        request: EditRequest,
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
    ) -> ImageBuffer:
        """Perform the edit and return the result.

        The returned buffer has the same width, height and channel count as
        ``request.image`` for `Operation.ERASE` and `Operation.FILL`. For
        `Operation.EXTEND` it is larger, and the caller learns the new size from
        the returned buffer rather than computing it.

        Raises one of `UnsupportedRequest`, `OutOfDeviceMemory`,
        `ModelNotAvailable`, `Cancelled` or `EngineFailure`, and nothing else.
        """
        ...
