# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Who is allowed to say something, and how. No pytest and no repository here.

One module builds a log line and refuses one that would carry a photograph, a
prompt or a path out of the operator's library. That refusal is worth exactly as
much as the number of places that go around it, and today nothing stops a
component reaching for the standard library's logger or writing to the process's
output directly. Both produce a line nothing declared and nothing checked.

So this is the invariant: outside the declaration's own package, a module under
``src/`` neither imports a logging framework nor writes to the process's output.
It is a textual rule over the syntax, which is what makes it cheap and what
bounds it, and ``refusals`` is where the bound is written down rather than left
to be discovered.

The inputs arrive as arguments. The tree, the project file and the package names
are the caller's business, the same way they are for ``harness_rules``.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Mapping


class Offence(NamedTuple):
    """One place a module says something outside the declaration."""

    line: int
    written: str
    invariant: str


def _dotted(node: ast.expr) -> str | None:
    """``sys.stdout.write`` from the attribute chain, or nothing for a call.

    A call in the middle of the chain, ``open(path).write``, resolves to no
    dotted name at all rather than to a partial one, because a partial name is
    what a rule matches by accident.
    """
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def _imported_names(node: ast.AST) -> Iterator[str]:
    """The module an import statement names, absolute only.

    A relative import cannot reach a top-level framework, so it is passed over
    rather than resolved. The same decision, for the same reason, as the import
    rules in ``harness_rules``.
    """
    if isinstance(node, ast.Import):
        for alias in node.names:
            yield alias.name
    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        yield node.module


def output_offences(
    source: bytes,
    refused_imports: Collection[str],
    refused_calls: Collection[str],
    filename: str = "<source>",
) -> list[Offence]:
    """Every import of a logging framework and every direct write, in line order.

    The walk reads the whole module, function bodies included. A deferred import
    is how a framework arrives in a module somebody meant to keep to the
    declaration, and a write inside an error path is the write that matters most,
    because it is the one that runs when something has already gone wrong.

    A refused call is matched on its dotted name as written. ``sys.stdout.write``
    is caught and ``stdout.write`` after ``from sys import stdout`` is not, which
    is the shape of every rule of this kind and is why the caller states what it
    does not see.
    """
    tree = ast.parse(source, filename=filename)
    refused_import_roots = frozenset(refused_imports)
    refused_call_names = frozenset(refused_calls)
    offences: list[Offence] = []
    for node in ast.walk(tree):
        for name in _imported_names(node):
            if name.split(".")[0] in refused_import_roots:
                offences.append(Offence(node.lineno, name, "imports-a-logger"))
        if isinstance(node, ast.Call):
            written = _dotted(node.func)
            if written is not None and written in refused_call_names:
                offences.append(Offence(node.lineno, written, "writes-directly"))
    return sorted(set(offences))


def output_message(
    offences: Mapping[str, list[Offence]],
    through: str,
    reasons: Mapping[str, str],
) -> str:
    """What a module that spoke for itself is told, per file and per line.

    The failure each invariant prevents is passed in rather than written here, so
    adding one is an entry in the declaration and not an edit to this sentence.
    """
    drawn = "\n".join(
        f"  {filename}:{offence.line}: {offence.written} ({offence.invariant})"
        for filename in sorted(offences)
        for offence in offences[filename]
    )
    named = "\n".join(f"  {name}: {reasons[name]}" for name in sorted(reasons))
    return (
        f"a line about the work goes through {through} and nowhere else. "
        f"{sum(len(found) for found in offences.values())} place(s) do not:\n"
        f"{drawn}\n"
        f"What each invariant prevents:\n"
        f"{named}"
    )
