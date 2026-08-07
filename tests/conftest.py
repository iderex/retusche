"""Where the harness rules meet this repository.

The rules themselves are in ``harness_rules``, with no pytest and no tree in
them. What is here is the wiring: read the project file, read ``src/``, hand both
to a rule, and turn what comes back into a refusal or into a line the run prints.

Two rules, and both fail closed.

The first is a discovery rule. A test that imports a machine-learning runtime is
not a unit test, and it is refused while the file is still bytes on disk, so
nothing forbidden is imported on the way to the refusal.

The second is a disclosure rule. Coverage measures the orchestration packages and
not the worker, so the run prints what it did not measure and why, and refuses to
start when a package under ``src/`` is in neither list.

Both read ``pyproject.toml``. The forbidden module roots and the exclusion
reasons are data in one place, so a second rule wanting the same list reads the
list rather than a copy of it.

The fixtures at the bottom are the same wiring for a rule that is a test rather
than a hook. ``test_import_boundary`` walks the import graph of the
orchestration packages, and what it needs is the tree and the project file,
which is what this module already knows how to read.
"""

from __future__ import annotations

import tomllib
from pathlib import Path, PurePosixPath
from typing import Any, Final

import pytest
from harness_rules import (
    coverage_scope_lines,
    coverage_scope_problems,
    forbidden_import_message,
    module_level_forbidden_imports,
)

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent
_PROJECT_FILE: Final = _REPO_ROOT / "pyproject.toml"
_SOURCE_ROOT: Final = _REPO_ROOT / "src"


def _project_config() -> dict[str, Any]:
    """The project file, parsed. Read per call rather than cached at import.

    The file is small and a run reads it a handful of times. A cache here would
    mean a rule edited during a session is judged by whatever copy the first
    import happened to see.
    """
    with _PROJECT_FILE.open("rb") as handle:
        return tomllib.load(handle)


def _forbidden_roots() -> frozenset[str]:
    config = _project_config()
    roots: list[str] = config["tool"]["retusche"]["import-boundary"]["forbidden-roots"]
    return frozenset(roots)


def _measured_packages() -> frozenset[str]:
    source: list[str] = _project_config()["tool"]["coverage"]["run"]["source"]
    return frozenset(PurePosixPath(entry).name for entry in source)


def _declared_exclusions() -> dict[str, str]:
    exclusions: dict[str, str] = _project_config()["tool"]["retusche"][
        "coverage-exclusions"
    ]
    return exclusions


def _packages_in_tree() -> frozenset[str]:
    return frozenset(
        entry.name
        for entry in _SOURCE_ROOT.iterdir()
        if (entry / "__init__.py").is_file()
    )


def _module_name(path: Path) -> str:
    """The dotted name ``src/a/b/c.py`` is imported under, and ``a.b`` for a package."""
    relative = path.relative_to(_SOURCE_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


@pytest.fixture(scope="session")
def source_modules() -> dict[str, bytes]:
    """Every module under ``src/``, keyed by the name an import statement uses.

    Read off the tree rather than out of a list, so a module added tomorrow is
    walked without anyone remembering to register it.
    """
    return {
        _module_name(path): path.read_bytes()
        for path in sorted(_SOURCE_ROOT.rglob("*.py"))
    }


@pytest.fixture(scope="session")
def source_packages() -> frozenset[str]:
    """The dotted names under ``src/`` that are packages rather than modules.

    A relative import resolves differently inside ``__init__.py`` than inside a
    module beside it, so the walk has to be told which is which.
    """
    return frozenset(_module_name(path) for path in _SOURCE_ROOT.rglob("__init__.py"))


@pytest.fixture(scope="session")
def forbidden_roots() -> frozenset[str]:
    """The module roots that stand for a machine-learning runtime."""
    return _forbidden_roots()


@pytest.fixture(scope="session")
def socket_safe_roots() -> frozenset[str]:
    """The project packages permitted in the process that listens on a socket."""
    roots: list[str] = _project_config()["tool"]["retusche"]["import-boundary"][
        "socket-safe-roots"
    ]
    return frozenset(roots)


@pytest.fixture(scope="session")
def orchestration_entry_point() -> str:
    """The module an offending import chain is reported from."""
    entry: str = _project_config()["tool"]["retusche"]["import-boundary"]["entry-point"]
    return entry


def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> None:
    """Refuse a test file that reaches for the runtime, before it is imported.

    Raised as a usage error rather than reported as a failing test. A failing
    test would have to be imported first, which is the thing being refused.
    """
    del parent  # The rule is about the file, not about where it sits.
    if file_path.suffix != ".py":
        return
    offences = module_level_forbidden_imports(
        file_path.read_bytes(), _forbidden_roots(), filename=str(file_path)
    )
    if offences:
        raise pytest.UsageError(forbidden_import_message(str(file_path), offences))


def pytest_configure(config: pytest.Config) -> None:
    """Refuse to start when a package under ``src/`` has had no decision made."""
    del config
    problems = coverage_scope_problems(
        _packages_in_tree(), _measured_packages(), _declared_exclusions()
    )
    if problems:
        raise pytest.UsageError(" ".join(problems))


def pytest_terminal_summary(
    terminalreporter: Any,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Print what coverage measured and what it did not, with the reason."""
    del exitstatus, config
    terminalreporter.write_sep("-", "coverage scope")
    for line in coverage_scope_lines(_measured_packages(), _declared_exclusions()):
        terminalreporter.write_line(line)
