# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The two places this project states its own version, held together.

``retusche.__version__`` is what a running service reports about itself, in a log
line, a health answer and a bug report. ``[project] version`` in the project file
is what is stamped on the artefact an operator installed. They are edited
separately and there is nothing about editing one that makes anyone look at the
other, so an operator can be told two different numbers for one build.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Final

import retusche

_PROJECT_FILE: Final = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _project_config() -> dict[str, Any]:
    with _PROJECT_FILE.open("rb") as handle:
        return tomllib.load(handle)


def test_the_reported_version_is_the_packaged_version() -> None:
    assert retusche.__version__ == _project_config()["project"]["version"]


def test_the_orchestration_package_exports_its_version() -> None:
    """``__all__`` is what a star import brings over, and the version is the one
    thing in this package worth naming today."""
    assert "__version__" in retusche.__all__
