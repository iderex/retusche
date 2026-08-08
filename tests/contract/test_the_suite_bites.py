# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Every clause, against an engine built to break exactly that clause.

A suite whose clauses all pass says nothing about whether any of them could
fail. The engines below each depart from `FakeEngine` in one place, and each is
asked the clause that place belongs to, so a clause that stopped deciding
anything reds this file rather than staying green in the file beside it.

Two things are asserted per case, and the second is the one worth the effort.
That the clause reported a problem at all, and that the report names the reason
the clause exists rather than some other reason it happened to trip on. A clause
that refuses a broken engine because the engine also crashes is a clause that
was not measured.

One departure each, deliberately. A wreck would be refused by half the clauses
at once, which tells you nothing about which half. The near miss is the
one-character mistake somebody writing a second engine will actually make.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from types import ModuleType
from typing import TYPE_CHECKING

from contract_suite import CLAUSES, EngineCase, NotApplicable

from retusche.testing import FakeEngine, Script
from retusche_contracts import (
    Cancelled,
    DeviceMemoryEstimate,
    ImageBuffer,
    MaskBuffer,
)

if TYPE_CHECKING:
    from collections.abc import Collection

    from retusche_contracts import (
        CancellationToken,
        Capabilities,
        EditRequest,
        JobDescription,
        ProgressCallback,
    )


class _DriftingDeclaration(FakeEngine):
    """Answers with a different engine_id every time it is asked."""

    def __init__(self) -> None:
        super().__init__()
        self._answers = 0

    def capabilities(self) -> Capabilities:
        self._answers += 1
        return replace(super().capabilities(), engine_id=f"drifting-{self._answers}")


class _LoadsTheRuntimeWhileEstimating(FakeEngine):
    """Puts a machine-learning runtime into `sys.modules` inside the estimate.

    A real engine would do it by importing one. This one cannot: none of the
    forbidden roots is installed in the environment this suite runs in, which is
    the arrangement `tests/test_import_boundary.py` exists to keep. What the
    clause watches for is the module arriving, and that is what arrives.
    """

    def __init__(self, root: str) -> None:
        super().__init__()
        self._root = root

    def estimate_device_memory(self, job: JobDescription) -> DeviceMemoryEstimate:
        sys.modules.setdefault(self._root, ModuleType(self._root))
        return super().estimate_device_memory(job)


class _EditsAPixelTheMaskSpared(FakeEngine):
    """Changes one byte of the result whatever the mask said."""

    def run(
        self,
        request: EditRequest,
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
    ) -> ImageBuffer:
        result = super().run(request, progress, cancellation)
        data = bytearray(result.data)
        data[0] ^= 0xFF
        return replace(result, data=bytes(data))


