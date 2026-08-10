# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The three places the hardware marker is written, held to one string.

The marker is a word three mechanisms have to agree on. pytest registers it, the
default run deselects it, and the discovery rule in ``conftest.py`` refuses an
unmarked test that reaches for a runtime. Each of the three works perfectly well
on its own while disagreeing with the other two, and every disagreement fails in
the quiet direction: a registration nothing selects on, a selection matching no
registered marker, a rule naming a word pytest has never heard of. In all three
the suite is green and the gate is off.

So the string is data, in ``[tool.retusche.hardware-harness]``, and this file is
what turns a rename that reached two of the three into a red run.

These tests read the real project file, which is what they are about. The rules
themselves take their inputs as arguments and are exercised in
``test_harness_rules``. What is left over is the wiring between the two, and the
last pair here holds it: a rule that decides correctly and is never asked decides
nothing, and nothing else in this suite would notice the call going missing.
"""

from __future__ import annotations

import importlib.util
import textwrap
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any, Final, cast

import pytest

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent
_PROJECT_FILE: Final = _REPO_ROOT / "pyproject.toml"
_ROOT_CONFTEST: Final = _REPO_ROOT / "tests" / "conftest.py"

# The hook deletes this argument before it does anything, and a real collector
# cannot be built without a running collection. The cast says so in one place.
_NO_COLLECTOR: Final = cast("pytest.Collector", object())

_UNMARKED = """
def test_edit() -> None:
    import torch

    assert torch.cuda.is_available()
"""

_MARKED = """
import pytest


@pytest.mark.hardware
def test_edit() -> None:
    import torch

    assert torch.cuda.is_available()
"""


def _project_config() -> dict[str, Any]:
    with _PROJECT_FILE.open("rb") as handle:
        return tomllib.load(handle)


def _collection_hooks() -> ModuleType:
    """``tests/conftest.py``, loaded by path rather than by name.

    Three files in this suite are called ``conftest.py``. ``import conftest``
    therefore resolves to whichever one pytest happened to load first, which is
    a different module depending on what else the run collected, and a test that
    passes alone and fails in the suite is worse than no test. The path is
    unambiguous.
    """
    spec = importlib.util.spec_from_file_location("root_conftest", _ROOT_CONFTEST)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _marker() -> str:
    marker: str = _project_config()["tool"]["retusche"]["hardware-harness"]["marker"]
    return marker


def _pytest_options() -> dict[str, Any]:
    options: dict[str, Any] = _project_config()["tool"]["pytest"]["ini_options"]
    return options


def test_the_marker_is_registered_under_the_name_the_rule_reads() -> None:
    """--strict-markers refuses an unregistered marker, so a test carrying one
    the table does not declare fails collection. That is the right default and it
    is also how a rename loses the marker without losing the rule."""
    declared = [entry.split(":", 1)[0] for entry in _pytest_options()["markers"]]
    assert _marker() in declared


def test_every_registered_marker_says_what_it_is_for() -> None:
    """A bare name in the table is a marker whose meaning lives in whoever added
    it, and --strict-markers will accept it on any test from then on."""
    for entry in _pytest_options()["markers"]:
        name, _, description = entry.partition(":")
        assert name.strip(), entry
        assert description.strip(), entry


def test_the_default_run_deselects_the_marked_set() -> None:
    """The third Done-when line of #84: excluded by configuration and not by a
    flag a contributor has to remember. A flag is remembered everywhere except
    the machine that has a device in it, which is the machine where forgetting it
    looks like a green run."""
    addopts: list[str] = _pytest_options()["addopts"]
    assert "-m" in addopts
    assert addopts[addopts.index("-m") + 1] == f"not {_marker()}"


def test_the_selection_and_the_marker_table_cannot_drift_apart() -> None:
    """The failure this file exists for, stated as its own test: a selection
    naming a marker nobody registered matches nothing and reports nothing, so the
    suite runs everything and reads exactly like one where nothing was marked."""
    options = _pytest_options()
    addopts: list[str] = options["addopts"]
    selected = addopts[addopts.index("-m") + 1].removeprefix("not ")
    declared = [entry.split(":", 1)[0] for entry in options["markers"]]
    assert selected in declared


def test_strict_markers_is_still_on() -> None:
    """Without it an invented marker is silently accepted, and the deselection
    above would be a filter over a word no test actually carries."""
    assert "--strict-markers" in _pytest_options()["addopts"]


def test_collection_refuses_an_unmarked_test_that_reaches_for_a_device(
    tmp_path: Path,
) -> None:
    """The gate, driven through the hook the run actually calls.

    The file is written outside this repository and is never imported: the
    refusal happens while it is bytes on disk, which is the point of deciding at
    collection rather than at the assertion.
    """
    offender = tmp_path / "test_needs_a_device.py"
    offender.write_text(textwrap.dedent(_UNMARKED).lstrip("\n"), encoding="utf-8")
    with pytest.raises(pytest.UsageError) as refusal:
        _collection_hooks().pytest_collect_file(offender, _NO_COLLECTOR)
    assert "test_needs_a_device.py" in str(refusal.value)
    assert f"@pytest.mark.{_marker()}" in str(refusal.value)


def test_collection_accepts_the_same_test_once_it_says_what_it_needs(
    tmp_path: Path,
) -> None:
    """The other arm, and the one that stops the rule from being a ban. A gate
    that refused the marked form too would leave the hardware harness with no
    legal way to import anything, and the repair somebody would reach for is
    removing the gate."""
    marked = tmp_path / "test_needs_a_device.py"
    marked.write_text(textwrap.dedent(_MARKED).lstrip("\n"), encoding="utf-8")
    assert _collection_hooks().pytest_collect_file(marked, _NO_COLLECTOR) is None
