# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What the engine contract states about itself, checked against the module.

Nothing here exercises an engine, because no engine exists yet. What it holds is
the shape the orchestration layer is being written against: which names cross the
boundary, which failures a caller may distinguish by type, and which values reach
a wire. Each of those is a promise made in a docstring, and a promise no test
reads is a promise that moves.
"""

from __future__ import annotations

import dataclasses
from types import ModuleType
from typing import Any

import pytest

import retusche_contracts
from retusche_contracts import engine


def _names_defined_by(module: ModuleType) -> set[str]:
    """Public names this module creates, as opposed to ones it imported."""
    return {
        name
        for name, value in vars(module).items()
        if not name.startswith("_")
        and getattr(value, "__module__", None) == module.__name__
    }


def test_the_export_list_matches_what_the_module_defines() -> None:
    """A name added to the module and forgotten in ``__all__`` is invisible to a
    caller doing a star import, and a name removed from the module and left in
    ``__all__`` breaks one. Both are one edit away and neither shows in a diff
    review of the other half."""
    assert set(engine.__all__) == _names_defined_by(engine)


def test_the_package_re_exports_the_contract_exactly() -> None:
    """``retusche_contracts`` is the name the other two packages import. A name
    that reached ``engine.__all__`` and not this one is a name the contract has
    and its users cannot see."""
    assert retusche_contracts.__all__ == engine.__all__
    for name in retusche_contracts.__all__:
        assert getattr(retusche_contracts, name) is getattr(engine, name)


def test_the_export_list_is_sorted() -> None:
    """Sorted, so a name is added in one place rather than appended and the
    diff of an addition is one line."""
    assert engine.__all__ == sorted(engine.__all__)


def test_every_failure_type_descends_from_the_base() -> None:
    """The module says a caller distinguishes failures by type and never by
    reading a message. That only holds if every failure an engine may raise is
    catchable as ``EngineError``: one that is not would escape the handler a
    caller wrote against the documented base."""
    failures = [
        value
        for value in vars(engine).values()
        if isinstance(value, type)
        and issubclass(value, Exception)
        and value.__module__ == engine.__name__
    ]
    assert engine.EngineError in failures
    for failure in failures:
        assert issubclass(failure, engine.EngineError)


def test_the_run_method_names_every_failure_it_may_raise() -> None:
    """``run`` documents a closed set. This checks the set is closed rather than
    that the prose is elegant: a failure type added to the module and not to that
    list is one a caller has no reason to expect."""
    documented = engine.Engine.run.__doc__ or ""
    for failure in (
        engine.UnsupportedRequest,
        engine.OutOfDeviceMemory,
        engine.ModelNotAvailable,
        engine.Cancelled,
        engine.EngineFailure,
    ):
        assert failure.__name__ in documented


def test_an_operation_is_its_own_wire_value() -> None:
    """``Operation`` is a ``StrEnum`` because these values reach an HTTP request
    and a log line. A member whose value drifted from its name would be one
    spelling in the API and another in the code."""
    for member in engine.Operation:
        assert member.value == member.name.lower()
        assert member == member.value


@pytest.mark.parametrize(
    ("instance", "field"),
    [
        (engine.SizeConstraint(min_side=256, max_side=2048, multiple_of=8), "min_side"),
        (
            engine.ImageBuffer(data=b"\x00" * 12, width=2, height=2, channels=3),
            "width",
        ),
        (engine.MaskBuffer(data=b"\x00" * 4, width=2, height=2), "height"),
        (engine.DeviceMemoryEstimate(peak_bytes=1, is_measured=False), "peak_bytes"),
        (
            engine.JobDescription(
                operation=engine.Operation.ERASE,
                width=2,
                height=2,
                has_prompt=False,
                steps=1,
            ),
            "steps",
        ),
    ],
)
def test_a_value_crossing_the_boundary_cannot_be_edited_in_place(
    instance: object, field: str
) -> None:
    """These travel between a queue and a worker process. One that could be
    mutated after admission would let a job be judged on one shape and run on
    another."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, field, 0)


