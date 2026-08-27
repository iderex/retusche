# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Every path a document names is a path this tree holds.

The rule is in ``documentation_rules``, exercised there against sources written
in that file. What is here is the wiring: read the declaration, walk the
markdown, hand both to the rule, and turn what comes back into a refusal.

The declaration is ``[tool.retusche.documentation-references]`` in
``pyproject.toml``, read here and never restated. Its exemption table is the
place a reference to a deliberately absent path is written down with the reason,
and it fails closed in both directions: an entry whose path has arrived and an
entry no document makes are both refused, so the table cannot become the drawer
a stale pointer is filed in.

What this does not see:

- a bare filename, ``unicode-guard.yml``, and a token that carries a separator
  and no suffix, ``i/crlf``. Both are left alone on purpose: the first is how a
  document names a workflow in passing and the second is a column of
  ``git ls-files --eol``, and refusing either refuses the pages that explain
  those commands
- whether a link that resolves points at the right file, or whether the
  paragraph around it still describes what the file does
- a fragment. ``docs/logging.md#fields`` is resolved to the file and the
  heading is not looked for, so a renamed heading is a live link here
- a path named inside an indented block by a command that was run at some other
  ref. No command in this tree carries a backtick or a markdown link, so the two
  populations do not overlap today; nothing in the syntax keeps them apart
- a reference in anything that is not markdown. A path named in a docstring, in
  a comment or in a workflow file is not read here
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any, Final

import pytest
from documentation_rules import (
    Reference,
    reference_message,
    reference_offences,
    references,
    stale_exemptions,
)

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent
_PROJECT_FILE: Final = _REPO_ROOT / "pyproject.toml"


@cache
def _declaration() -> dict[str, Any]:
    with _PROJECT_FILE.open("rb") as handle:
        config: dict[str, Any] = tomllib.load(handle)
    table: dict[str, Any] = config["tool"]["retusche"]["documentation-references"]
    return table


def _skipped(parts: tuple[str, ...], declaration: dict[str, Any]) -> bool:
    resolved: list[str] = declaration["resolved-dot-directories"]
    skipped: list[str] = declaration["skipped-directories"]
    return any(
        (part.startswith(".") and part not in resolved) or part in skipped
        for part in parts
    )


@cache
def _held_paths() -> frozenset[str]:
    """Every path a reference may resolve to, as a posix string.

    Built by walking rather than by asking git, so the suite needs nothing but
    the checkout it is running in. A skipped directory is pruned rather than
    filtered afterwards, because the largest of them is the virtual environment
    and descending into it costs more than the rest of the walk together.

    A dot directory is skipped unless the declaration names it, which is what
    keeps a generated tree out of the answer: ``.venv/`` resolves nowhere here
    even on the machine that has one.
    """
    declaration = _declaration()
    held: set[str] = set()
    pending = [_REPO_ROOT]
    while pending:
        for path in pending.pop().iterdir():
            relative = path.relative_to(_REPO_ROOT)
            if _skipped(relative.parts[-1:], declaration):
                continue
            if path.is_dir():
                held.add(relative.as_posix() + "/")
                pending.append(path)
            else:
                held.add(relative.as_posix())
    return frozenset(held)


def _exists(held: frozenset[str]) -> Callable[[str], bool]:
    def resolve(target: str) -> bool:
        if not target:
            return False
        stripped = target.rstrip("/")
        return target in held or stripped in held or f"{stripped}/" in held

    return resolve


@cache
def _documents() -> tuple[Path, ...]:
    """Every markdown file the walk above reached, which is every one that is
    not inside a cache, a build output or the virtual environment."""
    return tuple(
        sorted(_REPO_ROOT / held for held in _held_paths() if held.endswith(".md"))
    )


def _cited_targets() -> set[str]:
    suffixes = _declaration()["path-suffixes"]
    return {
        reference.target
        for path in _documents()
        for reference in references(path.read_bytes(), suffixes)
    }


def test_the_walk_finds_the_documents_it_is_supposed_to_judge() -> None:
    """A walk that found nothing would pass and say nothing.

    This is the arm that goes red the day the skip grows past what it was written
    for, or the day the documents move and the glob stops matching.
    """
    found = {path.relative_to(_REPO_ROOT).as_posix() for path in _documents()}
    assert "README.md" in found
    assert "docs/legal/data-protection.md" in found
    assert ".github/pull_request_template.md" in found


def test_the_walk_reads_both_shapes_of_reference() -> None:
    """The two kinds are counted before anything is asserted about resolution.

    A rule that had stopped matching links, or stopped matching backticked
    paths, would find no offence and read exactly like a tree with none.
    """
    suffixes = _declaration()["path-suffixes"]
    found: list[Reference] = [
        reference
        for path in _documents()
        for reference in references(path.read_bytes(), suffixes)
    ]
    kinds = {reference.kind for reference in found}
    assert kinds == {"link", "path"}


def test_the_dot_directory_the_declaration_names_is_reachable() -> None:
    """The exception to the dot skip is the one the declaration names, and it
    holds documents this tree points at. Without this, the list could name any
    directory and the walk below would agree with itself about a smaller set."""
    held = _held_paths()
    for name in _declaration()["resolved-dot-directories"]:
        assert f"{name}/" in held


def test_a_generated_tree_is_not_what_a_reference_resolves_against() -> None:
    """``.venv/`` is on this machine whenever the suite runs, because the runner
    creates it. It is not what a document may point at, and a walk that resolved
    it would excuse the one reference the exemption table exists to hold."""
    assert not _exists(_held_paths())(".venv")


@pytest.mark.parametrize("path", _documents(), ids=lambda path: path.name)
def test_every_path_a_document_names_is_in_this_tree(path: Path) -> None:
    declaration = _declaration()
    offences = reference_offences(
        path.read_bytes(),
        _exists(_held_paths()),
        declaration["path-suffixes"],
        set(declaration["exempt"]),
    )
    filename = path.relative_to(_REPO_ROOT).as_posix()
    assert not offences, reference_message({filename: offences})


def test_every_exemption_is_still_excusing_something() -> None:
    declaration = _declaration()
    stale = stale_exemptions(
        declaration["exempt"], _exists(_held_paths()), _cited_targets()
    )
    assert not stale, "\n".join(
        [
            "an entry in [tool.retusche.documentation-references.exempt] has",
            "stopped being an exemption:",
            "",
            *(f"  {target}: {problem}" for target, problem in sorted(stale.items())),
            "",
            "Remove it. An entry that excuses nothing is a sentence about a",
            "document that has moved on without it.",
        ]
    )
