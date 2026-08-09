# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The clauses every engine has to meet, with no pytest and no register in them.

Kept apart from the wiring for the reason `harness_rules` is: given an engine and
nothing else, a clause can be exercised against an engine built to break it, so
each refusal is seen on purpose rather than on the day somebody trips it.
`test_the_suite_bites.py` is where that happens and `test_the_contract.py` is
where these run against the register.

Every clause takes an `EngineCase` and returns one of three things. None, which
is a pass. A string, which is what is wrong. Or a `NotApplicable`, which is the
clause saying it had nothing to ask this engine and why. The third is not folded
into the first because a clause that was not asked and a clause that passed are
different states, and a run printing the same thing for both would be
unreadable.

What a clause may read to decide what to send
---------------------------------------------
The capability declaration, and nothing else. That is the whole of the rule
against engine-specific branches: an engine declaring two operations is asked
about two, an engine whose work is not divided into steps is not asked to
observe a mid-run cancellation, and neither of those is a clause knowing which
engine it holds. `EngineCase` carries one number the declaration does not, the
tolerance below, and that is data an engine's own entry supplies rather than a
branch in a clause.

An engine that refuses a request its own declaration admits is reported as
broken rather than skipped. The declaration is the only thing this suite has to
go on, so a declaration that does not hold is the finding and not an exemption
from one.

What these clauses do not reach
-------------------------------
The result of an edit, beyond the pixels a zero mask leaves alone. Whether an
erase removed the object is a judgement about an image and no assertion here
makes it. What is held is the shape of the conversation between the queue and an
engine: what is declared, what is refused, what progress means, and what
cancelling does.

