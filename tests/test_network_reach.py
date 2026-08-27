# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Nothing under the judged packages reaches a host except the download.

The reason this project exists is that the photographs are processed where they
already live. Until this file landed, what stood behind that was the fact that
nobody had written an outbound call yet: a component that acquired one would
have left every route in this repository as green as one that had not.

The declaration is ``[tool.retusche.network-reach]`` in ``pyproject.toml``, read
here and never restated. The rule is in ``network_rules``, exercised there
against sources written in that file.

What this does not see, and none of it is hypothetical:

- a connection opened through a name the rule cannot resolve: ``socket()`` after
  ``from socket import socket`` is caught by the import arm instead, but an
  attribute reached through a variable, a module fetched by ``importlib`` or a
  name assembled at runtime is caught by neither
- ``os.system``, ``subprocess`` and the rest of the ways a process can ask
  something else to make the call. They are not in the declaration because they
  are also how the worker is launched, and refusing them here would refuse the
  architecture this project chose
- the worker, which is outside ``judged-roots`` and says so there, with the
  reason
- a third-party package that phones home on its own account once the chain
  leaves ``src/``, which is a property of that package and not of this tree.
  There are no runtime dependencies today, so the population is empty rather
  than unexamined
- whether the one module permitted to reach a host reaches the right one. That
  is the source in a registry entry, and ``retusche.models.registry`` is where a
  URL is judged
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Final

from network_rules import Reach, network_message, network_offences

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent
_PROJECT_FILE: Final = _REPO_ROOT / "pyproject.toml"
_SOURCE_ROOT: Final = _REPO_ROOT / "src"


def _declaration() -> dict[str, Any]:
    with _PROJECT_FILE.open("rb") as handle:
        config: dict[str, Any] = tomllib.load(handle)
    reach: dict[str, Any] = config["tool"]["retusche"]["network-reach"]
    return reach


def _module_name(path: Path) -> str:
    relative = path.relative_to(_SOURCE_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _all_modules() -> dict[str, Path]:
    return {
        _module_name(path): path
        for path in sorted(_SOURCE_ROOT.rglob("*.py"))
        if _module_name(path).split(".")[0] in _declaration()["judged-roots"]
    }


def _judged_files() -> dict[str, Path]:
    """Every module under the judged roots except the one permitted to reach out.

    Read off the tree rather than out of a list, so a module added tomorrow is
    judged without anyone registering it, and the module that is exempt is the
    one named in the declaration rather than one spelled again here.
    """
    exempt = _declaration()["through"]
    return {
        str(path.relative_to(_REPO_ROOT).as_posix()): path
        for name, path in _all_modules().items()
        if name != exempt
    }


def test_the_walk_judges_the_packages_the_declaration_names() -> None:
    """A walk matching nothing reports nothing and reads exactly like a walk that
    found the tree clean, so what it covers is asserted before what it found."""
    judged = _judged_files()
    assert judged
    roots = {path.split("/")[1] for path in judged}
    assert roots == set(_declaration()["judged-roots"])


def test_the_exempt_module_is_one_this_tree_holds() -> None:
    """``through`` is not a free field. A value naming no module in the tree
    would exempt nothing and the walk below would agree with itself about the
    larger scope, which is the failure that reads as a passing check."""
    assert _declaration()["through"] in _all_modules()


def test_the_exempt_module_is_the_one_that_actually_reaches_out() -> None:
    """The exemption has to be earning itself.

    A module exempted from this rule and reaching no host is an exemption
    nothing needs, and the day the download moves elsewhere this is what says so
    rather than leaving a hole named after a module that no longer uses it.
    """
    declaration = _declaration()
    exempt = _all_modules()[declaration["through"]]
    found = network_offences(
        exempt.read_bytes(),
        declaration["refused-imports"],
        declaration["refused-calls"],
        filename=declaration["through"],
    )
    assert found, "the exempt module reaches no host, so the exemption excuses nothing"


def test_the_walk_leaves_out_exactly_the_exempt_module() -> None:
    """What the walk skips is what the declaration says it skips, and no more."""
    exempt = "src/" + _declaration()["through"].replace(".", "/") + ".py"
    left_out = {
        str(path.relative_to(_REPO_ROOT).as_posix()) for path in _all_modules().values()
    } - set(_judged_files())
    assert left_out == {exempt}


def test_nothing_else_reaches_a_host() -> None:
    declaration = _declaration()
    offences: dict[str, list[Reach]] = {}
    for filename, path in _judged_files().items():
        found = network_offences(
            path.read_bytes(),
            declaration["refused-imports"],
            declaration["refused-calls"],
            filename=filename,
        )
        if found:
            offences[filename] = found
    assert not offences, network_message(
        offences, declaration["through"], declaration["prevents"]
    )


def test_every_invariant_the_rule_can_report_carries_its_reason() -> None:
    """A refusal naming an invariant the declaration has no sentence for would
    print an empty reason, and the entry that would notice is this one."""
    declaration = _declaration()
    reported = {
        offence.invariant
        for offence in network_offences(
            b"import socket\nimport urllib.request\nsocket.socket()\n",
            declaration["refused-imports"],
            declaration["refused-calls"],
        )
    }
    assert reported
    assert reported <= set(declaration["prevents"])
