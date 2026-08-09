# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The layout's dependency rules, with no pytest and no repository in them.

`docs/architecture.md` says which package may reach which. One of those
directions is held by `tests/test_import_boundary.py`: the process that listens
on a socket may not reach the worker, a machine-learning runtime or a model
library. The other two directions were prose, and this module is where they stop
being prose.

The walk is the one that boundary rule already uses, imported rather than written
again, so a chain found here and a chain found there are found by the same code.
What is new is the shape of the question. That rule asks one thing about one
package; this one asks it once per package, against a set declared per package,
so a layer arriving under `src/` tomorrow is judged rather than assumed.

One bound on the report, and it is attribution rather than correctness. The walk
seeds every module whose root is permitted, so judging a layer that is permitted
a neighbour also walks that neighbour's modules. An edge the neighbour may not
take is then refused under both rows, which duplicates a real offence and invents
none: an edge is out of bounds for a row only where that row does not permit it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from harness_rules import import_boundary_offences

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping


def layer_offences(
    sources: Mapping[str, bytes],
    packages: Collection[str],
    layer: str,
    permitted_roots: Collection[str],
) -> list[list[str]]:
    """Every import chain from ``layer`` that reaches a package it may not.

    No runtime roots are passed, and that is deliberate rather than an omission.
    A machine-learning runtime is refused to the socket-safe packages by the
    boundary rule and permitted to the worker by the layout, so a second list of
    runtime roots here would either duplicate that rule or contradict the one
    package the layout exempts. What is left is this project's own edges, which is
    the half nothing was refusing.
    """
    return import_boundary_offences(sources, packages, layer, permitted_roots, ())


def layer_message(
    layer: str, permitted_roots: Collection[str], chains: list[list[str]]
) -> str:
    """What a crossed layer is reported as. Names the chain and what it costs.

    Written here rather than at the assertion so the wording is one of the things
    the suite reads. A message that stopped printing the chain would leave a
    reader with a verdict and a package to search by hand, and nothing would
    notice that it had happened.
    """
    drawn = "\n".join("  " + " -> ".join(chain) for chain in chains)
    permitted = ", ".join(sorted(permitted_roots))
    return (
        f"{layer} may reach only {permitted} inside this project, and "
        f"{len(chains)} import chain(s) reach further:\n"
        f"{drawn}\n"
        f"A contract that reaches back into one of its users has stopped being a "
        f"contract, and a worker that reaches back into the orchestrator turns "
        f"two processes into one program split across a pipe. Both are what "
        f"docs/architecture.md is written to prevent. The declared sets are "
        f"[tool.retusche.layer-imports] in pyproject.toml."
    )


def layer_table_problems(
    in_tree: Collection[str],
    permitted_by_row: Mapping[str, Collection[str]],
    judged_elsewhere: Collection[str],
) -> list[str]:
    """Everything wrong with the agreement between the table and the tree.

    Three sets have to agree: the packages under ``src/``, the rows of the table,
    and the packages another rule already judges. A package in neither of the last
    two is judged by nothing and says so nowhere, which is a state a reader of a
    green run cannot tell from a package that was walked and found clean.
    """
    present = frozenset(in_tree)
    declared = frozenset(permitted_by_row)
    elsewhere = frozenset(judged_elsewhere)
    problems: list[str] = []

    unjudged = present - declared - elsewhere
    if unjudged:
        problems.append(
            f"packages under src/ that no dependency rule judges: "
            f"{', '.join(sorted(unjudged))}. Add each to "
            f"[tool.retusche.layer-imports] in pyproject.toml with the project "
            f"packages it may reach, or to the set the boundary rule already "
            f"reads. A package in neither is one whose imports nothing looks at."
        )

    absent = declared - present
    if absent:
        problems.append(
            f"[tool.retusche.layer-imports] holds rows for packages that are not "
            f"under src/: {', '.join(sorted(absent))}. A row matching no package "
            f"judges no imports and reports no error of its own, so the run looks "
            f"exactly like one where that layer was walked and was clean."
        )

    both = declared & elsewhere
    if both:
        problems.append(
            f"packages judged by two rules at once: {', '.join(sorted(both))}. "
            f"Each of the two declares the permitted set, and a reader cannot "
            f"tell which of them the run reported a verdict from."
        )

    permits_nothing = sorted(
        f"{row} -> {name}"
        for row, permitted in permitted_by_row.items()
        for name in sorted(frozenset(permitted) - present)
    )
    if permits_nothing:
        problems.append(
            f"rows permitting a package that is not under src/: "
            f"{', '.join(permits_nothing)}. The name permits nothing, so the "
            f"import it was written for is refused with a message listing a "
            f"package that does not exist."
        )

    return problems
