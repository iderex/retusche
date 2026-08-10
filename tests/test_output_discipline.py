# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Nothing under the judged packages says anything except through the declaration.

`retusche.logging.records` refuses a line carrying a photograph, a prompt, or a
path out of the operator's library. That refusal holds for the lines that go
through it, and until now nothing said the lines had to. A module reaching for
the standard library's logger, or writing to the process's output itself,
produces a line no field set was ever compared against, and `docs/logging.md` is
the page an operator copies into their own record of processing.

The declaration is `[tool.retusche.output-discipline]` in `pyproject.toml`, read
here and never restated. The rule is in `output_rules`, exercised there against
sources written in that file.

What this does not see, and none of it is hypothetical:

- a write through a name the rule cannot resolve: `stdout.write` after
  `from sys import stdout`, an attribute reached through a variable, a function
  fetched by `getattr`, or `os.write(1, ...)`, which is left out because it is
  also how an ordinary file is written and refusing it would refuse the result
  of the job this service exists to do
- a third-party package that logs on its own account once the chain leaves
  `src/`, which is a property of that package and not of this tree
- the worker, which is outside `judged-roots` and says so there, with the reason
- whether a line that does go through the declaration was the right line to write
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Final

from output_rules import Offence, output_message, output_offences

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent
_PROJECT_FILE: Final = _REPO_ROOT / "pyproject.toml"
_SOURCE_ROOT: Final = _REPO_ROOT / "src"


def _declaration() -> dict[str, Any]:
    with _PROJECT_FILE.open("rb") as handle:
        config: dict[str, Any] = tomllib.load(handle)
    discipline: dict[str, Any] = config["tool"]["retusche"]["output-discipline"]
    return discipline


def _module_name(path: Path) -> str:
    relative = path.relative_to(_SOURCE_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _judged_files() -> dict[str, Path]:
    """Every module under the judged roots except the declaring package itself.

    Read off the tree rather than out of a list, so a module added tomorrow is
    judged without anyone registering it, and the package that is exempt is the
    one named in the declaration rather than one spelled again here.
    """
    declaration = _declaration()
    roots: list[str] = declaration["judged-roots"]
    exempt: str = declaration["declared-in"]
    judged: dict[str, Path] = {}
    for path in sorted(_SOURCE_ROOT.rglob("*.py")):
        name = _module_name(path)
        if name.split(".")[0] not in roots:
            continue
        if name == exempt or name.startswith(f"{exempt}."):
            continue
        judged[str(path.relative_to(_REPO_ROOT).as_posix())] = path
    return judged


def test_the_walk_judges_the_packages_the_declaration_names() -> None:
    """A walk matching nothing reports nothing and reads exactly like a walk that
    found the tree clean, so what it covers is asserted before what it found."""
    judged = _judged_files()
    assert judged, "the walk found no module to judge"
    roots = {path.split("/")[1] for path in judged}
    assert roots == set(_declaration()["judged-roots"])


def test_the_exempt_package_is_the_one_everything_else_goes_through() -> None:
    """The exemption is not a free field.

    It is the package holding the module every other module is required to reach,
    and any other value is a package removed from the rule with nothing saying so.
    Without this, ``declared-in`` could name any package in the tree and the walk
    below would agree with itself about the smaller scope.
    """
    declaration = _declaration()
    through: str = declaration["through"]
    exempt: str = declaration["declared-in"]
    assert through == exempt or through.startswith(f"{exempt}.")


def test_the_walk_leaves_out_exactly_the_declaring_package() -> None:
    """What the walk skips is what the declaration says it skips, and no more.

    The test above pins which package that may be. This one pins the walk to it,
    so a skip widened in the code rather than in the declaration is a red run.
    """
    exempt = "src/" + _declaration()["declared-in"].replace(".", "/") + "/"
    judged = set(_judged_files())
    present = {
        str(path.relative_to(_REPO_ROOT).as_posix())
        for path in _SOURCE_ROOT.rglob("*.py")
        if path.relative_to(_REPO_ROOT).parts[1] in _declaration()["judged-roots"]
    }
    left_out = present - judged
    assert left_out, "nothing was skipped, so this asserts nothing"
    assert left_out == {path for path in present if path.startswith(exempt)}


def test_nothing_speaks_around_the_declaration() -> None:
    declaration = _declaration()
    offences: dict[str, list[Offence]] = {}
    for filename, path in _judged_files().items():
        found = output_offences(
            path.read_bytes(),
            declaration["refused-imports"],
            declaration["refused-calls"],
            filename=filename,
        )
        if found:
            offences[filename] = found
    assert not offences, output_message(
        offences, declaration["through"], declaration["prevents"]
    )


def test_every_invariant_the_rule_can_report_carries_its_reason() -> None:
    """A refusal naming an invariant the declaration has no sentence for would
    print an empty reason, and the entry that would notice is this one."""
    declaration = _declaration()
    reported = {
        offence.invariant
        for offence in output_offences(
            b"import logging\nimport sys\nsys.stdout.write('x')\n",
            declaration["refused-imports"],
            declaration["refused-calls"],
        )
    }
    assert reported
    assert reported <= set(declaration["prevents"])
