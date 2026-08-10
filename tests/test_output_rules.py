# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The output rule against sources written here, and against no repository.

Every input below is a string in this file. A rule exercised against the real
tree proves what the tree happens to hold today; what it does not prove is that
the rule would refuse the file that has not been written yet, which is the only
file it exists for.

The refused names appear here inside string literals. They are parsed and never
imported, so nothing in this file reaches a logger or writes anything.
"""

from __future__ import annotations

import textwrap

from output_rules import Offence, output_message, output_offences

_IMPORTS = frozenset({"logging"})
_CALLS = frozenset({"sys.stdout.write", "sys.stderr.write"})


def _source(text: str) -> bytes:
    return textwrap.dedent(text).lstrip("\n").encode()


def test_a_plain_import_of_the_logger_is_found() -> None:
    found = output_offences(_source("import logging\n"), _IMPORTS, _CALLS)
    assert found == [Offence(1, "logging", "imports-a-logger")]


def test_a_from_import_of_the_logger_is_found() -> None:
    found = output_offences(
        _source("from logging import getLogger\n"), _IMPORTS, _CALLS
    )
    assert found == [Offence(1, "logging", "imports-a-logger")]


def test_a_submodule_import_is_found_and_reported_as_written() -> None:
    found = output_offences(_source("import logging.handlers\n"), _IMPORTS, _CALLS)
    assert found == [Offence(1, "logging.handlers", "imports-a-logger")]


def test_an_import_deferred_into_a_function_is_found() -> None:
    """The near miss. A module-level import is visible in a diff at the top of
    the file; the same import inside the function that wanted it reads as a local
    decision, and it loads the same framework."""
    found = output_offences(
        _source("""
        def report(job_id: str) -> None:
            import logging

            logging.getLogger(__name__).info("job %s", job_id)
        """),
        _IMPORTS,
        _CALLS,
    )
    assert found == [Offence(2, "logging", "imports-a-logger")]


def test_a_write_to_standard_output_is_found() -> None:
    """The line somebody writes after `print` has been refused once. ruff's T20
    matches the name `print` and this is not that name."""
    found = output_offences(
        _source("""
        import sys


        def report(job_id: str) -> None:
            sys.stdout.write(f"job {job_id} finished\\n")
        """),
        _IMPORTS,
        _CALLS,
    )
    assert found == [Offence(5, "sys.stdout.write", "writes-directly")]


def test_a_write_to_standard_error_is_found() -> None:
    found = output_offences(
        _source("""
        import sys


        def report() -> None:
            sys.stderr.write("something went wrong\\n")
        """),
        _IMPORTS,
        _CALLS,
    )
    assert found == [Offence(5, "sys.stderr.write", "writes-directly")]


def test_a_write_inside_an_error_path_is_found() -> None:
    """The write that matters most, because it runs when something has already
    gone wrong and is the one a reader of a healthy run never sees."""
    found = output_offences(
        _source("""
        import sys


        def run() -> None:
            try:
                work()
            except OSError:
                sys.stderr.write("giving up\\n")
                raise
        """),
        _IMPORTS,
        _CALLS,
    )
    assert found == [Offence(8, "sys.stderr.write", "writes-directly")]


def test_a_write_to_a_file_is_not_found() -> None:
    """The other direction of the same one-character mistake. A rule matching on
    the attribute `write` alone would refuse every file this service writes,
    starting with the result of the job it was asked to do."""
    assert (
        output_offences(
            _source("""
            def store(path, data) -> None:
                with path.open("wb") as handle:
                    handle.write(data)
            """),
            _IMPORTS,
            _CALLS,
        )
        == []
    )


def test_a_call_in_the_middle_of_the_chain_resolves_to_no_name() -> None:
    """``open(path).write`` has no dotted name, and reading one out of a partial
    chain is how a rule matches something it was never pointed at."""
    assert (
        output_offences(
            _source("""
            def store(path, data) -> None:
                open(path, "wb").write(data)
            """),
            _IMPORTS,
            _CALLS,
        )
        == []
    )


def test_the_declaration_itself_is_not_matched_by_its_own_name() -> None:
    """`retusche.logging` shares its last part with the standard library module
    and is the thing every other module is required to reach for. A rule matching
    on the written name rather than on the root would refuse the import it exists
    to require."""
    assert (
        output_offences(
            _source("""
            from retusche.logging.records import record


            def report() -> None:
                record("job.finished", "info")
            """),
            _IMPORTS,
            _CALLS,
        )
        == []
    )


def test_a_relative_import_is_not_found() -> None:
    assert (
        output_offences(_source("from .logging import record\n"), _IMPORTS, _CALLS)
        == []
    )


def test_a_module_whose_root_merely_starts_with_a_refused_one_is_not_found() -> None:
    assert output_offences(_source("import loggingish\n"), _IMPORTS, _CALLS) == []


def test_a_reference_that_is_not_a_call_is_not_found() -> None:
    """Naming ``sys.stdout`` is not writing to it. A rule that refused the name
    would refuse a module deciding whether the process has a terminal."""
    assert (
        output_offences(
            _source("""
            import sys


            def interactive() -> bool:
                return sys.stdout.isatty()
            """),
            _IMPORTS,
            _CALLS,
        )
        == []
    )


def test_every_offence_in_one_file_is_reported_in_line_order() -> None:
    found = output_offences(
        _source("""
        import logging
        import sys


        def report() -> None:
            sys.stdout.write("a")
            sys.stderr.write("b")
        """),
        _IMPORTS,
        _CALLS,
    )
    assert found == [
        Offence(1, "logging", "imports-a-logger"),
        Offence(6, "sys.stdout.write", "writes-directly"),
        Offence(7, "sys.stderr.write", "writes-directly"),
    ]


def test_a_clean_module_offends_nothing() -> None:
    assert (
        output_offences(
            _source("""
            from retusche.logging.records import record


            def report(job_id: str) -> None:
                record("job.finished", "info", job_id=job_id)
            """),
            _IMPORTS,
            _CALLS,
        )
        == []
    )


def test_the_message_names_the_place_and_the_failure_each_invariant_prevents() -> None:
    """The reason travels with the refusal. A reader meeting this has to be able
    to tell whether the rule is right about their line, and a bare verdict makes
    that a search through the project file."""
    message = output_message(
        {
            "src/retusche/queue/store.py": [
                Offence(12, "logging", "imports-a-logger"),
                Offence(40, "sys.stderr.write", "writes-directly"),
            ]
        },
        "retusche.logging.records",
        {
            "imports-a-logger": "a second way to write a line",
            "writes-directly": "a line that never passes the field check",
        },
    )
    assert "src/retusche/queue/store.py:12: logging (imports-a-logger)" in message
    assert (
        "src/retusche/queue/store.py:40: sys.stderr.write (writes-directly)" in message
    )
    assert "retusche.logging.records" in message
    assert "2 place(s)" in message
    assert "a second way to write a line" in message
    assert "a line that never passes the field check" in message
