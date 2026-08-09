# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The engine rule, run against trees built to break exactly it.

The trees here are fixtures rather than this repository. A rule whose refusing
arm is only ever reached on the day somebody trips it is a rule nobody has seen
work, and a rule judged against the real tree proves the state of the tree on
the day it ran rather than the rule.

Every violation below is written as the mistake somebody would actually make. A
second engine landing in the worker package with no register entry is the one
this rule exists for, and it is an omission: nothing is edited, nothing is
misspelled, and the contract suite goes on passing with a smaller subject.
Renaming a method on an implementation is the other direction, and it is the
change that looks safe because the type checker follows the call sites it can
see.
"""

from __future__ import annotations

from engine_rules import engine_implementations, register_problems

_INTERFACE = frozenset({"capabilities", "estimate_device_memory", "run"})

_AN_ENGINE = (
    b"class Erase:\n"
    b"    def capabilities(self): ...\n"
    b"    def estimate_device_memory(self, job): ...\n"
    b"    def run(self, request, progress=None, cancellation=None): ...\n"
)

_CLEAN_TREE: dict[str, bytes] = {
    "retusche_contracts.engine": b"class Engine(Protocol):\n"
    b"    def capabilities(self): ...\n"
    b"    def estimate_device_memory(self, job): ...\n"
    b"    def run(self, request, progress=None, cancellation=None): ...\n",
    "retusche.queue.store": b"class JobStore:\n    def close(self): ...\n",
    "retusche_worker.engines.erase": _AN_ENGINE,
}

_REGISTERED = frozenset({"retusche_worker.engines.erase.Erase"})


def _tree(**overrides: bytes) -> dict[str, bytes]:
    """The clean tree with one module added or replaced. One change per fixture."""
    return _CLEAN_TREE | overrides


def test_a_clean_tree_is_refused_nothing() -> None:
    """The passing arm. A rule that refused everything would pass every other
    test in this file and refuse the tree it ships in."""
    found = engine_implementations(_CLEAN_TREE, _INTERFACE)
    assert found == _REGISTERED
    assert not register_problems(found, _REGISTERED, _INTERFACE)


def test_a_second_engine_nobody_registered_is_refused() -> None:
    """The near miss this rule exists for.

    A diffusion engine lands in the worker package. It implements the interface,
    the layout permits it, the import boundary is unmoved, and the contract
    suite passes because it runs once per register entry and the register still
    has one. Nothing in the tree said the new engine was held to nothing.
    """
    tree = _tree(
        **{
            "retusche_worker.engines.inpaint": b"class Inpaint:\n"
            b"    def capabilities(self): ...\n"
            b"    def estimate_device_memory(self, job): ...\n"
            b"    def run(self, request, progress=None, cancellation=None): ...\n"
        }
    )
    problems = register_problems(
        engine_implementations(tree, _INTERFACE), _REGISTERED, _INTERFACE
    )
    assert len(problems) == 1
    assert "retusche_worker.engines.inpaint.Inpaint" in problems[0]
    assert "held to none of them" in problems[0]


def test_an_engine_that_stopped_answering_the_interface_is_refused() -> None:
    """The other direction, written as the rename that looks safe.

    ``estimate_device_memory`` becomes ``estimate``. The class is still in the
    register, the register still builds it, and the clause that asks for an
    estimate fails loudly. The clause that does not ask passes, and so does
    every other gate. What this refuses is the state rather than the symptom:
    the register names something the declaration no longer describes.
    """
    tree = _tree(
        **{
            "retusche_worker.engines.erase": b"class Erase:\n"
            b"    def capabilities(self): ...\n"
            b"    def estimate(self, job): ...\n"
            b"    def run(self, request, progress=None, cancellation=None): ...\n"
        }
    )
    problems = register_problems(
        engine_implementations(tree, _INTERFACE), _REGISTERED, _INTERFACE
    )
    assert len(problems) == 1
    assert "retusche_worker.engines.erase.Erase" in problems[0]
    assert "estimate_device_memory" in problems[0]


def test_the_protocol_declaring_the_interface_is_not_an_engine() -> None:
    """The one-character version of this rule refusing its own contract.

    The protocol defines every method the interface has, which is what a
    protocol is. A walk that counted it would demand a register entry for the
    declaration, and the cheapest way out of that failure is to add one, which
    puts the interface itself through clauses written to judge implementations
    of it.
    """
    assert "retusche_contracts.engine.Engine" not in engine_implementations(
        _CLEAN_TREE, _INTERFACE
    )


def test_a_class_answering_part_of_the_interface_is_not_an_engine() -> None:
    """A half-implementation is not an engine, and calling one an engine would
    make every partial class in the tree owe a register entry it cannot meet."""
    tree = _tree(
        **{
            "retusche.queue.lane": b"class Lane:\n"
            b"    def capabilities(self): ...\n"
            b"    def run(self, request): ...\n"
        }
    )
    assert engine_implementations(tree, _INTERFACE) == _REGISTERED


def test_an_engine_built_inside_a_factory_is_still_seen() -> None:
    """A class defined in a function body is a class the tree holds.

    It is reported under the module rather than under the function, which is the
    bound `engine_rules` states on the name. The refusal is the point and the
    name is how a reader finds it.
    """
    tree = _tree(
        **{
            "retusche_worker.engines.build": b"def make():\n"
            b"    class Hidden:\n"
            b"        def capabilities(self): ...\n"
            b"        def estimate_device_memory(self, job): ...\n"
            b"        def run(self, request): ...\n"
            b"    return Hidden\n"
        }
    )
    assert "retusche_worker.engines.build.Hidden" in engine_implementations(
        tree, _INTERFACE
    )
