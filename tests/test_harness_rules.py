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
    import_boundary_message,
    import_boundary_offences,
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


# The import-graph rule. The vocabularies below are constructed the same way and
# for the same reason: a graph rule exercised only against this tree is a rule
# whose refusals are each seen once, on the day somebody trips one.

_PERMITTED = frozenset({"app", "contracts"})


def _graph(**modules: str) -> dict[str, bytes]:
    """Modules keyed by dotted name. A double underscore in a keyword is a dot."""
    return {name.replace("__", "."): _source(text) for name, text in modules.items()}


def test_a_clean_graph_offends_nothing() -> None:
    sources = _graph(
        app="from app import jobs\n",
        app__jobs="from contracts.engine import Engine\n",
        contracts="",
        contracts__engine="import dataclasses\n",
    )
    assert (
        import_boundary_offences(
            sources, {"app", "contracts"}, "app", _PERMITTED, _ROOTS
        )
        == []
    )


def test_a_runtime_reached_two_hops_away_is_reported_as_the_whole_chain() -> None:
    """The reason the rule returns a path and not a verdict. A reader is told
    which edge to cut, and the edge is not the one the entry point owns."""
    sources = _graph(
        app="from app import jobs\n",
        app__jobs="from app import render\n",
        app__render="import torch\n",
    )
    chains = import_boundary_offences(sources, {"app"}, "app", _PERMITTED, _ROOTS)
    assert chains == [["app", "app.jobs", "app.render", "torch"]]


def test_an_import_inside_a_function_is_reached() -> None:
    """A deferred import is how a heavy dependency arrives in a process somebody
    meant to keep small, and it is invisible to a module-level rule."""
    sources = _graph(
        app="""
        def probe() -> int:
            import torch

            return torch.cuda.device_count()
        """
    )
    chains = import_boundary_offences(sources, {"app"}, "app", _PERMITTED, _ROOTS)
    assert chains == [["app", "torch"]]


def test_a_project_package_outside_the_permitted_roots_is_refused() -> None:
    """The worker arm, derived from the tree rather than from a list of names."""
    sources = _graph(
        app="from worker.runner import LOOP_INTERVAL\n",
        worker="",
        worker__runner="LOOP_INTERVAL = 5\n",
    )
    chains = import_boundary_offences(
        sources, {"app", "worker"}, "app", _PERMITTED, _ROOTS
    )
    assert chains == [["app", "worker.runner"]]


def test_the_walk_stops_at_the_package_it_refuses() -> None:
    """What the worker imports is the worker's business. Following into it would
    report a chain the orchestration layer cannot act on, and would credit the
    entry point with a runtime it never named."""
    sources = _graph(
        app="import worker\n",
        worker="import torch\n",
    )
    chains = import_boundary_offences(
        sources, {"app", "worker"}, "app", _PERMITTED, _ROOTS
    )
    assert chains == [["app", "worker"]]


def test_a_socket_safe_module_nothing_imports_is_still_judged() -> None:
    """The module written today and wired up tomorrow. Judging only what the
    entry point reaches would let it sit in the tree unexamined until the import
    that makes it reachable lands, which is the change least likely to be read
    as the one that crossed the boundary."""
    sources = _graph(app="", app__orphan="import torch\n")
    chains = import_boundary_offences(sources, {"app"}, "app", _PERMITTED, _ROOTS)
    assert chains == [["app.orphan", "torch"]]


def test_a_relative_import_is_resolved_and_followed() -> None:
    sources = _graph(
        app="from . import jobs\n",
        app__jobs="from .render import fill\n",
        app__render="import diffusers\n",
    )
    chains = import_boundary_offences(sources, {"app"}, "app", _PERMITTED, _ROOTS)
    assert chains == [["app", "app.jobs", "app.render", "diffusers"]]


def test_a_relative_import_beside_a_module_resolves_to_its_package() -> None:
    """``from . import x`` means a different thing in ``app/jobs.py`` than in
    ``app/__init__.py``, which is why the packages are named separately."""
    sources = _graph(
        app="", app__jobs="from . import render\n", app__render="import torch\n"
    )
    chains = import_boundary_offences(sources, {"app"}, "app", _PERMITTED, _ROOTS)
    assert chains == [["app.jobs", "app.render", "torch"]]


def test_a_relative_import_that_walks_past_the_top_is_not_guessed_at() -> None:
    """It resolves to nothing rather than to a top-level name that happens to
    match. A rule that guessed here would report a chain that does not exist."""
    sources = _graph(app="from ... import torch\n")
    assert import_boundary_offences(sources, {"app"}, "app", _PERMITTED, _ROOTS) == []


def test_two_offending_edges_are_both_reported() -> None:
    """One chain fixed leaves the other, so both are named in one run rather
    than one being found after the first repair lands."""
    sources = _graph(
        app="from app import jobs\nfrom app import render\n",
        app__jobs="import torch\n",
        app__render="import onnxruntime\n",
    )
    chains = import_boundary_offences(sources, {"app"}, "app", _PERMITTED, _ROOTS)
    assert chains == [
        ["app", "app.jobs", "torch"],
        ["app", "app.render", "onnxruntime"],
    ]


def test_an_entry_point_that_is_not_in_the_tree_costs_the_chain_its_head() -> None:
    """The degradation the boundary test has an arm against.

    Every offending edge is still found, because the fallback seeds each
    socket-safe module in name order. What is lost is where the chain starts: a
    reader is shown the module that imports the runtime rather than the path
    from the entry point to it, which is the part that says whose problem it is.
    """
    sources = {
        "z_app": b"import a_lib\n",
        "a_lib": b"import torch\n",
    }
    permitted = frozenset({"z_app", "a_lib"})
    assert import_boundary_offences(
        sources, set(sources), "z_app", permitted, _ROOTS
    ) == [["z_app", "a_lib", "torch"]]
    assert import_boundary_offences(
        sources, set(sources), "mistyped", permitted, _ROOTS
    ) == [["a_lib", "torch"]]


def test_the_message_draws_every_chain() -> None:
    """The message is what a reader acts on, so it is read here rather than
    trusted. A message that stopped printing the chain would leave a verdict and
    a package to search by hand."""
    message = import_boundary_message(
        "app", [["app", "app.jobs", "torch"], ["app.orphan", "diffusers"]]
    )
    assert "app -> app.jobs -> torch" in message
    assert "app.orphan -> diffusers" in message
    assert "2 import chain(s)" in message