The extend operation is also outside every clause below except the refusal one.
An extend returns a larger canvas and the interface declares no border, so
locating the original frame inside a result is not something a clause can do
from the declaration alone.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from retusche_contracts import (
    Cancelled,
    Capabilities,
    EditRequest,
    EngineError,
    ImageBuffer,
    JobDescription,
    MaskBuffer,
    Operation,
    SizeConstraint,
    UnsupportedRequest,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping

    from retusche_contracts import Engine

__all__ = [
    "CANCELLATION_BOUND_IN_STEPS",
    "CLAUSES",
    "EngineCase",
    "NotApplicable",
]

# The bound this suite holds cancellation to, in completed steps observed after
# the token first reports cancelled. The interface says an engine checks the
# token at each step boundary and stops there, so at most one step completes
# between the token turning and the stop. An engine whose work is not divided
# into steps declares `step_count_is_one` and is not asked this question at all.
CANCELLATION_BOUND_IN_STEPS: Final = 1

# The side this suite asks for where the declaration leaves it free. Large enough
# that a mask has an inside and an outside and a truncation is visible, small
# enough that a run costs nothing.
_PREFERRED_SIDE: Final = 8

# Channels in every image this suite sends. The interface states the byte layout
# and says nothing about which channel counts an engine takes, so this is a
# choice rather than a derivation, and an engine accepting only a different one
# refuses the request and the clause reports the refusal.
_CHANNELS: Final = 3

# Preference order where a clause needs one operation and the engine declares
# several. Fixed so two runs of this suite send the same request.
_OPERATION_ORDER: Final = (Operation.ERASE, Operation.FILL, Operation.EXTEND)

# The operations whose result has the same shape as the input, per the interface.
_SHAPE_PRESERVING: Final = (Operation.ERASE, Operation.FILL)


@dataclass(frozen=True, slots=True)
class NotApplicable:
    """This clause had nothing to ask this engine, and here is why."""

    reason: str


@dataclass(frozen=True, slots=True)
class EngineCase:
    """One engine this suite runs against, and what its entry has to declare."""

    name: str
    """How the engine is named in a failure message. Checked against the
    `engine_id` the engine declares, so the two cannot drift apart."""

    build: Callable[[], Engine]
    """Makes a fresh instance. Called per clause rather than once, because a
    clause that left an engine mid-run would decide the next clause's verdict."""

    unchanged_tolerance: int = 0
    """The largest per-channel difference this engine may show on a pixel its
    mask left at zero. Zero for an engine that copies such pixels. A diffusion
    engine round-tripping the whole frame through an encoder does not, and its
    own entry states by how much rather than this suite guessing for it."""


def capabilities_are_stable_across_calls(
    case: EngineCase, forbidden_roots: Collection[str]
) -> str | NotApplicable | None:
    """The queue reads the declaration to decide admission.

    A declaration that moved between two reads would make those decisions
    unrepeatable: the same job admitted at one moment and refused at the next,
    with nothing in the job to explain it. The interface says stable for the
    lifetime of the instance, so a run in between is part of that lifetime.
    """
    del forbidden_roots
    engine = case.build()
    first = engine.capabilities()
    second = engine.capabilities()
    if first != second:
        return (
            f"two consecutive calls to capabilities() returned different "
            f"declarations: {first!r} then {second!r}"
        )
    request = _smallest_request(first)
    if isinstance(request, str):
        return request
    try:
        engine.run(request)
    except EngineError as failure:
        return _refused_its_own_declaration(request, failure)
    after = engine.capabilities()
    if after != first:
        return f"capabilities() changed across one run: {first!r} then {after!r}"
    return None


def an_estimate_arrives_without_loading_weights(
    case: EngineCase, forbidden_roots: Collection[str]
) -> str | NotApplicable | None:
    """Admission asks about jobs it will never admit, so asking must be cheap.

    Cheap is not measurable here and loading a runtime is. The check is that no
    module root standing for a machine-learning runtime arrives in `sys.modules`
    during the call, which catches the engine deferring its import into the
    estimate.

    Its bound, stated rather than left to be discovered: a runtime already
    imported by the time this runs cannot arrive again, so in a process holding
    one this clause sees nothing and says nothing. It is a floor.
    """
    engine = case.build()
    declaration = engine.capabilities()
    operation = _first_operation(declaration)
    if operation is None:
        return _declares_no_operation(declaration)
    side = _admissible_side(declaration.sizes)
    if side is None:
        return _no_admissible_side(declaration.sizes)
    job = JobDescription(
        operation=operation, width=side, height=side, has_prompt=False, steps=1
    )
    before = frozenset(sys.modules)
    estimate = engine.estimate_device_memory(job)
    arrived = {name.split(".")[0] for name in frozenset(sys.modules) - before}
    offending = sorted(arrived & set(forbidden_roots))
    if offending:
        return (
            f"estimating a {side}x{side} {operation.value} imported "
            f"{', '.join(offending)}, so the queue cannot ask about a job "
            f"without paying for the runtime that would serve it"
        )
    if estimate.peak_bytes <= 0:
        return (
            f"estimated {estimate.peak_bytes} bytes for a {side}x{side} "
            f"{operation.value}, and a job declared to cost nothing on the "
            f"device is one a memory budget admits without limit"
        )
    return None


def a_zero_mask_leaves_the_image_unchanged(
    case: EngineCase, forbidden_roots: Collection[str]
) -> str | NotApplicable | None:
    """A mask of zeroes says leave every pixel alone.

    An engine returning a re-encoded frame for an edit nobody asked for makes
    every later assertion about an edit unreadable, because the difference
    between the pixels it was told to change and the pixels it changed anyway is
    exactly what a caller is looking at.
    """
    del forbidden_roots
    engine = case.build()
    declaration = engine.capabilities()
    operations = [
        operation
        for operation in _SHAPE_PRESERVING
        if operation in declaration.operations
    ]
    if not operations:
        return NotApplicable(
            "the engine declares neither erase nor fill, and only those two "
            "return a canvas of the same shape as the one they were given"
        )
    side = _admissible_side(declaration.sizes)
    if side is None:
        return _no_admissible_side(declaration.sizes)
    image = _image(side, side)
    mask = _mask(side, side, 0)
    problems = []
    for operation in operations:
        request = EditRequest(operation=operation, image=image, mask=mask)
        try:
            result = engine.run(request)
        except EngineError as failure:
            problems.append(
                f"{operation.value} refused a mask of zeroes over an image its "
                f"own declaration admits, with {type(failure).__name__}: "
                f"{failure}"
            )
            continue
        problems.extend(_unchanged_problems(operation, image, result, case))
    return "; ".join(problems) or None


def a_full_mask_is_handled_or_refused(
    case: EngineCase, forbidden_roots: Collection[str]
) -> str | NotApplicable | None:
    """A mask covering everything is a real request, and refusing it is an answer.

    What is not an answer is a smaller canvas. A caller that asked for the whole
    frame and was handed part of it has no way to tell that from an engine that
    did the work, and the loss surfaces wherever the result is written back.
    """
    del forbidden_roots
    engine = case.build()
    declaration = engine.capabilities()
    operation = _first_operation(declaration)
    if operation is None:
        return _declares_no_operation(declaration)
    side = _admissible_side(declaration.sizes)
    if side is None:
        return _no_admissible_side(declaration.sizes)
    image = _image(side, side)
    request = EditRequest(
        operation=operation, image=image, mask=_mask(side, side, 0xFF)
    )
    try:
        result = engine.run(request)
    except UnsupportedRequest:
        return None
    except EngineError as failure:
        return (
            f"a mask covering the whole image failed with "
            f"{type(failure).__name__}, which is neither handling it nor "
            f"refusing it as unsupported: {failure}"
        )
    declared = result.width * result.height * result.channels
    if len(result.data) != declared:
        return (
            f"returned a buffer declaring {result.width}x{result.height} at "
            f"{result.channels} channels, which is {declared} bytes, and "
            f"carrying {len(result.data)}"
        )
    if result.width < image.width or result.height < image.height:
        return (
            f"returned a {result.width}x{result.height} canvas for a "
            f"{image.width}x{image.height} image, which is the silent "
            f"truncation this clause exists to refuse"
        )
    if result.channels != image.channels:
        return (
            f"returned {result.channels} channels for a {image.channels} channel image"
        )
    return None


def progress_is_monotonic_and_ends_at_the_total(
    case: EngineCase, forbidden_roots: Collection[str]
) -> str | NotApplicable | None:
    """A caller shows a bounded bar, which only works if the bound holds.

    The interface fixes `total` for the run, counts completed steps from one,
    and says progress never moves backwards. It also ties the declaration to the
    count: `step_count_is_one` and a total of two are a contradiction, and so is
    the other direction, where a declaration promises a boundary the run has
    not got.
    """
    del forbidden_roots
    engine = case.build()
    declaration = engine.capabilities()
    request = _smallest_request(declaration)
    if isinstance(request, str):
        return request
    calls: list[tuple[int, int]] = []
    try:
        engine.run(request, lambda step, total: calls.append((step, total)))
    except EngineError as failure:
        return _refused_its_own_declaration(request, failure)
    if not calls:
        return "a run that completed reported no progress at all"
    totals = sorted({total for _, total in calls})
    if len(totals) != 1:
        return f"total moved during one run, taking the values {totals}"
    total = totals[0]
    steps = [step for step, _ in calls]
    if steps != sorted(steps):
        return f"progress moved backwards, reporting steps {steps}"
    if steps[0] < 1:
        return f"progress started at step {steps[0]} rather than at one"
    if steps[-1] != total:
        return f"progress ended at step {steps[-1]} of a declared total of {total}"
    if declaration.step_count_is_one and total != 1:
        return (
            f"declares step_count_is_one and reported a total of {total}, so a "
            f"caller reading the declaration for a cancellation bound reads the "
            f"wrong one"
        )
    if not declaration.step_count_is_one and total < 2:
        return (
            f"declares step_count_is_one false and reported a total of {total}, "
            f"so the declaration promises a step boundary the run has not got"
        )
    return None


def cancelling_before_the_first_step_produces_no_image(
    case: EngineCase, forbidden_roots: Collection[str]
) -> str | NotApplicable | None:
    """A job cancelled while it waited must not reach the device at all.

    This is the case the queue relies on when a caller withdraws a job that has
    just been admitted. An engine starting anyway has spent a lane, and on a
    device shared with the rest of the host it has spent more than that.
    """
    del forbidden_roots
    engine = case.build()
    request = _smallest_request(engine.capabilities())
    if isinstance(request, str):
        return request
    calls: list[tuple[int, int]] = []
    try:
        result = engine.run(
            request,
            lambda step, total: calls.append((step, total)),
            _AlreadyCancelled(),
        )
    except Cancelled:
        if calls:
            return (
                f"raised Cancelled, correctly, but reported progress for "
                f"{len(calls)} step(s) first, so work was done for a job "
                f"cancelled before it started"
            )
        return None
    except EngineError as failure:
        return (
            f"a token already cancelled produced {type(failure).__name__} "
            f"rather than Cancelled, so a caller cannot tell a withdrawal from "
            f"a fault: {failure}"
        )
    return (
        f"a token already cancelled produced a {result.width}x{result.height} "
        f"image instead of raising Cancelled"
    )


def cancelling_mid_run_is_observed_within_the_bound(
    case: EngineCase, forbidden_roots: Collection[str]
) -> str | NotApplicable | None:
    """Cancellation is cooperative, so the bound is what makes it usable.

    The token here reports not-cancelled on its first read and cancelled on
    every read after it, which puts the cancellation inside the first step
    without the engine having to be scripted. An engine checking the token at
    each boundary observes it at the next one, so at most
    `CANCELLATION_BOUND_IN_STEPS` step completes after the token turns.
    """
    del forbidden_roots
    engine = case.build()
    declaration = engine.capabilities()
    if declaration.step_count_is_one:
        return NotApplicable(
            "the engine declares step_count_is_one, so the interface's worst "
            "case for it is the whole run and there is no mid-run boundary to "
            "observe one at"
        )
    request = _smallest_request(declaration)
    if isinstance(request, str):
        return request
    token = _CancelsAfterTheFirstRead()
    calls: list[tuple[int, int]] = []
    try:
        engine.run(request, lambda step, total: calls.append((step, total)), token)
    except Cancelled:
        if len(calls) > CANCELLATION_BOUND_IN_STEPS:
            return (
                f"observed cancellation only after {len(calls)} completed "
                f"step(s); the interface bounds it at "
                f"{CANCELLATION_BOUND_IN_STEPS}"
            )
        return None
    except EngineError as failure:
        return (
            f"a token that turned during the run produced "
            f"{type(failure).__name__} rather than Cancelled: {failure}"
        )
    if token.reads == 0:
        return (
            "ran to completion without reading the cancellation token once, so "
            "nothing a caller does can stop it"
        )
    return (
        f"ran to completion having read the cancellation token {token.reads} "
        f"time(s), and it reported cancelled from the second read onwards"
    )


def an_unsupported_request_is_refused_rather_than_approximated(
    case: EngineCase, forbidden_roots: Collection[str]
) -> str | NotApplicable | None:
    """A declaration nothing enforces is a declaration nothing can be built on.

    The request is one size step wider than the declared maximum, which every
    engine's own `SizeConstraint` says it does not take. Both entry points are
    asked, because an estimate answering for a job `run` refuses tells the queue
    the job is servable and then takes a lane to say otherwise.
    """
    del forbidden_roots
    engine = case.build()
    declaration = engine.capabilities()
    sizes = declaration.sizes
    operation = _first_operation(declaration)
    if operation is None:
        return _declares_no_operation(declaration)
    height = _admissible_side(sizes)
    if height is None:
        return _no_admissible_side(sizes)
    width = sizes.max_side + sizes.multiple_of
    problems = []
    request = EditRequest(
        operation=operation,
        image=_image(width, height),
        mask=_mask(width, height, 0),
    )
    try:
        result = engine.run(request)
    except UnsupportedRequest:
        pass
    except EngineError as failure:
        problems.append(
            f"run() answered a width of {width} against a declared maximum of "
            f"{sizes.max_side} with {type(failure).__name__} rather than "
            f"UnsupportedRequest: {failure}"
        )
    else:
        problems.append(
            f"run() produced a {result.width}x{result.height} image for a width "
            f"of {width} against a declared maximum of {sizes.max_side}, which "
            f"is approximating a request the declaration refuses"
        )
    job = JobDescription(
        operation=operation, width=width, height=height, has_prompt=False, steps=1
    )
    try:
        estimate = engine.estimate_device_memory(job)
    except UnsupportedRequest:
        pass
    except EngineError as failure:
        problems.append(
            f"estimate_device_memory() answered the same job with "
            f"{type(failure).__name__} rather than UnsupportedRequest: {failure}"
        )
    else:
        problems.append(
            f"estimate_device_memory() answered {estimate.peak_bytes} bytes for "
            f"a job of width {width} that run() refuses, so admission would "
            f"spend a lane to discover the refusal"
        )
    return "; ".join(problems) or None


CLAUSES: Final[
    Mapping[str, Callable[[EngineCase, Collection[str]], str | NotApplicable | None]]
] = {
    "an-estimate-arrives-without-loading-weights": (
        an_estimate_arrives_without_loading_weights
    ),
    "an-unsupported-request-is-refused-rather-than-approximated": (
        an_unsupported_request_is_refused_rather_than_approximated
    ),
    "a-full-mask-is-handled-or-refused": a_full_mask_is_handled_or_refused,
    "a-zero-mask-leaves-the-image-unchanged": a_zero_mask_leaves_the_image_unchanged,
    "cancelling-before-the-first-step-produces-no-image": (
        cancelling_before_the_first_step_produces_no_image
    ),
    "cancelling-mid-run-is-observed-within-the-bound": (
        cancelling_mid_run_is_observed_within_the_bound
    ),
    "capabilities-are-stable-across-calls": capabilities_are_stable_across_calls,
    "progress-is-monotonic-and-ends-at-the-total": (
        progress_is_monotonic_and_ends_at_the_total
    ),
}
"""Every clause, under the name a failure message calls it.

The names are the interface between a red run and the reader of one, so they are
written here once and never derived from a function name: renaming a function
would then silently rename the clause a reader searches this file for.
"""


class _AlreadyCancelled:
    """Cancelled before the engine reads it, and every time after."""

    @property
    def is_cancelled(self) -> bool:
        return True


class _CancelsAfterTheFirstRead:
    """Not cancelled on the first read, cancelled on every read after it.

    This is how a mid-run cancellation is produced without scripting the engine:
    whatever its steps are, the token turns inside the first one.
    """

    def __init__(self) -> None:
        self.reads = 0

    @property
    def is_cancelled(self) -> bool:
        self.reads += 1
        return self.reads > 1


def _first_operation(declaration: Capabilities) -> Operation | None:
    """One operation this engine declares, chosen the same way every run."""
    for operation in _OPERATION_ORDER:
        if operation in declaration.operations:
            return operation
    return None


def _declares_no_operation(declaration: Capabilities) -> str:
    return (
        f"declares no operation at all, so {declaration.engine_id} is an engine "
        f"nothing can be asked of"
    )


def _round_up(value: int, factor: int) -> int:
    return ((value + factor - 1) // factor) * factor


def _admissible_side(sizes: SizeConstraint) -> int | None:
    """A side this engine takes, near `_PREFERRED_SIDE` where the range allows."""
    if sizes.multiple_of < 1 or sizes.min_side > sizes.max_side:
        return None
    side = _round_up(max(sizes.min_side, _PREFERRED_SIDE), sizes.multiple_of)
    if side <= sizes.max_side:
        return side
    smallest = _round_up(sizes.min_side, sizes.multiple_of)
    return smallest if smallest <= sizes.max_side else None


def _no_admissible_side(sizes: SizeConstraint) -> str:
    return (
        f"declares no image size it accepts: min_side={sizes.min_side}, "
        f"max_side={sizes.max_side}, multiple_of={sizes.multiple_of}"
    )


def _smallest_request(declaration: Capabilities) -> EditRequest | str:
    """The least this engine can be asked to do, or why it cannot be asked.

    A string comes back where the declaration itself is the problem, so the
    caller reports it as a broken clause rather than as a skip.
    """
    operation = _first_operation(declaration)
    if operation is None:
        return _declares_no_operation(declaration)
    side = _admissible_side(declaration.sizes)
    if side is None:
        return _no_admissible_side(declaration.sizes)
    return EditRequest(
        operation=operation,
        image=_image(side, side),
        mask=_mask(side, side, 0),
    )


def _refused_its_own_declaration(request: EditRequest, failure: EngineError) -> str:
    return (
        f"refused a {request.image.width}x{request.image.height} "
        f"{request.operation.value} that its own declaration admits, with "
        f"{type(failure).__name__}: {failure}"
    )


def _image(width: int, height: int) -> ImageBuffer:
    """Pixels that are the same on every run, so a failure is reproducible.

    Not a constant fill. A buffer of one repeated byte is one an engine can copy
    the wrong region of and still return, byte for byte, what was expected.
    """
    data = bytes((index * 37 + 11) % 256 for index in range(width * height * _CHANNELS))
    return ImageBuffer(data=data, width=width, height=height, channels=_CHANNELS)


def _mask(width: int, height: int, value: int) -> MaskBuffer:
    return MaskBuffer(
        data=bytes([value]) * (width * height), width=width, height=height
    )


def _unchanged_problems(
    operation: Operation,
    image: ImageBuffer,
    result: ImageBuffer,
    case: EngineCase,
) -> list[str]:
    """How far the result moved from an input no mask asked it to move."""
    shape = (result.width, result.height, result.channels)
    if shape != (image.width, image.height, image.channels):
        return [
            f"{operation.value} returned {shape[0]}x{shape[1]} at {shape[2]} "
            f"channels for a {image.width}x{image.height} at {image.channels} "
            f"channel input"
        ]
    if len(result.data) != len(image.data):
        return [
            f"{operation.value} returned {len(result.data)} bytes for a "
            f"{len(image.data)} byte input of the same declared shape"
        ]
    worst = max(
        (
            abs(after - before)
            for after, before in zip(result.data, image.data, strict=True)
        ),
        default=0,
    )
    if worst > case.unchanged_tolerance:
        return [
            f"{operation.value} moved a pixel by {worst} where the mask was "
            f"zero everywhere, against a stated tolerance of "
            f"{case.unchanged_tolerance}"
        ]
    return []
