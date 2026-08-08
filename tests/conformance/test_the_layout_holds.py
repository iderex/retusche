# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The layout's dependency rules, applied to this tree.

Two directions the layout states and nothing refused until now. A contract that
imports one of its users has stopped being a contract, and it makes the worker's
dependency on the contract a dependency on the orchestration layer. A worker that
imports the orchestrator turns two operating-system processes into one program
that happens to be split across a pipe, which is the arrangement the process
boundary exists to prevent.

Both are one line away at all times, and the line is a plausible one: a contract
module recording the version it was built against, or an engine reaching for the
test double as a fallback. `tests/conformance/test_the_layer_rules_bite.py` is
where each refusal is shown to happen against a tree built to break it.

What these tests do not establish is written where the walk is:
`tests/test_import_boundary.py` says what a static reading of import statements
cannot see, and this rule sees exactly as much and no more.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from layer_rules import layer_message, layer_offences, layer_table_problems

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping


def test_no_layer_reaches_a_package_it_may_not(
    source_modules: Mapping[str, bytes],
    source_packages: Collection[str],
    layer_imports: Mapping[str, frozenset[str]],
) -> None:
    """The rule itself. Fails with the chain rather than with the fact."""
    reported = [
        layer_message(layer, permitted, chains)
        for layer, permitted in sorted(layer_imports.items())
        if (chains := layer_offences(source_modules, source_packages, layer, permitted))
    ]
    assert not reported, "\n".join(reported)


def test_every_package_under_src_is_judged_by_one_rule(
    source_modules: Mapping[str, bytes],
    layer_imports: Mapping[str, frozenset[str]],
    orchestration_entry_point: str,
) -> None:
    """A package no rule judges is the state a green run cannot be read against.

    The orchestration layer is not a row in the table. Its permitted set is
    `socket-safe-roots`, which the boundary rule reads, and a second copy here
    would be two lists for one property with nothing refusing a divergence
    between them. So it is passed in as judged elsewhere, and every other package
    under `src/` owes a row.

    The boundary rule also walks the other socket-safe package, under the
    orchestration layer's set rather than that package's own. Where the two sets
    differ the stricter one decides, because a refusal from either fails the run.
    """
    roots_in_tree = {name.split(".")[0] for name in source_modules}
    problems = layer_table_problems(
        roots_in_tree,
        layer_imports,
        {orchestration_entry_point.split(".")[0]},
    )
    assert not problems, " ".join(problems)
