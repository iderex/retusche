# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What this project says about the artefact it builds, held to the tree.

``retusche.__version__`` is what a running service reports about itself, in a log
line, a health answer and a bug report. ``[project] version`` in the project file
is what is stamped on the artefact an operator installed. They are edited
separately and there is nothing about editing one that makes anyone look at the
other, so an operator can be told two different numbers for one build.

The wheel's exclusion list is here for the same reason: it names a directory in
this tree, and a directory that moves leaves the name behind.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Final

import retusche

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent
_PROJECT_FILE: Final = _REPO_ROOT / "pyproject.toml"

# The one package under src/ that is built and not shipped, named once.
_UNSHIPPED: Final = "src/retusche/testing"


def _project_config() -> dict[str, Any]:
    with _PROJECT_FILE.open("rb") as handle:
        return tomllib.load(handle)


def _wheel_exclusions() -> list[str]:
    wheel: dict[str, Any] = _project_config()["tool"]["hatch"]["build"]["targets"][
        "wheel"
    ]
    excluded: list[str] = wheel["exclude"]
    return excluded


def test_the_reported_version_is_the_packaged_version() -> None:
    assert retusche.__version__ == _project_config()["project"]["version"]


def test_the_orchestration_package_exports_its_version() -> None:
    """``__all__`` is what a star import brings over, and the version is the one
    thing in this package worth naming today."""
    assert "__version__" in retusche.__all__


def test_the_test_double_is_excluded_from_the_wheel() -> None:
    """``retusche.testing`` is built into the tree and kept out of the artefact.

    It holds an implementation of the engine contract that reaches no device and
    produces derived noise. Shipped, it would be an engine an operator can
    select, and the accident is silent: the jobs succeed and the photographs
    come back as noise.

    WHAT THIS ESTABLISHES IS THAT THE LINE IS THERE AND NAMES A REAL DIRECTORY,
    NOT THAT A BUILT WHEEL OMITS IT. Building one here would need hatchling in
    the dev group, and adding a dependency to check a configuration line is a
    cost paid on every sync by everyone. The path is anchored with a leading
    slash so the pattern cannot match a ``testing`` directory somewhere else.
    """
    assert f"/{_UNSHIPPED}" in _wheel_exclusions()


def test_the_excluded_path_is_a_package_in_the_tree() -> None:
    """The half of the rule above that goes red on its own.

    An exclusion naming a directory that has moved excludes nothing and reports
    nothing, so the package it was written for ships and the line that was
    supposed to stop it is still sitting in the project file being read as
    proof.
    """
    assert (_REPO_ROOT / _UNSHIPPED / "__init__.py").is_file()


def test_nothing_else_under_src_is_excluded_without_being_noticed() -> None:
    """An exclusion list is a place a package disappears from an artefact
    quietly. One entry is a decision somebody made; a second arriving beside it
    is a decision nobody reviewed, and this is what asks for the review."""
    assert _wheel_exclusions() == [f"/{_UNSHIPPED}"]
