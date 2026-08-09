# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Each layer rule, run against a tree built to break exactly that rule.

The trees here are fixtures rather than this repository. A rule whose refusing arm
is only ever reached on the day somebody trips it is a rule nobody has seen work,
and a rule judged against the real tree proves the state of the tree on the day it
ran rather than the rule.

Every violation below is written as the mistake somebody would actually make. A
contract module recording the version it was built against is a plausible line
that a formatter, a linter and a type checker all pass, and it was written into
this tree once to measure that every gate did pass it. An engine reaching for the
test double as a fallback is the same shape on the other side of the boundary. An
import inside a function body is how either arrives when somebody wants it to look
conditional.
"""

from __future__ import annotations

from layer_rules import layer_message, layer_offences, layer_table_problems

_CONTRACTS_MAY_REACH = frozenset({"retusche_contracts"})
_WORKER_MAY_REACH = frozenset({"retusche_worker", "retusche_contracts"})

_PACKAGES = frozenset(
    {
        "retusche",
        "retusche.testing",
        "retusche_contracts",
        "retusche_worker",
        "retusche_worker.engines",
    }
)

_CLEAN_TREE: dict[str, bytes] = {
    "retusche": b"from retusche_contracts import Engine\n\n__all__ = ['Engine']\n",
    "retusche.testing": b"from retusche_contracts import Engine\n",
    "retusche_contracts": b"import dataclasses\n\n"
    b"from retusche_contracts import engine\n",
    "retusche_contracts.engine": b"import enum\n",
    "retusche_worker": b"from retusche_contracts import Engine\n",
    "retusche_worker.engines": b"from retusche_contracts.engine import Engine\n",
}


def _tree(**overrides: bytes) -> dict[str, bytes]:
    """The clean tree with one module replaced. One change per fixture."""
    return _CLEAN_TREE | overrides


def _packages(tree: dict[str, bytes]) -> frozenset[str]:
    return frozenset(name for name in tree if name in _PACKAGES)


def test_a_clean_tree_is_refused_nothing() -> None:
    """The passing arm. A rule that refused everything would pass every other
    test in this file and refuse the tree it ships in."""
    for layer, permitted in (
        ("retusche_contracts", _CONTRACTS_MAY_REACH),
        ("retusche_worker", _WORKER_MAY_REACH),
    ):
        assert not layer_offences(_CLEAN_TREE, _packages(_CLEAN_TREE), layer, permitted)


def test_a_contract_recording_the_version_it_was_built_against_is_refused() -> None:
    """The near miss this rule exists for.

    It is used, so nothing calls it an unused import; it is in sorted position, so
    the import sorter is content; it is a plain module attribute, so the type
    checker is content. Every gate in this repository passed this line while the
    contract package was reaching into the layer it is owned by neither of.
    """
    tree = _tree(
        retusche_contracts=b"from retusche import __version__\n\n"
        b"_BUILT_AGAINST = __version__\n"
    )
    chains = layer_offences(
        tree, _packages(tree), "retusche_contracts", _CONTRACTS_MAY_REACH
    )
    assert chains == [["retusche_contracts", "retusche"]]


def test_a_contract_deferring_the_import_into_a_function_is_refused() -> None:
    """The same mistake written to look conditional.

    A deferred import is still an import the moment the function runs, and it is
    where somebody puts one they know does not belong at the top of the file.
    """
    tree = _tree(
        **{
            "retusche_contracts.engine": b"def built_against() -> str:\n"
            b"    from retusche import __version__\n\n"
            b"    return __version__\n"
        }
    )
    chains = layer_offences(
        tree, _packages(tree), "retusche_contracts", _CONTRACTS_MAY_REACH
    )
    assert chains == [["retusche_contracts", "retusche_contracts.engine", "retusche"]]


def test_a_worker_reaching_for_the_test_double_is_refused() -> None:
    """An engine borrowing the fake as a fallback, which is the plausible one.

    The fake implements the contract and needs no device, so it looks like the
    right thing to fall back to. It lives in the orchestration package, so
    reaching it makes the worker process import the orchestrator.
    """
    tree = _tree(
        **{
            "retusche_worker.engines": b"from retusche.testing import FakeEngine\n\n"
            b"FALLBACK = FakeEngine\n"
        }
    )
    chains = layer_offences(tree, _packages(tree), "retusche_worker", _WORKER_MAY_REACH)
    assert chains == [["retusche_worker.engines", "retusche.testing"]]


def test_a_worker_module_nothing_imports_is_still_judged() -> None:
    """A module no other module imports yet is exactly what the next change
    reaches, and a walk that only followed edges from the package root would call
    it clean."""
    tree = _tree(
        **{"retusche_worker.engines": b"import retusche\n"},
        retusche_worker=b"from retusche_contracts import Engine\n",
    )
    chains = layer_offences(tree, _packages(tree), "retusche_worker", _WORKER_MAY_REACH)
    assert chains == [["retusche_worker.engines", "retusche"]]


def test_the_message_carries_the_chain_and_the_declared_set() -> None:
    """A verdict without the chain leaves a reader a package to search by hand."""
    message = layer_message(
        "retusche_contracts",
        _CONTRACTS_MAY_REACH,
        [["retusche_contracts", "retusche"]],
    )
    assert "retusche_contracts -> retusche" in message
    assert "may reach only retusche_contracts" in message
    assert "[tool.retusche.layer-imports] in pyproject.toml" in message


def test_a_package_no_rule_judges_is_refused() -> None:
    """The fail-closed half. A package arriving under src/ is unjudged until
    somebody decides what it may reach, and unjudged has to be loud."""
    problems = layer_table_problems(
        {"retusche", "retusche_worker", "retusche_images"},
        {"retusche_worker": frozenset({"retusche_worker"})},
        {"retusche"},
    )
    assert len(problems) == 1
    assert "retusche_images" in problems[0]


def test_a_row_for_a_package_that_is_not_there_is_refused() -> None:
    """A row whose name does not match a package walks nothing and says nothing,
    which reads exactly like a layer that was walked and was clean."""
    worker_only = frozenset({"retusche_worker"})
    problems = layer_table_problems(
        {"retusche", "retusche_worker"},
        {"retusche_worker": worker_only, "retusche_wroker": worker_only},
        {"retusche"},
    )
    assert len(problems) == 1
    assert "retusche_wroker" in problems[0]


def test_a_package_two_rules_both_judge_is_refused() -> None:
    """Two permitted sets for one package is a verdict a reader cannot place."""
    problems = layer_table_problems(
        {"retusche", "retusche_worker", "retusche_contracts"},
        {
            "retusche": frozenset({"retusche", "retusche_contracts"}),
            "retusche_worker": _WORKER_MAY_REACH,
            "retusche_contracts": _CONTRACTS_MAY_REACH,
        },
        {"retusche"},
    )
    assert len(problems) == 1
    assert "judged by two rules at once: retusche." in problems[0]


def test_a_row_permitting_a_package_that_is_not_there_is_refused() -> None:
    """A misspelled permission refuses the import it was written to allow, and
    the refusal names a package nobody can find."""
    problems = layer_table_problems(
        {"retusche", "retusche_worker"},
        {"retusche_worker": frozenset({"retusche_worker", "retusche_contract"})},
        {"retusche"},
    )
    assert len(problems) == 1
    assert "retusche_worker -> retusche_contract" in problems[0]


def test_a_table_that_agrees_with_the_tree_is_refused_nothing() -> None:
    """The passing arm of the accounting rule."""
    assert not layer_table_problems(
        {"retusche", "retusche_worker", "retusche_contracts"},
        {
            "retusche_worker": _WORKER_MAY_REACH,
            "retusche_contracts": _CONTRACTS_MAY_REACH,
        },
        {"retusche"},
    )
