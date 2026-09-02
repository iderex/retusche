"""Resolve every external link this repository's documentation names.

A document here argues by pointing somewhere. `tests/documentation_rules.py`
already refuses a pointer at a path this tree does not hold; a pointer at
somebody else's server cannot be judged that way, because deciding it means
reaching the network, and nothing on the pull-request path does that. So this is
the other half, and `.github/workflows/external-links.yml` runs it on a schedule
rather than on a change.

Off the change path on purpose. A link check that ran on a pull request would
refuse a merge for somebody else's outage, and the merge it refuses has nothing
to do with the link. On a schedule the same failure is a message about the
document instead of a gate in front of unrelated work.

Written in Python rather than as a shell pipeline for the reason
`.github/scripts/code_scanning_gate.py` gives: the classification is the part
that has to be right, and this is the language this repository already reads,
formats and lints. The standard library carries all of it, so the run needs the
interpreter and nothing resolved from the lock file.

    python .github/scripts/external_links.py

The command takes no argument, and that is deliberate rather than an omission.
The gate beside it was refused by `py/path-injection` for taking a path from
`sys.argv`, and a step whose verdict a person reads is a poor place to accept
input from whoever calls it. Every path this reads is derived from the location
of this file.

What it does not see, so a green run is not read as more than it is:

- whether a page that answers still says what the document claims about it. A
  200 from a rewritten page is green here
- a fragment. A URL ending in `#section` is resolved to the page and the anchor
  is never looked for, so a renamed heading is a live link
- a URL split across a line break, or written as a reference-style link
  definition somewhere the literal does not appear
- a URL a document writes as a template, and a host reserved for documentation.
  Both are skipped rather than resolved, and each says below why
- a host that answers this runner and refuses another, or the other way round.
  What is measured is one machine's reach at one moment
- anything that is not markdown. A URL in a docstring, in a comment or in a
  workflow file is not read here

Exit 0 means every link answered. Exit 1 means one did not, or that the run
could not judge: a missing declaration and an unreadable document both mean
nothing was judged, and the one verdict that must never come out of that is a
pass.
"""

from __future__ import annotations

import re
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Final, NamedTuple

REPO_ROOT: Final = Path(__file__).resolve().parent.parent.parent
"""The checkout this file sits in, two directories up from `.github/scripts/`."""

PROJECT_FILE: Final = REPO_ROOT / "pyproject.toml"

TIMEOUT_SECONDS: Final = 20
"""Per attempt rather than per URL. A URL gets at most two attempts."""

USER_AGENT: Final = "retusche-external-links (+https://github.com/iderex/retusche)"
"""Sent because the default one is refused by hosts that serve a browser fine,
and a refusal that is about the agent string is a false red on a live link."""

_URL = re.compile(rb"https?://[^\s<>)\]]+")
"""An external link, matched as a run of characters that cannot close one.

The excluded set is what wraps a URL in this tree's prose: whitespace, angle
brackets for an autolink, a closing parenthesis for a markdown link target and a
closing bracket for a label. Quotes and backticks are not excluded here because
they cannot open a URL either; they are stripped from the right instead, with
the sentence punctuation below.

Only `http` and `https` are matched, which is what makes the fetch below safe to
call on the result: there is no path from a document to a `file:` read or an
`ftp:` fetch.
"""

_TRAILING: Final = ".,;:!?\"'`"
"""Stripped from the right of a match. Sentence punctuation a URL collects at
the end of a clause, and the quote or backtick a document wraps it in. No host
this tree names ends a path in one of these."""

_RETRY_ON: Final = frozenset({401, 403, 405, 429, 501})
"""Statuses that say something about the request rather than about the page. A
HEAD is cheap and widely refused, so each of these is asked again as a GET
before the link is called dead."""

_TEMPLATE: Final = "$"
"""What separates a URL a reader can follow from one a command builds.

`docs/legal/transparency.md` names `.../resource/celex/$c` inside a shell loop
and prints the three 404s that loop produced. Resolving the literal would refuse
that page for recording a measured negative, and the address as written is not
one anybody can open. So a match carrying a shell expansion is a template rather
than a link. A URL inside an indented command block is otherwise judged like any
other: it is still an address a reader will follow."""


class Site(NamedTuple):
    """One place a URL is written."""

    document: str
    line: int


class Failure(NamedTuple):
    """One link that did not answer, and where it is written."""

    url: str
    reason: str
    site: Site


def _say(line: str) -> None:
    sys.stdout.write(f"{line}\n")


class Declaration(NamedTuple):
    """What the project file says about this walk, read once.

    Two tables rather than one. The walk is the reference rule's, read from
    where that rule reads it so the two cannot come to judge different sets of
    documents. The reserved hosts are this gate's own, because no other rule has
    a use for them.
    """

    walk: dict[str, Any]
    reserved_hosts: tuple[str, ...]


def _declaration() -> Declaration:
    with PROJECT_FILE.open("rb") as handle:
        config: dict[str, Any] = tomllib.load(handle)
    tool: dict[str, Any] = config["tool"]["retusche"]
    hosts: list[str] = tool["external-links"]["reserved-hosts"]
    return Declaration(tool["documentation-references"], tuple(hosts))


def _skipped(parts: tuple[str, ...], declaration: dict[str, Any]) -> bool:
    resolved: list[str] = declaration["resolved-dot-directories"]
    skipped: list[str] = declaration["skipped-directories"]
    return any(
        (part.startswith(".") and part not in resolved) or part in skipped
        for part in parts
    )


