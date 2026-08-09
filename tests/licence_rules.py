# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The licence header rule, with no pytest and no repository in it.

Kept beside the other harness rules and for the same reason: given plain inputs,
the rule can be exercised against sources this suite writes, so each refusal is
seen on purpose rather than on the day somebody trips it.

``test_licence_headers`` reads the project file and the tree and hands both
here. Nothing in this module knows where any of it came from.
"""

from __future__ import annotations

import re

_COPYRIGHT = re.compile(r"^# Copyright \(C\) \d{4}(-\d{4})? \S.*$")
_IDENTIFIER = re.compile(r"^# SPDX-License-Identifier: (?P<identifier>\S+)$")

MISSING = "missing"
WRONG_IDENTIFIER = "wrong-identifier"


def header_problem(source: bytes, expected: str) -> str | None:
    """What is wrong with this file's header, as one of two named states.

    The two are distinct on purpose. A file that never carried a header and a
    file whose header names a licence this project does not use are different
    mistakes with different repairs, and a check reporting one verdict for both
    tells the second reader to add a header that is already there.

    The header is the first two lines, before the docstring and before any
    import, because that is the only position a reader can rely on finding it in
    and a position that is merely "somewhere near the top" is one that drifts.
    """
    lines = source.decode("utf-8").splitlines()[:2]
    if len(lines) < 2 or not _COPYRIGHT.match(lines[0]):
        return MISSING
    match = _IDENTIFIER.match(lines[1])
    if match is None:
        return MISSING
    if match.group("identifier") != expected:
        return WRONG_IDENTIFIER
    return None


def header_message(path: str, problem: str, expected: str) -> str:
    """What a refused file is told. Names the file, the state and the repair."""
    if problem == WRONG_IDENTIFIER:
        return (
            f"{path}: the SPDX identifier in this file's header is not the one "
            f"[project] license declares in pyproject.toml, which is "
            f"{expected}. One of the two is wrong and nothing else in the tree "
            f"says which, so a reader of this file is told the wrong terms. "
            f"Change whichever is out of date, and if the project's licence "
            f"really has changed, every other file says the old one too."
        )
    return (
        f"{path}: this file carries no licence header. The first two lines of "
        f"every Python file in this repository are a copyright line and "
        f"# SPDX-License-Identifier: {expected}, before the docstring and "
        f"before any import. A source file that travels without them travels "
        f"without its terms, and this project is under a licence whose terms "
        f"reach whoever receives the file."
    )
