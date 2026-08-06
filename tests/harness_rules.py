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
from collections import deque
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


def _import_base(module: str, *, is_package: bool, level: int) -> str | None:
    """What a relative import of ``level`` dots resolves against, or nothing.

    One dot means the package the module sits in, which for a package is itself.
    A level that walks past the top of the tree resolves to nothing rather than
    to the empty string, because an import that cannot be resolved must not be
    silently read as an import of some top-level name.
    """
    parts = module.split(".")
    if not is_package:
        parts.pop()
    upward = level - 1
    if upward > len(parts):
        return None
    kept = parts[: len(parts) - upward]
    return ".".join(kept) if kept else None


def imported_modules(
    source: bytes,
    module: str,
    *,
    is_package: bool,
    known_modules: Collection[str],
    filename: str = "<source>",
) -> list[str]:
    """Every module name this source imports, absolute, at any depth.

    Not only module level, which is where this rule differs from the one that
    binds the suite. A runtime imported inside a function is still loaded into
    the process the moment that function runs, and a deferred import is exactly
    how a heavy dependency arrives in a process somebody meant to keep small. So
    a function body, a method and a branch nobody takes are all walked.

    Relative imports are resolved against the module they sit in, so a chain
    through ``from . import jobs`` is followed rather than passed over.

    ``from x import y`` is why ``known_modules`` is here. The statement imports
    the module ``x`` and it may or may not also import the module ``x.y``,
    depending on whether such a module exists, and nothing in the statement says
    which. Guessing that it does would invent an edge to a name that is really an
    attribute; guessing that it does not would lose the edge that most of this
    project's own imports are written as.
    """
    tree = ast.parse(source, filename=filename)
    known = frozenset(known_modules)
    found: list[str] = []

    def submodules(base: str, node: ast.ImportFrom) -> list[str]:
        return [
            candidate
            for alias in node.names
            if (candidate := f"{base}.{alias.name}") in known
        ]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    found.append(node.module)
                    found.extend(submodules(node.module, node))
                continue
            base = _import_base(module, is_package=is_package, level=node.level)
            if base is None:
                continue
            if node.module:
                found.append(f"{base}.{node.module}")
                found.extend(submodules(f"{base}.{node.module}", node))
            else:
                found.append(base)
                found.extend(submodules(base, node))
    return found


def import_boundary_offences(
    sources: Mapping[str, bytes],
    packages: Collection[str],
    entry_point: str,
    permitted_roots: Collection[str],
    forbidden_roots: Collection[str],
) -> list[list[str]]:
    """Every import chain that leaves the socket-safe part of the tree.

    A chain is the path the walk took, starting at ``entry_point`` where one
    exists, and ending at the module that may not be reached. The chain is the
    point: a bare verdict tells a reader that something in a growing package
    imports a tensor library and leaves them to find which edge, which is the
    review the rule exists to replace.

    Two kinds of module may not be reached. A name whose root is in
    ``forbidden_roots``, which is a machine-learning runtime or a model library.
    And a name whose root is one of this project's own packages that is not in
    ``permitted_roots``, which today is the worker. That second arm is derived
    from ``sources`` rather than listed, so a package arriving under ``src/`` is
    out of bounds for the socket process until somebody puts it in.

    The walk starts at the entry point and then seeds every socket-safe module
    it did not reach, in name order. Without that second pass a module nothing
    imports yet would be unjudged, and a module nothing imports yet is exactly
    what the next change makes reachable.
    """
    project_roots = {name.split(".")[0] for name in sources}
    permitted = frozenset(permitted_roots)
    forbidden = frozenset(forbidden_roots)
    package_names = frozenset(packages)

    def out_of_bounds(target: str) -> bool:
        root = target.split(".")[0]
        return root in forbidden or (root in project_roots and root not in permitted)

    visited: set[str] = set()
    offences: dict[tuple[str, str], list[str]] = {}

    def path_to(came_from: Mapping[str, str | None], module: str) -> list[str]:
        chain = [module]
        while (parent := came_from[chain[-1]]) is not None:
            chain.append(parent)
        chain.reverse()
        return chain

    def walk(seed: str) -> None:
        if seed in visited:
            return
        came_from: dict[str, str | None] = {seed: None}
        visited.add(seed)
        queue = deque([seed])
        while queue:
            current = queue.popleft()
            for target in dict.fromkeys(
                imported_modules(
                    sources[current],
                    current,
                    is_package=current in package_names,
                    known_modules=sources,
                    filename=current,
                )
            ):
                if out_of_bounds(target):
                    offences.setdefault(
                        (current, target), [*path_to(came_from, current), target]
                    )
                elif target in sources and target not in visited:
                    visited.add(target)
                    came_from[target] = current
                    queue.append(target)

    if entry_point in sources:
        walk(entry_point)
    for name in sorted(sources):
        if name.split(".")[0] in permitted:
            walk(name)

    return sorted(offences.values(), key=lambda chain: (len(chain), chain))


def import_boundary_message(entry_point: str, chains: list[list[str]]) -> str:
    """What a crossed boundary is reported as. Names every chain, not the count.

    Written here rather than at the assertion so the wording is one of the
    things the suite reads. A message that stopped printing the chain would
    leave a reader with a verdict and a package to search by hand, and nothing
    would notice it had happened.
    """
    drawn = "\n".join("  " + " -> ".join(chain) for chain in chains)
    return (
        f"the process that listens on a socket must not reach a "
        f"machine-learning runtime, a model library or the worker package. "
        f"Walking from {entry_point!r}, {len(chains)} import chain(s) do:\n"
        f"{drawn}\n"
        f"Move the work behind the engine interface in retusche_contracts and "
        f"let the worker process do it. The refused module roots and the roots "
        f"permitted in this process are [tool.retusche.import-boundary] in "
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