@pytest.mark.parametrize(
    "declared",
    [
        engine.Capabilities,
        engine.DeviceMemoryEstimate,
        engine.EditRequest,
        engine.ImageBuffer,
        engine.JobDescription,
        engine.MaskBuffer,
        engine.SizeConstraint,
    ],
)
def test_a_value_crossing_the_boundary_carries_no_instance_dictionary(
    declared: type,
) -> None:
    """``slots=True`` on every one of them. Without it an attribute typo lands
    silently on the instance instead of being refused, and the queue holds one of
    these per waiting job."""
    assert "__slots__" in vars(declared)
    assert "__dict__" not in vars(declared)


def test_an_edit_request_needs_only_an_operation_an_image_and_a_mask() -> None:
    """The optional half is optional. A default that went missing would turn
    every caller that omits a prompt into a type error at the call site."""
    request = engine.EditRequest(
        operation=engine.Operation.FILL,
        image=engine.ImageBuffer(data=b"\x00" * 12, width=2, height=2, channels=3),
        mask=engine.MaskBuffer(data=b"\x00" * 4, width=2, height=2),
    )
    assert request.prompt is None
    assert request.steps is None
    assert request.seed is None
    assert request.parameters is None


class _MinimalEngine:
    """Everything the protocol asks for and nothing else."""

    def capabilities(self) -> engine.Capabilities:
        return engine.Capabilities(
            engine_id="minimal",
            operations=frozenset({engine.Operation.ERASE}),
            sizes=engine.SizeConstraint(min_side=64, max_side=1024, multiple_of=8),
            uses_prompt=False,
            step_count_is_one=True,
        )

    def estimate_device_memory(
        self, job: engine.JobDescription
    ) -> engine.DeviceMemoryEstimate:
        return engine.DeviceMemoryEstimate(
            peak_bytes=job.width * job.height, is_measured=False
        )

    def run(
        self,
        request: engine.EditRequest,
        progress: engine.ProgressCallback | None = None,
        cancellation: engine.CancellationToken | None = None,
    ) -> engine.ImageBuffer:
        del progress, cancellation
        return request.image


class _EngineMissingRun:
    """The same, less the method the whole interface exists for."""

    def capabilities(self) -> engine.Capabilities:
        raise NotImplementedError

    def estimate_device_memory(
        self, job: engine.JobDescription
    ) -> engine.DeviceMemoryEstimate:
        raise NotImplementedError


def test_an_object_with_the_methods_is_an_engine() -> None:
    """The protocol is runtime-checkable so the worker can refuse a badly
    registered engine at load rather than at the first job."""
    assert isinstance(_MinimalEngine(), engine.Engine)


def test_an_object_missing_a_method_is_not_an_engine() -> None:
    """The half of the previous test that can actually fail. ``isinstance``
    against a protocol with no required members is true of everything."""
    assert not isinstance(_EngineMissingRun(), engine.Engine)


def test_a_callable_of_the_right_shape_is_a_progress_callback() -> None:
    def report(step: int, total: int) -> None:
        del step, total

    assert isinstance(report, engine.ProgressCallback)
    assert not isinstance(object(), engine.ProgressCallback)


def test_an_object_with_the_property_is_a_cancellation_token() -> None:
    class _Token:
        @property
        def is_cancelled(self) -> bool:
            return False

    assert isinstance(_Token(), engine.CancellationToken)
    assert not isinstance(object(), engine.CancellationToken)


def test_the_minimal_engine_answers_the_three_questions() -> None:
    """Not a test of an engine. It is the check that the protocol as declared can
    actually be implemented by an object that imports nothing heavier than the
    contract, which is the claim the boundary rests on."""
    subject: Any = _MinimalEngine()
    capabilities = subject.capabilities()
    assert engine.Operation.ERASE in capabilities.operations

    estimate = subject.estimate_device_memory(
        engine.JobDescription(
            operation=engine.Operation.ERASE,
            width=64,
            height=64,
            has_prompt=False,
            steps=1,
        )
    )
    assert estimate.peak_bytes == 64 * 64
    assert estimate.is_measured is False

    image = engine.ImageBuffer(data=b"\x00" * 12, width=2, height=2, channels=3)
    result = subject.run(
        engine.EditRequest(
            operation=engine.Operation.ERASE,
            image=image,
            mask=engine.MaskBuffer(data=b"\x00" * 4, width=2, height=2),
        )
    )
    assert result is image
