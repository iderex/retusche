# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Which classes are engines, and which of them the contract suite holds.

No pytest, no tree and no register in this module. It is handed a mapping of
module name to source, the method names the interface declares, and the set of
classes a register names, and it answers what disagrees between them.

The interface is read rather than restated. Nothing here spells out
``capabilities``, ``estimate_device_memory`` or ``run``: the caller derives them
from the declaration in ``retusche_contracts``, so a method added to the
interface tomorrow changes what counts as an engine here without this file being
touched. A list of method names written into this module would be the second
copy of an interface, and the drift between the two would be invisible.

What a class is judged on is what its own body defines. Inheritance is not
followed, because the sources are text and the base may be in another module,
another distribution or a runtime this process may not import. The cost is
stated rather than discovered: an engine that reaches the interface only through
a base class is not seen here, and the register arm below is what catches it, in
the direction that matters.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Mapping


def _classes(node: ast.AST, prefix: str) -> Iterator[tuple[str, ast.ClassDef]]:
    """Every class in a module, named the way an import statement reaches it.

    The walk enters function bodies as well as class bodies, so a class built
    inside a factory is seen. Only class nesting extends the name, so such a
    class is reported under the enclosing class or module rather than under the
    function. That is a bound on the report and not on the finding: the name is
    what a reader searches by, and the class is still refused.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            name = f"{prefix}.{child.name}"
            yield name, child
            yield from _classes(child, name)
        else:
            yield from _classes(child, prefix)


def _is_protocol(node: ast.ClassDef) -> bool:
    """Whether the class is the declaration rather than an implementation.

    A protocol defines every method the interface has, which is the whole point
    of it, so without this the module declaring the interface would be refused
    for not being in a register of its own implementations.
    """
    names = [
        base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
        for base in node.bases
    ]
    return "Protocol" in names


def engine_implementations(
    sources: Mapping[str, bytes], interface_methods: Collection[str]
) -> frozenset[str]:
    """Every class under ``src/`` whose own body answers the whole interface.

    A class answering all of it and nothing calling it an engine is exactly the
    shape this is for: an engine is what implements the interface, not what
    somebody remembered to name.
    """
    required = frozenset(interface_methods)
    found: set[str] = set()
    for module, source in sources.items():
        tree = ast.parse(source, filename=module)
        for name, node in _classes(tree, module):
            if _is_protocol(node):
                continue
            defined = {
                member.name
                for member in node.body
                if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef)
            }
            if required <= defined:
                found.add(name)
    return frozenset(found)


def register_problems(
    in_tree: Collection[str],
    registered: Collection[str],
    interface_methods: Collection[str],
) -> list[str]:
    """Everything wrong between the engines in the tree and the register.

    Both directions, because each is a different way for a clause to stop
    reaching an engine and neither reports itself. An engine the register does
    not name is held to nothing while every gate stays green. A register entry
    naming a class that no longer answers the interface is a run whose clauses
    execute against something the declaration does not describe, and the report
    a reader gets says the contract suite passed.

    ``interface_methods`` is printed rather than checked again. A reader meeting
    the second arm needs to know what answering the whole interface meant on the
    day the run happened, and that set is derived from the declaration rather
    than from anything written here.
    """
    present = frozenset(in_tree)
    named = frozenset(registered)
    required = ", ".join(sorted(interface_methods))
    problems: list[str] = []

    unheld = present - named
    if unheld:
        problems.append(
            f"engines under src/ that the contract register does not name: "
            f"{', '.join(sorted(unheld))}. The clauses in tests/contract/ run "
            f"once per entry in tests/contract/engine_register.py, so an engine "
            f"absent from it has been held to none of them: not what its "
            f"capability declaration promises, not what a mask of zeroes means, "
            f"not what cancelling does. Add an entry, or move the engine to the "
            f"hardware harness register where it is skipped by name."
        )

    unknown = named - present
    if unknown:
        problems.append(
            f"contract register entries that are not a class under src/ "
            f"answering the whole interface: {', '.join(sorted(unknown))}. "
            f"Either the class moved, or a method the interface declares was "
            f"renamed on the implementation and nothing else noticed, because "
            f"the clauses call what they call and a run against a stand-in "
            f"reports the same green as a run against the engine. Answering the "
            f"whole interface meant defining {required}."
        )

    return problems
