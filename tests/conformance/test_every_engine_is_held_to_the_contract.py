# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The engine rule, applied to this tree.

`tests/contract/` holds the clauses every engine is held to, and they run once
per entry in `tests/contract/engine_register.py`. That register is a list
somebody maintains, and what it costs to forget a line is the whole of the
contract for one engine: no capability declaration checked, no mask of zeroes,
no cancellation, and a green run that reads exactly like a run where the engine
passed.

The mistake is one line, it is an omission rather than an edit, and nothing in
this repository refused it until now. This rule refuses it in both directions:
an engine in the tree the register does not name, and a register entry that is
not a class in the tree answering the whole interface.

`tests/conformance/test_the_engine_rules_bite.py` is where each refusal is shown
to happen against a tree built to break exactly that rule. What a static reading
of a class body cannot see is written in `engine_rules` beside the walk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine_rules import engine_implementations, register_problems

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping


def test_every_engine_in_the_tree_is_in_the_contract_register(
    source_modules: Mapping[str, bytes],
    engine_interface_methods: Collection[str],
    registered_engines: Collection[str],
) -> None:
    """The rule itself. Fails naming the engine rather than the count."""
    problems = register_problems(
        engine_implementations(source_modules, engine_interface_methods),
        registered_engines,
        engine_interface_methods,
    )
    assert not problems, " ".join(problems)


def test_the_interface_is_read_off_the_declaration(
    engine_interface_methods: Collection[str],
) -> None:
    """The rule's own input, which decides what counts as an engine.

    An interface read as an empty set would make every class in the tree an
    engine and every one of them a violation, and an interface read as one
    method would make far too many. Neither state is visible in the rule's
    verdict, so it is asserted here: what the contract declares is what a caller
    reaches an engine through, and the three names below are what
    `docs/engine-interface.md` is written about.
    """
    assert set(engine_interface_methods) == {
        "capabilities",
        "estimate_device_memory",
        "run",
    }
