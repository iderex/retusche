# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The harness judged by the same standard as everything else it judges.

Every input here is written in this file. None of these tests reads the real
project file or the real ``src/`` directory, and that is the point: a rule
exercised against this repository proves the state of the repository on the day
it ran, and says nothing about what the rule does on the input that has not
arrived yet.

The sources below are strings. They are parsed, never imported, so a forbidden
name appearing in one is a name in a string literal and the discovery rule that
reads this file finds nothing to refuse in it.
"""

from __future__ import annotations

import textwrap

import pytest
from harness_rules import (
    coverage_scope_lines,
    coverage_scope_problems,
    forbidden_import_message,
    module_level_forbidden_imports,
)

_ROOTS = frozenset({"torch", "diffusers", "onnxruntime"})


def _source(text: str) -> bytes:
    return textwrap.dedent(text).lstrip("\n").encode()


def test_a_plain_import_is_found_with_its_line() -> None:
    found = module_level_forbidden_imports(
        _source("""
        import os

        import torch
        """),
        _ROOTS,
    )
    assert found == [(3, "torch")]


def test_a_submodule_import_is_found_and_reported_as_written() -> None:
    """The rule matches the root and reports the whole dotted name, so a reader
    is told what the file says rather than what the rule matched on."""
    found = module_level_forbidden_imports(
        _source("import torch.nn.functional\n"), _ROOTS
    )
    assert found == [(1, "torch.nn.functional")]


def test_a_from_import_is_found() -> None:
    found = module_level_forbidden_imports(
        _source("from diffusers.pipelines import Pipeline\n"), _ROOTS
    )
    assert found == [(1, "diffusers.pipelines")]


def test_an_aliased_import_is_found() -> None:
    """``as`` renames the binding, not the module, and the rule reads the
    module."""
    found = module_level_forbidden_imports(_source("import torch as t\n"), _ROOTS)
    assert found == [(1, "torch")]


def test_an_import_under_type_checking_is_found() -> None:
    """The near miss the rule exists for. It never executes, the annotation using
    it is a string, and both the linter and the type checker are content."""
    found = module_level_forbidden_imports(
        _source("""
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from torch import Tensor
        """),
        _ROOTS,
    )
    assert found == [(4, "torch")]


def test_an_import_in_a_class_body_is_found() -> None:
    found = module_level_forbidden_imports(
        _source("""
        class Holder:
            import onnxruntime
        """),
        _ROOTS,
    )
    assert found == [(2, "onnxruntime")]


def test_an_import_in_a_try_block_is_found() -> None:
    """The shape somebody reaches for to make a hard dependency look optional."""
    found = module_level_forbidden_imports(
        _source("""
        try:
            import torch
        except ImportError:
            torch = None
        """),
        _ROOTS,
    )
    assert found == [(2, "torch")]


def test_an_import_inside_a_function_is_not_found() -> None:
    """The boundary the rule draws, stated as a test rather than as a comment. A
    test may reach for the runtime inside a body it never calls without weights
    present; what is refused is a module that cannot be imported without one."""
    assert (
        module_level_forbidden_imports(
            _source("""
            def load():
                import torch

                return torch
            """),
            _ROOTS,
        )
        == []
    )


def test_an_import_inside_an_async_function_is_not_found() -> None:
    assert (
        module_level_forbidden_imports(
            _source("""
            async def load():
                import torch

                return torch
            """),
            _ROOTS,
        )
        == []
    )


def test_a_module_whose_name_merely_starts_with_a_root_is_not_found() -> None:
    """The one-character mistake in the other direction. Matching on a prefix
    rather than on the dotted root would refuse an unrelated package and the
    refusal would name a rule the file does not break."""
    assert module_level_forbidden_imports(_source("import torchless\n"), _ROOTS) == []


def test_a_relative_import_is_not_found() -> None:
    """A relative import cannot reach a top-level runtime. Matching one on its
    written name would refuse a local module for sharing a name."""
    assert (
        module_level_forbidden_imports(_source("from .torch import helper\n"), _ROOTS)
        == []
    )


def test_an_allowed_import_is_not_found() -> None:
    assert (
        module_level_forbidden_imports(
            _source("""
            import retusche_contracts
            from pathlib import Path
            """),
            _ROOTS,
        )
        == []
    )


def test_every_offence_in_one_file_is_reported() -> None:
    """Not only the first. A file fixed one line at a time, with a fresh run
    between each, is a file somebody gives up on."""
    found = module_level_forbidden_imports(
        _source("""
        import torch
        import diffusers
        """),
        _ROOTS,
    )
    assert found == [(1, "torch"), (2, "diffusers")]


def test_the_refusal_names_the_file_the_line_and_the_module() -> None:
    """A refusal a reader cannot act on is a refusal that gets worked around."""
    message = forbidden_import_message("tests/test_thing.py", [(19, "torch")])
    assert "tests/test_thing.py" in message
    assert "line 19" in message
    assert "torch" in message
    assert "hardware harness" in message


def test_a_package_in_neither_list_is_refused() -> None:
    """The state nobody is told anything about: absent from the report because
    coverage never looked, absent from the exclusions because nobody wrote a
    reason, and the two absences read identically."""
    problems = coverage_scope_problems(
        in_tree={"alpha", "beta"}, measured={"alpha"}, excluded={}
    )
    assert len(problems) == 1
    assert "beta" in problems[0]


def test_a_package_in_both_lists_is_refused() -> None:
    problems = coverage_scope_problems(
        in_tree={"alpha"}, measured={"alpha"}, excluded={"alpha": "a reason"}
    )
    assert len(problems) == 1
    assert "both measured and excluded" in problems[0]


def test_a_configured_package_that_does_not_exist_is_refused() -> None:
    """A source entry matching nothing measures nothing and says so nowhere, so
    the run reads exactly like one where the package was clean."""
    problems = coverage_scope_problems(
        in_tree={"alpha"}, measured={"alpha", "typo"}, excluded={}
    )
    assert len(problems) == 1
    assert "typo" in problems[0]


def test_an_excluded_package_that_does_not_exist_is_refused() -> None:
    problems = coverage_scope_problems(
        in_tree={"alpha"}, measured={"alpha"}, excluded={"gone": "a reason"}
    )
    assert len(problems) == 1
    assert "gone" in problems[0]


def test_several_problems_are_all_reported() -> None:
    problems = coverage_scope_problems(
        in_tree={"alpha", "beta"}, measured={"typo"}, excluded={}
    )
    assert len(problems) == 2


def test_an_agreeing_configuration_is_accepted() -> None:
    assert (
        coverage_scope_problems(
            in_tree={"alpha", "beta"},
            measured={"alpha"},
            excluded={"beta": "a reason"},
        )
        == []
    )


def test_the_printed_scope_carries_the_reason_for_each_exclusion() -> None:
    """The disclosure the whole second rule is for. A report that omitted the
    package silently would read as one where it was measured and complete."""
    lines = coverage_scope_lines(
        measured={"alpha"}, excluded={"beta": "no unit test loads it"}
    )
    assert lines == [
        "measured: alpha",
        "not measured: beta - no unit test loads it",
    ]


@pytest.mark.parametrize("roots", [frozenset(), frozenset({"torch"})])
def test_an_empty_file_offends_nothing(roots: frozenset[str]) -> None:
    assert module_level_forbidden_imports(b"", roots) == []
