# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The network rule against sources written here, and against no repository.

Every input below is a string in this file. A rule exercised against the real
tree proves what the tree happens to hold today; what it does not prove is that
the rule would refuse the module that has not been written yet, which is the
only module it exists for.

The refused names appear here inside string literals. They are parsed and never
imported, so nothing in this file opens anything.

The near misses are the ones somebody writes. ``urllib.parse`` beside
``urllib.request`` is the pair a root match cannot tell apart. ``from urllib
import request`` is what is written once the plain import has been refused once.
A deferred import inside a function is what a component reaching for telemetry
looks like in a diff.
"""

from __future__ import annotations

import textwrap
from typing import Final

from network_rules import Reach, network_message, network_offences

_IMPORTS: Final = frozenset(
    {"socket", "ssl", "http.client", "urllib.request", "webbrowser"}
)
_CALLS: Final = frozenset({"socket.socket", "urllib.request.urlopen"})


def _source(text: str) -> bytes:
    return textwrap.dedent(text).lstrip("\n").encode()


def _offences(text: str) -> list[Reach]:
    return network_offences(_source(text), _IMPORTS, _CALLS)


def test_a_plain_import_of_a_socket_is_found() -> None:
    assert _offences("import socket\n") == [Reach(1, "socket", "imports-a-way-out")]


def test_a_submodule_import_is_found_and_reported_as_written() -> None:
    found = _offences("import http.client\n")
    assert found == [Reach(1, "http.client", "imports-a-way-out")]


def test_the_neighbouring_module_that_opens_nothing_is_left_alone() -> None:
    """The pair a root match cannot tell apart. ``urllib.parse`` splits a string
    and is used in two modules here; refusing it for what ``urllib.request``
    does is a rule that has to be worked around on the day it lands."""
    assert _offences("from urllib.parse import urlsplit\n") == []


def test_the_module_beside_it_that_does_open_something_is_found() -> None:
    found = _offences("from urllib.request import urlopen\n")
    assert found == [Reach(1, "urllib.request.urlopen", "imports-a-way-out")]


def test_the_spelling_written_after_a_refusal_is_found() -> None:
    """The near miss. ``from urllib import request`` names ``urllib`` as its
    module, so a rule reading only that would let it through while it binds
    exactly the same object."""
    found = _offences("from urllib import request\n")
    assert found == [Reach(1, "urllib.request", "imports-a-way-out")]


def test_a_from_import_of_a_harmless_neighbour_under_the_same_root_is_left_alone() -> (
    None
):
    assert _offences("from urllib import parse\n") == []


def test_an_import_deferred_into_a_function_is_found() -> None:
    """The other near miss. A module-level import is visible at the top of the
    file in a diff; the same import inside the function that wanted it reads as
    a local decision, and it opens the same socket."""
    found = _offences("""
    def report(job_id: str) -> None:
        import urllib.request

        urllib.request.urlopen("https://example.invalid/" + job_id)
    """)
    assert found == [
        Reach(2, "urllib.request", "imports-a-way-out"),
        Reach(4, "urllib.request.urlopen", "opens-a-connection"),
    ]


def test_a_relative_import_is_not_resolved() -> None:
    """A relative import cannot reach a top-level module, so there is nothing
    for this rule to decide about one."""
    assert _offences("from . import socket\n") == []


def test_a_call_is_found_on_its_dotted_name() -> None:
    found = _offences("import socket\n\nsocket.socket()\n")
    assert found == [
        Reach(1, "socket", "imports-a-way-out"),
        Reach(3, "socket.socket", "opens-a-connection"),
    ]


def test_a_call_through_a_chain_that_starts_with_a_call_is_not_matched() -> None:
    """A partial name is what a rule matches by accident, so a chain whose head
    is a call resolves to no dotted name at all."""
    assert _offences("open(path).write('x')\n") == []


def test_a_name_that_merely_starts_with_a_refused_one_is_left_alone() -> None:
    """``socketserver`` is not ``socket``, and a prefix match written without
    the separator would refuse it."""
    assert _offences("import socketserver\n") == []


def test_every_place_is_reported_and_not_only_the_first() -> None:
    found = _offences("""
    import socket
    import ssl
    """)
    assert [offence.written for offence in found] == ["socket", "ssl"]


def test_one_line_binding_the_same_module_twice_is_reported_once() -> None:
    """Two aliases for one module on one line are one place, not two, and a
    reader handed the same line twice stops reading the list."""
    found = _offences("from urllib import request as a, request as b\n")
    assert found == [Reach(1, "urllib.request", "imports-a-way-out")]


def test_the_message_names_the_module_the_line_and_what_was_written() -> None:
    message = network_message(
        {"src/retusche/api/surface.py": [Reach(9, "socket", "imports-a-way-out")]},
        "retusche.models.fetch",
        {"imports-a-way-out": "a second route off this machine"},
    )
    assert "src/retusche/api/surface.py:9: socket (imports-a-way-out)" in message
    assert "retusche.models.fetch" in message
    assert "a second route off this machine" in message
