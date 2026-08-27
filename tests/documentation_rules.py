# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""A reference in a document names a path, and the path is there. No tree here.

The documents in this repository carry load-bearing claims: what stays on the
host, what a licence permits, what a setting does. Most of them are argued by
pointing at a file, either as a markdown link or as a backticked path in prose.
A file that moves takes every pointer at it out of date, and nothing notices,
because a document is not compiled and a stale path reads exactly like a live
one.

Two shapes are read, and they are two because they fail differently. A markdown
link is followed by a reader who clicks it and lands on a 404. A backticked path
is followed by a reader who types it and finds nothing, and it is the far more
common shape here: the documents in this tree argue by naming the module that
decides a thing.

What makes a backticked token a reference is deliberately narrow. It carries a
separator and it ends either in a declared suffix or in a separator, so
``i/crlf``, which is a column of ``git ls-files --eol`` output, and
``unicode-guard.yml``, which is a bare filename, are both left alone. Widening
either half refuses the documents that explain those two commands, which is the
failure this narrowness is chosen against rather than an accident of it.

Whether a path exists is the caller's business and arrives as ``exists``. The
rule has no repository in it, the same way ``output_rules`` and ``harness_rules``
have none, so every offence below is produced from bytes and a predicate and can
be asked about a source the suite writes.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping

__all__ = [
    "Reference",
    "reference_message",
    "reference_offences",
    "references",
    "stale_exemptions",
]

# A markdown inline link or image target. The target stops at the first closing
# parenthesis, which is what markdown itself does for an unbracketed target, so
# a sentence's own parenthesis after the link is not swallowed.
_LINK = re.compile(r"\]\(([^)\s]+)")

# A backticked span. Newlines are excluded so an unclosed backtick cannot pair
# with one further down the document and swallow the paragraph between them.
_CODE = re.compile(r"`([^`\n]+)`")

# A target this rule does not resolve: an absolute URL, a protocol-relative one,
# a mail address, or an anchor into the page itself.
_NOT_A_PATH = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", re.IGNORECASE)


class Reference(NamedTuple):
    """One place a document names a path."""

    line: int
    target: str
    kind: str


def _targets(line: str) -> list[tuple[str, str]]:
    return [(target, "link") for target in _LINK.findall(line)] + [
        (token.strip(), "path") for token in _CODE.findall(line)
    ]


def _is_reference(target: str, kind: str, suffixes: Collection[str]) -> bool:
    if kind == "link":
        return not _NOT_A_PATH.match(target)
    if "/" not in target:
        return False
    return target.endswith(("/", *suffixes))


def _resolvable(target: str) -> str:
    """The part of a target a path can be looked up by.

    A fragment addresses a heading inside the file and a query string addresses
    nothing on a filesystem at all; both are cut before the lookup, because a
    link to a real file with a fragment is a live link and refusing it would
    make the check refuse the correct thing.
    """
    return target.split("#", 1)[0].split("?", 1)[0]


def references(source: bytes, suffixes: Collection[str]) -> list[Reference]:
    """Every reference the document makes, in line order.

    The whole document is read, indented blocks included. A command quoted in a
    block names paths at the moment it was run, so this is a place the rule can
    be wrong about intent; no such command in this tree carries a backtick or a
    markdown link, which is what keeps the two apart today rather than anything
    in the syntax.
    """
    found: list[Reference] = []
    for number, line in enumerate(source.decode("utf-8").splitlines(), start=1):
        for target, kind in _targets(line):
            if _is_reference(target, kind, suffixes):
                found.append(Reference(number, target, kind))
    return found


def reference_offences(
    source: bytes,
    exists: Callable[[str], bool],
    suffixes: Collection[str],
    exempt: Collection[str],
) -> list[Reference]:
    """Every reference naming a path that is not there and is not declared."""
    return [
        reference
        for reference in references(source, suffixes)
        if reference.target not in exempt and not exists(_resolvable(reference.target))
    ]


def reference_message(offences: Mapping[str, Collection[Reference]]) -> str:
    """What a reader is told, naming the document, the line and the target."""
    lines = [
        "a document names a path that is not in this tree:",
        "",
    ]
    for filename in sorted(offences):
        for reference in sorted(offences[filename]):
            lines.append(f"  {filename}:{reference.line}: {reference.target}")
    lines += [
        "",
        "Either the path moved and the document did not, or the reference is",
        "to a path that is deliberately absent. The second one is an entry in",
        "[tool.retusche.documentation-references.exempt] carrying the reason,",
        "and an entry there is refused once the path arrives.",
    ]
    return "\n".join(lines)


def stale_exemptions(
    exempt: Mapping[str, str],
    exists: Callable[[str], bool],
    cited: Collection[str],
) -> dict[str, str]:
    """Every declared exemption that has stopped being one, with what is wrong.

    The register fails closed in both directions. An exemption whose path has
    since arrived is a reference nothing checks any more, and an exemption no
    document makes is a sentence that outlived the document it was written for.
    Neither is caught by the walk above: an exemption only ever removes work
    from it.
    """
    stale: dict[str, str] = {}
    for target, reason in exempt.items():
        if exists(_resolvable(target)):
            stale[target] = "the path exists now, so nothing is being excused"
        elif target not in cited:
            stale[target] = "no document names it, so the entry excuses nothing"
        elif not reason.strip():
            stale[target] = "the entry carries no reason"
    return stale
