# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The reference rule against documents written here, and against no repository.

Every input below is a string in this file and every path it resolves against is
a set in this file. A rule exercised against the real tree proves what the tree
happens to hold today; what it does not prove is that the rule would refuse the
document that has not been written yet, which is the only document it exists for.

The near misses are the ones somebody writes rather than the obvious ones. A
module renamed from ``records.py`` to ``record.py``, and a document that kept the
old spelling, is one character, and it is what a rename leaves behind. A link
whose file moved one directory is the other.
"""

from __future__ import annotations

import textwrap
from typing import Final

from documentation_rules import (
    Reference,
    reference_message,
    reference_offences,
    references,
    stale_exemptions,
)

_SUFFIXES: Final = frozenset({".md", ".py", ".yml", ".toml"})

#: What this small tree holds. A directory carries the trailing separator, the
#: same shape the walk in ``test_documentation_references`` produces.
_HELD: Final = frozenset(
    {
        "README.md",
        "docs/",
        "docs/logging.md",
        "src/",
        "src/retusche/",
        "src/retusche/logging/",
        "src/retusche/logging/records.py",
        ".github/",
        ".github/workflows/",
        ".github/workflows/pull-request.yml",
    }
)


def _exists(target: str) -> bool:
    stripped = target.rstrip("/")
    return target in _HELD or stripped in _HELD or f"{stripped}/" in _HELD


def _document(text: str) -> bytes:
    return textwrap.dedent(text).lstrip("\n").encode()


def _offences(text: str, exempt: frozenset[str] = frozenset()) -> list[Reference]:
    return reference_offences(_document(text), _exists, _SUFFIXES, exempt)


def test_a_link_to_a_file_that_is_there_is_left_alone() -> None:
    assert _offences("See [the log page](docs/logging.md) for the fields.\n") == []


def test_a_link_whose_file_moved_one_directory_is_found() -> None:
    """The near miss. The file exists, one directory over, and the link reads
    exactly like the one beside it that still resolves."""
    found = _offences("See [the log page](docs/legal/logging.md).\n")
    assert found == [Reference(1, "docs/legal/logging.md", "link")]


def test_a_backticked_path_one_character_off_is_found() -> None:
    """The other near miss. ``records.py`` renamed to ``record.py`` leaves every
    document that named it holding a path that no longer exists, and the singular
    reads as correct to anybody who is not looking for it."""
    found = _offences("The line is built in `src/retusche/logging/record.py`.\n")
    assert found == [Reference(1, "src/retusche/logging/record.py", "path")]


def test_a_backticked_path_that_is_there_is_left_alone() -> None:
    text = "The line is built in `src/retusche/logging/records.py`.\n"
    assert _offences(text) == []


def test_a_directory_reference_resolves_to_the_directory() -> None:
    assert _offences("The workflows are under `.github/workflows/`.\n") == []


def test_a_directory_that_is_not_there_is_found() -> None:
    found = _offences("The harness lives under `tests/hardware/`.\n")
    assert found == [Reference(1, "tests/hardware/", "path")]


def test_a_fragment_is_cut_before_the_file_is_looked_for() -> None:
    """A link into a heading is a live link. Resolving the whole target would
    refuse it, which would make the rule refuse the correct thing."""
    assert _offences("See [the fields](docs/logging.md#the-fields).\n") == []


def test_a_fragment_does_not_rescue_a_file_that_is_not_there() -> None:
    found = _offences("See [the fields](docs/logs.md#the-fields).\n")
    assert found == [Reference(1, "docs/logs.md#the-fields", "link")]


def test_an_external_link_is_not_resolved() -> None:
    assert _offences("See [upstream](https://example.invalid/a.md).\n") == []


def test_an_anchor_into_the_page_itself_is_not_resolved() -> None:
    assert _offences("Back to [the top](#what-this-document-is).\n") == []


def test_a_mail_address_is_not_resolved() -> None:
    assert _offences("Write to [me](mailto:someone@example.invalid).\n") == []


def test_a_bare_filename_is_not_a_reference() -> None:
    """``unicode-guard.yml`` is how a document names a workflow in passing, and
    there are several of those. Reading a bare filename as a path is the
    widening that refuses the pages explaining the commands."""
    assert _offences("The scan is `unicode-guard.yml`, one directory down.\n") == []


def test_a_column_label_that_carries_a_separator_is_not_a_reference() -> None:
    """``i/crlf`` is a column of ``git ls-files --eol``. It carries a separator
    and no suffix, which is the half of the pair that leaves it alone."""
    assert _offences("What would be red is `i/crlf` in that first column.\n") == []


def test_an_image_target_is_read_the_same_way_as_a_link() -> None:
    found = _offences("![the shape](docs/shape.md)\n")
    assert found == [Reference(1, "docs/shape.md", "link")]


def test_a_declared_exemption_is_not_an_offence() -> None:
    text = "It creates `.venv/` from the lock file and installs this project.\n"
    assert _offences(text) != []
    assert _offences(text, frozenset({".venv/"})) == []


def test_the_line_reported_is_the_line_the_reference_is_on() -> None:
    found = _offences("""
    One.

    Two, in `docs/absent.md`.
    """)
    assert found == [Reference(3, "docs/absent.md", "path")]


def test_every_reference_is_reported_and_not_only_the_first() -> None:
    found = _offences("`docs/absent.md` and [another](docs/gone.md) on one line.\n")
    assert [reference.target for reference in found] == [
        "docs/gone.md",
        "docs/absent.md",
    ]


def test_an_unclosed_backtick_does_not_swallow_the_paragraph() -> None:
    """A stray backtick pairing with one further down would make every path
    between them invisible, which is a rule that quietly stops judging."""
    found = references(
        _document("""
        A stray ` here.

        And `src/retusche/logging/record.py` below.
        """),
        _SUFFIXES,
    )
    assert [reference.target for reference in found] == [
        "src/retusche/logging/record.py"
    ]


def test_the_message_names_the_document_the_line_and_the_target() -> None:
    message = reference_message(
        {"docs/logging.md": [Reference(12, "src/retusche/logging/record.py", "path")]}
    )
    assert "docs/logging.md:12: src/retusche/logging/record.py" in message
    assert "documentation-references.exempt" in message


def test_an_exemption_whose_path_has_arrived_is_stale() -> None:
    """The direction that matters most. A path that arrives leaves an entry
    excusing a reference that now resolves, and nothing in the walk would say
    so, because an exemption only ever removes work from it."""
    stale = stale_exemptions(
        {"docs/logging.md": "absent until #64"}, _exists, {"docs/logging.md"}
    )
    assert list(stale) == ["docs/logging.md"]
    assert "exists now" in stale["docs/logging.md"]


def test_an_exemption_no_document_makes_is_stale() -> None:
    stale = stale_exemptions({"docs/absent.md": "a reason"}, _exists, set())
    assert list(stale) == ["docs/absent.md"]
    assert "no document names it" in stale["docs/absent.md"]


def test_an_exemption_without_a_reason_is_stale() -> None:
    stale = stale_exemptions({"docs/absent.md": "  "}, _exists, {"docs/absent.md"})
    assert list(stale) == ["docs/absent.md"]
    assert "no reason" in stale["docs/absent.md"]


def test_a_live_exemption_is_not_reported() -> None:
    stale = stale_exemptions(
        {"docs/absent.md": "delivered by #61"}, _exists, {"docs/absent.md"}
    )
    assert stale == {}
