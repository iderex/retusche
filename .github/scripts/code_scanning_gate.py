"""Turn a CodeQL SARIF file into a verdict.

The CodeQL action reports and does not refuse: it writes findings and exits
zero, so a check that only runs it is green on a tree full of them. This is the
step that refuses, and `.github/workflows/code-scanning.yml` is its only caller.

A result is actionable when its rule carries the `security` tag, at any
severity, and `docs/code-scanning.md` argues why that is the line here rather
than a severity threshold. A result whose rule cannot be found in the SARIF is
actionable too: its tags cannot be read, so it cannot be shown to be harmless.

Every path that cannot judge exits non-zero rather than zero. A missing file, a
file that is not JSON, and a document holding no analysis run all mean the same
thing, which is that nothing was judged, and the one verdict that must never
come out of that is a pass.

Written in Python rather than in a shell pipeline because the classification is
the part that has to be right, and this is the language the repository already
reads, formats and types. `verdict` takes a path and prints its result, so it
runs against a fixture on a workstation exactly as it runs on a runner.

    python .github/scripts/code_scanning_gate.py

The command takes no argument and `SARIF` below is the only path it reads. It
was written taking one, and the first analysis this gate ever completed refused
this file for it: `py/path-injection` twice, at the two lines where a value from
`sys.argv` reached the filesystem, in run 31302655661. Under the `local` threat
model a command-line argument is untrusted, and the step that decides whether a
merge is refused is a poor place to accept a path from whoever calls it. A
fixture reaches `verdict` directly instead, from a driver outside this tree, so
nothing in here turns a value chosen at run time into a file to read.

`SARIF` is the reading half of a path the analysis step writes as `output:` in
`.github/workflows/code-scanning.yml`. Two places hold it, nothing compares
them, and a change to either is a change to both.

Exit 0 means nothing actionable was found. Exit 1 means something was, or that
the file could not be judged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Final

SECURITY = "security"
UNRESOLVED = "unresolved"
OTHER = "other"
ACTIONABLE = frozenset({SECURITY, UNRESOLVED})

SARIF: Final = Path("sarif-results") / "python.sarif"
"""Where the analysis step writes what this reads, relative to the checkout."""


def _say(line: str) -> None:
    sys.stdout.write(f"{line}\n")


def _rules_of(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Rule metadata by id, from the driver and from any query pack.

    CodeQL writes the rules beside the results rather than inside them, in
    `tool.driver.rules`, and a query pack contributes its own under
    `tool.extensions`. Reading only the first place is how a finding from an
    extended query set arrives with no tags and is quietly taken for harmless.
    """
    tool = run.get("tool") or {}
    driver = tool.get("driver") or {}
    collected: list[Any] = list(driver.get("rules") or [])
    for extension in tool.get("extensions") or []:
        collected.extend(extension.get("rules") or [])
    return {
        rule["id"]: rule
        for rule in collected
        if isinstance(rule, dict) and isinstance(rule.get("id"), str)
    }


def _where(result: dict[str, Any]) -> str:
    locations = result.get("locations") or []
    if not locations:
        return "?"
    physical = (locations[0] or {}).get("physicalLocation") or {}
    artifact = physical.get("artifactLocation") or {}
    region = physical.get("region") or {}
    return f"{artifact.get('uri', '?')}:{region.get('startLine', 0)}"


def _classify(result: dict[str, Any], rules: dict[str, dict[str, Any]]) -> list[str]:
    """One row: class, rule id, security severity, location, message."""
    rule_id = result.get("ruleId")
    rule = rules.get(rule_id) if isinstance(rule_id, str) else None
    if rule is None:
        kind = UNRESOLVED
        severity = "-"
    else:
        properties = rule.get("properties") or {}
        tags = properties.get("tags") or []
        kind = SECURITY if SECURITY in tags else OTHER
        severity = str(properties.get("security-severity", "-"))
    message = ((result.get("message") or {}).get("text") or "").strip()
    return [
        kind,
        rule_id if isinstance(rule_id, str) else "?",
        severity,
        _where(result),
        " ".join(message.split()),
    ]


def judge(document: dict[str, Any]) -> list[list[str]]:
    """Every result in every run, classified."""
    rows: list[list[str]] = []
    for run in document.get("runs") or []:
        rules = _rules_of(run)
        for result in run.get("results") or []:
            rows.append(_classify(result, rules))
    return rows


def verdict(path: Path) -> int:
    """The verdict for one SARIF file, with every line it prints.

    Given the path rather than reading `SARIF` itself, because this is the
    function a fixture drives and a fixture has no `sarif-results` directory.
    `main` is what supplies the constant, and it is the only caller that does.
    """
    if not path.is_file():
        _say(
            f"::error::No SARIF at {path}, so this run judged nothing. "
            "Failing closed rather than reporting a tree nobody analysed as clean."
        )
        return 1

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        _say(f"::error::{path} could not be read as JSON ({problem}). Failing closed.")
        return 1

    if not isinstance(document, dict) or not document.get("runs"):
        _say(f"::error::{path} holds no analysis run. Failing closed.")
        return 1

    rows = judge(document)
    actionable = [row for row in rows if row[0] in ACTIONABLE]
    _say(f"CodeQL results in this tree: {len(rows)}. Actionable: {len(actionable)}.")

    if actionable:
        _say(
            "::error::Code scanning refused this tree. Each line below is class, "
            "rule, security-severity, location, message."
        )
        for row in actionable:
            _say("\t".join(row))
        return 1

    _say("No security-tagged result. docs/code-scanning.md says what that misses.")
    return 0


def main() -> int:
    """The workflow's entry point. Reads the one path this gate ever reads."""
    return verdict(SARIF)


if __name__ == "__main__":
    raise SystemExit(main())