class _TruncatesInsteadOfRefusing(FakeEngine):
    """Halves the canvas rather than saying it cannot do the whole frame."""

    def run(
        self,
        request: EditRequest,
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
    ) -> ImageBuffer:
        result = super().run(request, progress, cancellation)
        return _crop(result, result.width // 2)


class _ReportsProgressBackwards(FakeEngine):
    """Runs correctly and then tells the caller about it in reverse."""

    def run(
        self,
        request: EditRequest,
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
    ) -> ImageBuffer:
        seen: list[tuple[int, int]] = []
        result = super().run(
            request, lambda step, total: seen.append((step, total)), cancellation
        )
        if progress is not None:
            for step, total in reversed(seen):
                progress(step, total)
        return result


class _MiscountsItsSteps(FakeEngine):
    """Runs in two steps and declares that its work is not divided."""

    def capabilities(self) -> Capabilities:
        return replace(super().capabilities(), step_count_is_one=True)


class _ReadsTheTokenOnlyOnce(FakeEngine):
    """Checks cancellation before it starts and never again.

    This passes the before-the-first-step clause and fails the mid-run one,
    which is the pair that would otherwise be indistinguishable. An engine
    honouring cancellation at the front door is not an engine that can be
    stopped.
    """

    def run(
        self,
        request: EditRequest,
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
    ) -> ImageBuffer:
        if cancellation is not None and cancellation.is_cancelled:
            message = "cancelled before the run began"
            raise Cancelled(message)
        return super().run(request, progress, None)


class _CropsAnOversizeRequest(FakeEngine):
    """Trims a request past the declared maximum down to fit, and serves it."""

    def run(
        self,
        request: EditRequest,
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
    ) -> ImageBuffer:
        limit = self.capabilities().sizes.max_side
        if request.image.width > limit:
            request = replace(
                request,
                image=_crop(request.image, limit),
                mask=_crop_mask(request.mask, limit),
            )
        return super().run(request, progress, cancellation)


def _crop(image: ImageBuffer, width: int) -> ImageBuffer:
    """The left `width` pixels of every row, as a buffer declaring that width."""
    stride = image.width * image.channels
    keep = width * image.channels
    rows = [
        image.data[row * stride : row * stride + keep] for row in range(image.height)
    ]
    return ImageBuffer(
        data=b"".join(rows),
        width=width,
        height=image.height,
        channels=image.channels,
    )


def _crop_mask(mask: MaskBuffer, width: int) -> MaskBuffer:
    rows = [
        mask.data[row * mask.width : row * mask.width + width]
        for row in range(mask.height)
    ]
    return MaskBuffer(data=b"".join(rows), width=width, height=mask.height)


def _report(clause_name: str, case: EngineCase, roots: Collection[str]) -> str:
    """What the named clause says about this engine, which must be a problem.

    A skip is refused as firmly as a pass. A clause answering `NotApplicable`
    for an engine built to break it has stopped asking the question, and that
    reads green in the file beside this one.
    """
    verdict = CLAUSES[clause_name](case, roots)
    assert isinstance(verdict, str), (
        f"clause '{clause_name}' answered {verdict!r} for {case.name}, which "
        f"was built to break it"
    )
    return verdict


def test_the_stability_clause_refuses_a_declaration_that_drifts(
    forbidden_roots: Collection[str],
) -> None:
    case = EngineCase(name="drifting", build=_DriftingDeclaration)
    problem = _report("capabilities-are-stable-across-calls", case, forbidden_roots)
    assert "different declarations" in problem


def test_the_estimate_clause_refuses_a_runtime_arriving_during_the_call(
    forbidden_roots: Collection[str],
) -> None:
    root = sorted(forbidden_roots)[0]
    case = EngineCase(
        name="late-runtime", build=lambda: _LoadsTheRuntimeWhileEstimating(root)
    )
    try:
        problem = _report(
            "an-estimate-arrives-without-loading-weights", case, forbidden_roots
        )
    finally:
        sys.modules.pop(root, None)
    assert root in problem


def test_the_unchanged_clause_refuses_one_edited_pixel(
    forbidden_roots: Collection[str],
) -> None:
    """One byte, not a whole frame.

    The clause is worth nothing if it needs a large difference to notice: an
    engine that quietly re-encodes moves every pixel by a little and none of
    them by a lot.
    """
    case = EngineCase(name="restless", build=_EditsAPixelTheMaskSpared)
    problem = _report("a-zero-mask-leaves-the-image-unchanged", case, forbidden_roots)
    assert "where the mask was zero everywhere" in problem


def test_the_unchanged_clause_admits_that_edit_under_a_tolerance_that_covers_it(
    forbidden_roots: Collection[str],
) -> None:
    """The other direction, and the reason the tolerance sits on the entry.

    A clause refusing every difference would be one no diffusion engine could
    ever be registered under, so the tolerance has to be usable. The same engine
    under a tolerance its worst pixel fits inside passes.
    """
    case = EngineCase(
        name="restless",
        build=_EditsAPixelTheMaskSpared,
        unchanged_tolerance=255,
    )
    clause = CLAUSES["a-zero-mask-leaves-the-image-unchanged"]
    assert clause(case, forbidden_roots) is None


def test_the_full_mask_clause_refuses_a_truncated_canvas(
    forbidden_roots: Collection[str],
) -> None:
    case = EngineCase(name="truncating", build=_TruncatesInsteadOfRefusing)
    problem = _report("a-full-mask-is-handled-or-refused", case, forbidden_roots)
    assert "silent truncation" in problem


def test_the_progress_clause_refuses_progress_that_moves_backwards(
    forbidden_roots: Collection[str],
) -> None:
    case = EngineCase(name="reversing", build=_ReportsProgressBackwards)
    problem = _report(
        "progress-is-monotonic-and-ends-at-the-total", case, forbidden_roots
    )
    assert "moved backwards" in problem


def test_the_progress_clause_refuses_a_total_the_declaration_contradicts(
    forbidden_roots: Collection[str],
) -> None:
    """A two-step engine saying its work is not divided.

    The declaration is what a caller reads to get a cancellation bound, so this
    is not bookkeeping: the caller is told the worst case is the whole run and
    the run has a boundary in it that nobody uses.
    """
    case = EngineCase(name="miscounting", build=_MiscountsItsSteps)
    problem = _report(
        "progress-is-monotonic-and-ends-at-the-total", case, forbidden_roots
    )
    assert "declares step_count_is_one" in problem


def test_the_early_cancellation_clause_refuses_an_engine_that_ignores_the_token(
    forbidden_roots: Collection[str],
) -> None:
    case = EngineCase(
        name="deaf", build=lambda: FakeEngine(Script(honours_cancellation=False))
    )
    problem = _report(
        "cancelling-before-the-first-step-produces-no-image", case, forbidden_roots
    )
    assert "instead of raising Cancelled" in problem


def test_the_mid_run_clause_refuses_an_engine_that_only_checks_at_the_start(
    forbidden_roots: Collection[str],
) -> None:
    case = EngineCase(name="one-look", build=_ReadsTheTokenOnlyOnce)
    problem = _report(
        "cancelling-mid-run-is-observed-within-the-bound", case, forbidden_roots
    )
    assert "ran to completion" in problem


def test_that_same_engine_passes_the_early_cancellation_clause(
    forbidden_roots: Collection[str],
) -> None:
    """Which is what makes the mid-run clause worth having separately.

    Two clauses that always agreed would be one clause written twice, and the
    second would prove nothing the first did not.
    """
    case = EngineCase(name="one-look", build=_ReadsTheTokenOnlyOnce)
    clause = CLAUSES["cancelling-before-the-first-step-produces-no-image"]
    assert clause(case, forbidden_roots) is None


def test_the_refusal_clause_refuses_an_engine_that_crops_to_fit(
    forbidden_roots: Collection[str],
) -> None:
    case = EngineCase(name="cropping", build=_CropsAnOversizeRequest)
    problem = _report(
        "an-unsupported-request-is-refused-rather-than-approximated",
        case,
        forbidden_roots,
    )
    assert "approximating a request the declaration refuses" in problem


def test_the_mid_run_clause_is_skipped_and_not_passed_by_a_single_step_engine(
    forbidden_roots: Collection[str],
) -> None:
    """The skip is the point.

    An engine whose work is not divided into steps cannot be asked to observe a
    mid-run cancellation, and a clause returning no problem for it would be a
    green line saying the bound was checked.
    """
    case = EngineCase(name="fake", build=lambda: FakeEngine(Script(steps=1)))
    clause = CLAUSES["cancelling-mid-run-is-observed-within-the-bound"]
    verdict = clause(case, forbidden_roots)
    assert isinstance(verdict, NotApplicable)
    assert "step_count_is_one" in verdict.reason
