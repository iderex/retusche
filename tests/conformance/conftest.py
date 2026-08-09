# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Where the conformance rules meet this repository.

The rules are in `layer_rules` and `engine_rules`, and neither knows about a
tree, a project file or a register. What is here is the wiring: read the declared
sets out of `pyproject.toml`, read the interface out of the contract, read the
register out of the contract suite, and hand all of it over.

The tree itself is not read again. `source_modules` and `source_packages` come
from the suite's root conftest, which already reads `src/` for the boundary rule,
so a module added tomorrow reaches every rule through one walk of the disk.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any, Final

import pytest

from retusche_contracts import engine as engine_contract

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent.parent
_PROJECT_FILE: Final = _REPO_ROOT / "pyproject.toml"
_CONTRACT_SUITE: Final = _REPO_ROOT / "tests" / "contract"


def _project_config() -> dict[str, Any]:
    with _PROJECT_FILE.open("rb") as handle:
        return tomllib.load(handle)


@pytest.fixture(scope="session")
def layer_imports() -> dict[str, frozenset[str]]:
    """Each layer and the project packages it may reach, itself included."""
    rows: dict[str, list[str]] = _project_config()["tool"]["retusche"]["layer-imports"]
    return {layer: frozenset(permitted) for layer, permitted in rows.items()}


@pytest.fixture(scope="session")
def engine_interface_methods() -> frozenset[str]:
    """The method names the engine interface declares, read off the declaration.

    Public callables in the protocol's own namespace, which is the three the
    contract states and whatever a later change adds beside them. Naming them
    here instead would be a second copy of the interface, and the copy is what
    goes stale.
    """
    return frozenset(
        name
        for name, member in vars(engine_contract.Engine).items()
        if not name.startswith("_") and callable(member)
    )


@pytest.fixture(scope="session")
def registered_engines() -> frozenset[str]:
    """Every engine the contract suite runs its clauses against.

    The register is a module in `tests/contract/`, which is a sibling directory
    rather than an importable package, so the path it is reached through is
    added here rather than left to whichever directory pytest happened to insert
    first. A fixture that depended on collection order would pass or fail by the
    alphabet.

    Each entry is asked to build its engine, and the class is taken from the
    instance. An entry's build is a callable rather than necessarily a class, so
    reading the attribute would answer for a factory function instead of for the
    engine it returns. The contract register holds engines that reach no device
    by construction; one that needs hardware belongs in the harness register in
    #85, which this rule does not read.
    """
    if str(_CONTRACT_SUITE) not in sys.path:
        sys.path.insert(0, str(_CONTRACT_SUITE))
    from engine_register import ENGINE_CASES

    built = [type(case.build()) for case in ENGINE_CASES]
    return frozenset(f"{cls.__module__}.{cls.__qualname__}" for cls in built)
