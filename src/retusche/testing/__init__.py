# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What the suite uses to stand in for an engine, in one importable place.

This package ships inside `retusche` because what it holds is an implementation
of the engine contract that reaches no device, and the orchestration layer is
what such an implementation stands in for. It is excluded from the wheel by
`[tool.hatch.build.targets.wheel] exclude` in the project file: an operator has
no use for an engine that produces derived noise, and a test double reachable
from an installed service is a thing somebody eventually configures by accident.

Everything here is imported from this name rather than from the module under it,
so that moving a class between modules is not a change to every test that uses
it.
"""

from retusche.testing.fake_engine import FakeEngine, Script

__all__ = ["FakeEngine", "Script"]
