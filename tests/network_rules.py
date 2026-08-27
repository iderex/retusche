# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Which modules may reach a host. No pytest and no repository here.

The premise of this project is that the photographs stay on the operator's
machine. That premise is carried today by the fact that nothing in the
orchestration layer opens a connection except the one module that fetches
weights, and by nothing else: no check reads it, and a component that acquired
an outbound call would leave every route as green as one that did not.

So this is the invariant: outside the module the declaration names, a module
under the judged roots neither imports a way of opening a connection nor calls
one. It is a textual rule over the syntax, which is what makes it cheap and what
bounds it, and ``refusals`` is where the bound is written down rather than left
to be discovered.

Why the match is on a dotted prefix and not on a root
-----------------------------------------------------
``urllib.request`` opens a connection and ``urllib.parse`` splits a string, and
both are used in this tree. Matching the root would refuse the second for what
the first does, which is a rule that has to be worked around on the day it lands.
So a refused import is a dotted prefix: ``urllib.request`` matches itself and
anything beneath it, and matches ``urllib.parse`` never.

``from urllib import request`` is read as ``urllib.request`` rather than as
``urllib``, because that spelling is what somebody writes once the plain import
has been refused, and reading only the module a ``from`` names would let it past.

The inputs arrive as arguments. The tree, the project file and the module names
are the caller's business, the same way they are for ``output_rules``.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Mapping

__all__ = [
    "Reach",
    "network_message",
    "network_offences",
]


class Reach(NamedTuple):
    """One place a module can reach a host from."""

    line: int
    written: str
    invariant: str


def _dotted(node: ast.expr) -> str | None:
    """``urllib.request.urlopen`` from the attribute chain, or nothing.

    A call in the middle of the chain resolves to no dotted name at all rather
    than to a partial one, because a partial name is what a rule matches by
    accident. The same decision, for the same reason, as ``output_rules``.
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
    """What an import statement reaches for, absolute only and fully spelled.

    ``import a.b`` yields ``a.b``. ``from a.b import c`` yields ``a.b.c`` rather
    than ``a.b``, so the member is judged by the same prefix rule as the module,
    and ``from a import b`` therefore yields ``a.b``. A relative import cannot
    reach a top-level module, so it is passed over rather than resolved.
    """
    if isinstance(node, ast.Import):
        for alias in node.names:
            yield alias.name
    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        for alias in node.names:
            yield f"{node.module}.{alias.name}"


def _under(name: str, prefixes: Collection[str]) -> bool:
    return any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)


def network_offences(
    source: bytes,
    refused_imports: Collection[str],
    refused_calls: Collection[str],
    filename: str = "<source>",
) -> list[Reach]:
    """Every import of a way out and every call of one, in line order.

    The walk reads the whole module, function bodies included. A deferred import
    is how a client arrives in a module somebody meant to keep off the network,
    and it opens the same socket wherever it is written.

    A refused call is matched on its dotted name as written. ``socket.socket`` is
    caught and ``socket()`` after ``from socket import socket`` is not, which is
    the shape of every rule of this kind. The import arm catches that second
    spelling instead, which is why the two arms are not alternatives.
    """
    tree = ast.parse(source, filename=filename)
    offences: list[Reach] = []
    for node in ast.walk(tree):
        for name in _imported_names(node):
            if _under(name, refused_imports):
                offences.append(Reach(node.lineno, name, "imports-a-way-out"))
        if isinstance(node, ast.Call):
            written = _dotted(node.func)
            if written is not None and _under(written, refused_calls):
                offences.append(Reach(node.lineno, written, "opens-a-connection"))
    return sorted(set(offences))


def network_message(
    offences: Mapping[str, list[Reach]],
    through: str,
    reasons: Mapping[str, str],
) -> str:
    """What a module that reached for a host is told, per file and per line.

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
        f"this service reaches a host from {through} and from nowhere else. "
        f"{sum(len(found) for found in offences.values())} place(s) do not:\n"
        f"{drawn}\n"
        f"What each invariant prevents:\n"
        f"{named}"
    )
