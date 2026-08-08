# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Which engines the contract suite runs against.

One entry per engine. The clauses are in `contract_suite` and know nothing about
this list; the wiring that turns it into a run is in `conftest`.

Today the register holds one entry, and a contract with one implementation
proves less than a contract with two. It cannot yet hold more: the second engine
is #18, and the harness that runs these same clause bodies against an engine
needing hardware is #85. Until one of those lands, what this suite establishes
is that the clauses are executable and that the fake meets them, and not that
two engines agree about anything.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from contract_suite import EngineCase

from retusche.testing import FakeEngine

if TYPE_CHECKING:
    from collections.abc import Sequence

ENGINE_CASES: Final[Sequence[EngineCase]] = (
    EngineCase(
        name="fake",
        build=FakeEngine,
        # The fake copies every pixel its mask leaves at zero, so nothing it
        # returns for such a pixel may differ by anything at all. An engine that
        # round-trips the whole frame through an encoder does differ, and its
        # own entry is where that number is stated rather than guessed at.
        unchanged_tolerance=0,
    ),
)
