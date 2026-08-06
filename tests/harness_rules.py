# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The rules the harness applies to itself, with no pytest and no repository.

Kept out of ``conftest.py`` and given plain inputs so the suite can exercise them
the way it exercises anything else: against vocabularies it constructs. A rule
reachable only by arranging the real tree is a rule whose refusals are each seen
once, on the day somebody trips it, and a rule whose passing arm proves the state
of this repository rather than the rule.

``conftest.py`` reads ``pyproject.toml`` and the tree and hands the results here.
Nothing in this module knows where any of it came from.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Mapping


def _module_level_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Every node reached without entering a function body.

    A class body and an ``if`` at module level are both inside this walk, and so
    is ``if TYPE_CHECKING:``. That is deliberate rather than an oversight: those
    are where an import gets written by somebody who wants it to look
    conditional, and a unit test that names a machine-learning runtime even in an
    annotation is a test whose subject is the runtime.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        yield child
        yield from _module_level_nodes(child)


def module_level_forbidden_imports(
    source: bytes,
    roots: Collection[str],
    filename: str = "<source>",
) -> list[tuple[int, str]]:
    """Line and module name for every module-level import of a forbidden root.

    A relative import cannot reach a top-level runtime, so a non-zero ``level``
    is passed over rather than resolved against the package it sits in.
    """
    tree = ast.parse(source, filename=filename)
    offences: list[tuple[int, str]] = []
    for node in _module_level_nodes(tree):
        if isinstance(node, ast.Import):
            offences.extend(
                (node.lineno, alias.name)
                for alias in node.names
                if alias.name.split(".")[0] in roots
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
            and node.module.split(".")[0] in roots
        ):
            offences.append((node.lineno, node.module))
    return offences


def forbidden_import_message(filename: str, offences: list[tuple[int, str]]) -> str:
    """What a refused test file is told. Names the file, the line and the module.

    Written here rather than at the raise site so the wording is one of the
    things the suite reads: a message that stopped naming the module would leave
    a reader with a refusal and no way to act on it, and nothing would notice.
    """
    named = "; ".join(f"line {line}: {module}" for line, module in offences)
    return (
        f"{filename}: a unit test may not import a machine-learning runtime "
        f"while the module executes ({named}). A test that needs the runtime "
        f"needs weights, a device and a driver, and this suite has none of the "
        f"three. Move it to the hardware harness, where it is skipped by name. "
        f"The refused module roots are [tool.retusche.import-boundary] in "
        f"pyproject.toml."
    )


def coverage_scope_problems(
    in_tree: Collection[str],
    measured: Collection[str],
    excluded: Mapping[str, str],
) -> list[str]:
    """Everything wrong with the agreement between three sets, in order.

    Three sets have to agree: the packages that exist, the packages coverage
    measures, and the packages carrying a written reason for not being measured.

    A package in none of the last two is the state nobody is told anything about.
    It is absent from the report because coverage never looked at it, and absent
    from the exclusions because nobody wrote a reason, and those two absences are
    indistinguishable to a reader of the run.
    """
    present = frozenset(in_tree)
    covered = frozenset(measured)
    waived = frozenset(excluded)
    problems: list[str] = []

    undecided = present - covered - waived
    if undecided:
        problems.append(
            f"packages under src/ that coverage neither measures nor excludes "
            f"with a reason: {', '.join(sorted(undecided))}. Add each to "
            f"[tool.coverage.run] source or to "
            f"[tool.retusche.coverage-exclusions] in pyproject.toml, with the "
            f"reason written out."
        )

    absent = (covered | waived) - present
    if absent:
        problems.append(
            f"coverage configuration names packages that are not under src/: "
            f"{', '.join(sorted(absent))}. A source entry matching nothing "
            f"measures nothing and reports no error of its own, so the run looks "
            f"exactly like one where the package was measured and was clean."
        )

    overlap = covered & waived
    if overlap:
        problems.append(
            f"packages both measured and excluded: {', '.join(sorted(overlap))}. "
            f"One of the two entries is wrong and the report cannot say which."
        )

    return problems


def coverage_scope_lines(
    measured: Collection[str], excluded: Mapping[str, str]
) -> list[str]:
    """The lines a run prints about its own scope.

    Derived from the configuration rather than written out, so the disclosure and
    the measurement cannot drift apart.
    """
    lines = [f"measured: {name}" for name in sorted(measured)]
    lines.extend(
        f"not measured: {name} - {excluded[name]}" for name in sorted(excluded)
    )
    return lines
