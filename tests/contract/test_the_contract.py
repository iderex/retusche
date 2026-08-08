# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Every clause, against every registered engine.

One test body for the whole suite, because the alternative is a body per clause
and a body is where an engine-specific branch gets written. What varies is the
pair the run is parameterised over, and neither half of that pair is read by the
clause to decide anything except through the engine's own declaration.

A failure names the engine and the clause, in that order, because the first
question a red run raises is which engine broke and the second is what it broke.
A clause that had nothing to ask of an engine is a skip carrying its reason, not
a pass, so a run covering less than the whole set cannot be read as one that
covered it and found nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from contract_suite import CLAUSES, NotApplicable
from engine_register import ENGINE_CASES

if TYPE_CHECKING:
    from collections.abc import Collection

    from contract_suite import EngineCase


@pytest.mark.parametrize("clause_name", sorted(CLAUSES))
def test_the_engine_meets_the_clause(
    engine_case: EngineCase,
    clause_name: str,
    forbidden_roots: Collection[str],
) -> None:
    """The suite itself."""
    verdict = CLAUSES[clause_name](engine_case, forbidden_roots)
    if isinstance(verdict, NotApplicable):
        pytest.skip(
            f"{engine_case.name}: contract clause '{clause_name}' does not "
            f"apply. {verdict.reason}"
        )
    assert verdict is None, (
        f"{engine_case.name}: contract clause '{clause_name}' broken. {verdict}"
    )


def test_every_registered_engine_answers_to_the_name_it_is_registered_under() -> None:
    """The name in a failure message has to be the engine that produced it.

    A register entry names the engine and the engine names itself, and nothing
    ties the two together. Where they drift, every message this suite writes
    points a reader at the wrong implementation, which is worse than a message
    with no name in it.
    """
    for case in ENGINE_CASES:
        declared = case.build().capabilities().engine_id
        assert case.name == declared, (
            f"registered as {case.name!r} and declares engine_id {declared!r}"
        )


def test_the_register_is_not_empty() -> None:
    """A register nobody filled would make every clause above pass by vacuum.

    pytest reports zero parameterised tests rather than a failure in that case,
    and zero green tests read the same as none having been asked for.
    """
    assert ENGINE_CASES