def documents(root: Path, declaration: dict[str, Any]) -> list[Path]:
    """Every markdown file the declaration's walk reaches, sorted.

    The same walk the reference rule uses, reading the same two lists, so the
    population this judges and the population that one judges cannot drift
    apart. A dot directory is skipped unless the declaration names it, which is
    what keeps `.venv/` out of the answer on a machine that has one.
    """
    found: list[Path] = []
    pending = [root]
    while pending:
        for path in sorted(pending.pop().iterdir()):
            if _skipped(path.relative_to(root).parts, declaration):
                continue
            if path.is_dir():
                pending.append(path)
            elif path.suffix == ".md":
                found.append(path)
    return sorted(found)


def urls_in(source: bytes) -> dict[str, int]:
    """Every external URL in one document, with the line it is first written on.

    Bytes rather than text, for the reason every rule in this tree reads bytes:
    what a document holds is what git stored, and decoding the whole file first
    makes the rule depend on a decoding that could fail on the file it is meant
    to judge.
    """
    found: dict[str, int] = {}
    for number, line in enumerate(source.splitlines(), start=1):
        for match in _URL.finditer(line):
            url = match.group().decode("utf-8", "replace").rstrip(_TRAILING)
            found.setdefault(url, number)
    return found


def _attempt(url: str, method: str) -> str | None:
    """Why this attempt failed, or nothing if the link answered."""
    request = urllib.request.Request(  # noqa: S310  # _URL matches http and https only
        url, method=method, headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(  # noqa: S310  # the request above carries the scheme
            request, timeout=TIMEOUT_SECONDS
        ) as response:
            status = int(response.status)
    except urllib.error.HTTPError as problem:
        return f"HTTP {problem.code}"
    except (urllib.error.URLError, OSError, ValueError) as problem:
        return f"{type(problem).__name__}: {problem}"
    if status >= 400:
        return f"HTTP {status}"
    return None


def skip_reason(url: str, reserved_hosts: tuple[str, ...]) -> str | None:
    """Why this URL is not asked, or nothing if it is a link to resolve.

    Skipped rather than silently dropped. Both kinds are printed by the run, so
    a document that quietly stopped naming a real address does not read like a
    tree with one fewer link in it.
    """
    if _TEMPLATE in url:
        return "a template, not an address"
    host = urllib.parse.urlsplit(url).hostname or ""
    if any(host == name or host.endswith(f".{name}") for name in reserved_hosts):
        return f"reserved for documentation ({host})"
    return None


def resolve(url: str) -> str | None:
    """Why a link is dead, or nothing.

    HEAD first because it costs the host least, then GET where the refusal was
    about the method or the client rather than about the page. A link called
    dead here has refused both.
    """
    reason = _attempt(url, "HEAD")
    if reason is None:
        return None
    if reason in {f"HTTP {status}" for status in _RETRY_ON}:
        return _attempt(url, "GET")
    return reason


def sites_in(root: Path, declaration: dict[str, Any]) -> dict[str, Site]:
    """Every external URL under `root`, against the first place it is written.

    One entry per URL rather than one per occurrence: the same link in four
    documents is one host to ask and one line to read, and the site kept is the
    first in the walk order so the report is stable between runs.
    """
    sites: dict[str, Site] = {}
    for document in documents(root, declaration):
        name = document.relative_to(root).as_posix()
        for url, line in urls_in(document.read_bytes()).items():
            sites.setdefault(url, Site(name, line))
    return sites


def verdict(root: Path) -> int:
    """Walk, extract, resolve, and say what happened to every link.

    Given the root rather than reading `REPO_ROOT` itself, so a driver can hand
    it a directory of its own. `main` is the only caller that supplies the
    constant.
    """
    try:
        declaration = _declaration()
    except (OSError, ValueError, KeyError) as problem:
        _say(
            f"::error::{PROJECT_FILE} does not declare the documentation walk "
            f"({problem}). Nothing was judged, so this fails closed."
        )
        return 1

    try:
        sites = sites_in(root, declaration.walk)
    except OSError as problem:
        _say(f"::error::A document could not be read ({problem}). Failing closed.")
        return 1

    skipped = {
        url: reason
        for url in sites
        if (reason := skip_reason(url, declaration.reserved_hosts)) is not None
    }
    asked = {url: site for url, site in sorted(sites.items()) if url not in skipped}

    _say(f"External links the documentation names: {len(sites)}.")
    _say(f"Not asked: {len(skipped)}.")
    for url, reason in sorted(skipped.items()):
        _say(f"\t{sites[url].document}:{sites[url].line}\t{reason}\t{url}")
    _say(f"Asked: {len(asked)}.")
    for url, site in asked.items():
        _say(f"\t{site.document}:{site.line}\t{url}")

    failures = [
        Failure(url, reason, site)
        for url, site in asked.items()
        if (reason := resolve(url)) is not None
    ]

    if failures:
        _say(
            "::error::A link above did not answer. Each line below is the "
            "document, the line, the reason and the URL."
        )
        for failure in failures:
            _say(
                f"\t{failure.site.document}:{failure.site.line}"
                f"\t{failure.reason}\t{failure.url}"
            )
        return 1

    _say(
        f"All {len(asked)} answered. The docstring says what that does not "
        f"establish, and the {len(skipped)} above it were never asked."
    )
    return 0


def main() -> int:
    """The workflow's entry point. Reads the checkout this file sits in."""
    return verdict(REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
