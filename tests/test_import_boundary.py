# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The heavy runtime stays out of the process that listens on a socket.

Two reasons, and neither is style. A crash or an out-of-memory kill inside a
native tensor library takes the whole process down with it, and the queue has to
survive that, which it cannot do from inside the same process. And the
dependency surface reachable from a socket should be as small as the work
allows, which it is not if it transitively includes a deep-learning framework.

The boundary is a property this file refuses a violation of. It is a static walk
over the tree rather than an import of the packages under test, so it judges a
module no runtime path has reached yet, and it needs none of the forbidden
packages to be installed in order to say that something reaches them.

What the walk cannot see, written here rather than left for a reader to work
out. It reads import statements, so a module loaded through ``importlib``,
through ``__import__`` with a name assembled at runtime, or through a plugin
entry point some library resolves for itself, is invisible to it. So is a
subprocess, which is what the worker is and is the whole point of the
arrangement. And it judges this repository's own tree: a third-party package the
orchestration layer imports may pull in anything it likes, and nothing here
looks past the first hop out of ``src/``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from harness_rules import import_boundary_message, import_boundary_offences

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping


def test_the_entry_point_is_a_module_in_the_tree(
    source_modules: Mapping[str, bytes],
    orchestration_entry_point: str,
) -> None:
    """A walk seeded with a name that is not there loses its first hop.

    The rule falls back to seeding every socket-safe module, so a mistyped entry
    point still judges the same edges and only costs the chain the module it
    starts at. That is a quiet degradation, which is the kind worth its own arm.
    """
    assert orchestration_entry_point in source_modules


def test_the_permitted_roots_are_packages_in_the_tree(
    source_modules: Mapping[str, bytes],
    socket_safe_roots: Collection[str],
) -> None:
    """A permitted root matching nothing permits nothing and reports no error."""
    roots_in_tree = {name.split(".")[0] for name in source_modules}
    assert set(socket_safe_roots) <= roots_in_tree


def test_the_boundary_has_something_on_its_other_side(
    source_modules: Mapping[str, bytes],
    socket_safe_roots: Collection[str],
) -> None:
    """Every package being permitted would leave one arm with nothing to refuse.

    The runtime arm would still bite, so the suite would stay green and the
    package arm would mean nothing. This is what goes red the day the worker is
    added to the permitted list instead of the work being moved out of it.
    """
    roots_in_tree = {name.split(".")[0] for name in source_modules}
    assert roots_in_tree - set(socket_safe_roots)


def test_the_orchestration_layer_reaches_nothing_it_may_not(
    source_modules: Mapping[str, bytes],
    source_packages: Collection[str],
    orchestration_entry_point: str,
    socket_safe_roots: Collection[str],
    forbidden_roots: Collection[str],
) -> None:
    """The boundary itself. Fails with the chain rather than with the fact."""
    chains = import_boundary_offences(
        source_modules,
        source_packages,
        orchestration_entry_point,
        socket_safe_roots,
        forbidden_roots,
    )
    assert not chains, import_boundary_message(orchestration_entry_point, chains)
