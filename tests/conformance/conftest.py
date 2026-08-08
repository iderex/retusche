# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Where the layer rules meet this repository.

The rules are in `layer_rules` and know nothing about a tree or a project file.
What is here is the wiring: read the declared sets out of `pyproject.toml` and
hand them over.

The tree itself is not read again. `source_modules` and `source_packages` come
from the suite's root conftest, which already reads `src/` for the boundary rule,
so a module added tomorrow reaches both rules through one walk of the disk.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Final

import pytest

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent.parent
_PROJECT_FILE: Final = _REPO_ROOT / "pyproject.toml"


def _project_config() -> dict[str, Any]:
    with _PROJECT_FILE.open("rb") as handle:
        return tomllib.load(handle)


@pytest.fixture(scope="session")
def layer_imports() -> dict[str, frozenset[str]]:
    """Each layer and the project packages it may reach, itself included."""
    rows: dict[str, list[str]] = _project_config()["tool"]["retusche"]["layer-imports"]
    return {layer: frozenset(permitted) for layer, permitted in rows.items()}
