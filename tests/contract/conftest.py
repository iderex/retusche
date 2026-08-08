# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Where the contract clauses meet the engines they are run against.

The register is in `engine_register` and the clauses are in `contract_suite`.
What is here is one fixture, which turns the register into one run of every
clause per engine.

The clauses also want the module roots that stand for a machine-learning
runtime. That fixture is already in the suite's own root conftest, reading them
out of the project file, so nothing here declares a second copy of the list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from engine_register import ENGINE_CASES

if TYPE_CHECKING:
    from contract_suite import EngineCase


@pytest.fixture(params=ENGINE_CASES, ids=lambda case: case.name)
def engine_case(request: pytest.FixtureRequest) -> EngineCase:
    """One registered engine. Every clause runs once against each."""
    case: EngineCase = request.param
    return case
