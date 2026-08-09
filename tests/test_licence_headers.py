# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Every Python file in this repository carries its terms in its first two lines.

A source file travels. It gets pasted into an issue, vendored into somebody's
tree, and read a long way from the `LICENSE` at the root of this repository.
This project is under a copyleft licence whose terms reach whoever receives the
file, so a file arriving without them arrives misrepresenting itself.

The expected identifier is read from `[project] license` in `pyproject.toml`
rather than written here, so the header and the packaging metadata cannot say
two different things. Changing one and not the other reddens this.

What the walk does not see: a file outside this repository's own directories,
and a licence statement written anywhere but the first two lines. The rule
itself is in `licence_rules`, exercised there against sources this file writes.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Final

import pytest
from licence_rules import (
    MISSING,
    WRONG_IDENTIFIER,
    header_message,
    header_problem,
)

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent
_PROJECT_FILE: Final = _REPO_ROOT / "pyproject.toml"

# Directories holding no tracked Python file. Every cache and every build output
# this project produces begins with a dot or is one of the two names below, so
# the walk skips them by shape rather than by a list that goes stale.
_SKIPPED_DIRECTORY_NAMES: Final = frozenset({"build", "dist", "__pycache__"})


def _declared_identifier() -> str:
    with _PROJECT_FILE.open("rb") as handle:
        identifier: str = tomllib.load(handle)["project"]["license"]
    return identifier


def _python_files() -> list[Path]:
    return sorted(
        path
        for path in _REPO_ROOT.rglob("*.py")
        if not any(
            part.startswith(".") or part in _SKIPPED_DIRECTORY_NAMES
            for part in path.relative_to(_REPO_ROOT).parts
        )
    )


def test_the_walk_finds_the_files_it_is_supposed_to_judge() -> None:
    """A walk that found nothing would pass and mean nothing.

    This is the arm that goes red the day the skip list grows past what it was
    written for, or the day the tree moves and the glob stops matching.
    """
    found = _python_files()
    assert len(found) > 1
    assert Path(__file__).resolve() in found


@pytest.mark.parametrize("path", _python_files(), ids=lambda path: path.name)
def test_every_python_file_carries_its_terms(path: Path) -> None:
    expected = _declared_identifier()
    problem = header_problem(path.read_bytes(), expected)
    assert problem is None, header_message(
        str(path.relative_to(_REPO_ROOT)), problem or MISSING, expected
    )


def test_the_declared_identifier_is_the_one_the_licence_file_holds() -> None:
    """The header points at `LICENSE`, so the two have to be the same licence.

    Read from the licence text rather than asserted, because a project file
    naming one licence over a `LICENSE` holding another is exactly the state a
    header cannot reveal: every file would agree with the project file and every
    file would be wrong.
    """
    licence_text = (_REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert _declared_identifier().startswith("AGPL-3.0")
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in licence_text
    assert "Version 3, 19 November 2007" in licence_text


def test_a_wrong_identifier_and_a_missing_header_are_different_states() -> None:
    """The two refusals a reader has to be able to tell apart.

    Reported as one verdict, the second reader is told to add a header that is
    already there, and goes looking for a file that does not exist.
    """
    assert header_problem(b'"""No header at all."""\n', "AGPL-3.0-only") == MISSING
    assert (
        header_problem(
            b"# Copyright (C) 2026 Nils Lehnen\n# SPDX-License-Identifier: MIT\n",
            "AGPL-3.0-only",
        )
        == WRONG_IDENTIFIER
    )


def test_a_header_that_is_not_first_is_not_a_header() -> None:
    """The position is the rule. A licence line somewhere in the file is one a
    reader has to go looking for, and one a reader who does not find it in the
    first two lines concludes is absent."""
    source = (
        b'"""A docstring above everything."""\n'
        b"\n"
        b"# Copyright (C) 2026 Nils Lehnen\n"
        b"# SPDX-License-Identifier: AGPL-3.0-only\n"
    )
    assert header_problem(source, "AGPL-3.0-only") == MISSING


def test_a_year_range_is_accepted() -> None:
    """A file edited across two years carries both, and refusing that would make
    the repair an edit to every other file."""
    source = (
        b"# Copyright (C) 2026-2027 Nils Lehnen\n"
        b"# SPDX-License-Identifier: AGPL-3.0-only\n"
    )
    assert header_problem(source, "AGPL-3.0-only") is None


def test_a_copyright_line_naming_nobody_is_refused() -> None:
    """A year and no holder is a template somebody forgot to fill in."""
    source = b"# Copyright (C) 2026\n# SPDX-License-Identifier: AGPL-3.0-only\n"
    assert header_problem(source, "AGPL-3.0-only") == MISSING


def test_an_empty_file_is_refused_rather_than_passed_over() -> None:
    """Nothing to read is not the same as nothing wrong."""
    assert header_problem(b"", "AGPL-3.0-only") == MISSING


def test_each_message_names_the_file_and_the_repair() -> None:
    """A refusal a reader cannot act on is a refusal that gets worked around."""
    missing = header_message("src/retusche/thing.py", MISSING, "AGPL-3.0-only")
    assert "src/retusche/thing.py" in missing
    assert "AGPL-3.0-only" in missing
    assert "first two lines" in missing

    wrong = header_message("src/retusche/thing.py", WRONG_IDENTIFIER, "AGPL-3.0-only")
    assert "pyproject.toml" in wrong
    assert wrong != missing
