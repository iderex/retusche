# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What the loader accepts, what it refuses, and what it refuses all at once.

Two properties carry this file. The first is that nothing is silently ignored:
a name nothing declares is refused in every source, because the typo in a
deployment file is what this exists to catch and a typo that does nothing reads
exactly like a setting that took effect. The second is that a refusal names
every problem, so an operator with four mistakes corrects them once.

The fixture set below is a fixture set, and the tests that judge it prove the
loader. The two tests at the foot judge the set this tree actually declares, and
they prove the tree on the day they ran, which is a different and much weaker
claim.

No device, no display and no elevation is needed by anything here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from retusche.config import (
    ENVIRONMENT_PREFIX,
    REDACTED,
    SETTINGS,
    ConfigurationError,
    Kind,
    Setting,
    environment_name,
    load,
    reference_markdown,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent

_FIXTURE = (
    Setting(
        name="store_path",
        kind=Kind.PATH,
        unit="a path to a file",
        summary="Where the store is kept.",
    ),
    Setting(
        name="library_token",
        kind=Kind.SECRET,
        unit="an opaque credential",
        summary="What the library is reached with.",
    ),
    Setting(
        name="queue_depth",
        kind=Kind.INTEGER,
        unit="jobs",
        summary="How many jobs may wait.",
        default="64",
    ),
    Setting(
        name="marking_enabled",
        kind=Kind.BOOLEAN,
        unit="true or false",
        summary="Whether results are marked.",
        default="true",
    ),
    Setting(
        name="instance_name",
        kind=Kind.TEXT,
        unit="a short label",
        summary="What this deployment calls itself.",
        default="retusche",
    ),
)

_COMPLETE_FILE = """
store_path = "/srv/retusche/jobs.sqlite3"
library_token = "hunter2-and-then-some"
"""


def test_a_complete_configuration_loads_with_every_kind_read_back() -> None:
    configuration = load(file_text=_COMPLETE_FILE, settings=_FIXTURE)
    assert configuration.path("store_path") == Path("/srv/retusche/jobs.sqlite3")
    assert configuration.text("library_token") == "hunter2-and-then-some"
    assert configuration.integer("queue_depth") == 64
    assert configuration.boolean("marking_enabled") is True
    assert configuration.text("instance_name") == "retusche"


def test_a_setting_with_no_default_and_no_value_refuses_the_load() -> None:
    """Fail-closed, which is the line this issue turns on.

    There is no state in which such a setting takes a value nobody wrote.
    """
    with pytest.raises(ConfigurationError) as refusal:
        load(settings=_FIXTURE)
    message = str(refusal.value)
    assert "store_path has no value and no default" in message
    assert "library_token has no value and no default" in message
    assert "RETUSCHE_STORE_PATH" in message


def test_every_problem_is_reported_rather_than_the_first_one() -> None:
    """Four mistakes, one refusal, so a deployment is corrected once."""
    with pytest.raises(ConfigurationError) as refusal:
        load(
            file_text='store_pth = "/srv/jobs"\nqueue_depth = "many"\n',
            environment={"RETUSCHE_QUEUE_DEPTHS": "8"},
            overrides={"marking_enabld": "true"},
            settings=_FIXTURE,
        )
    message = str(refusal.value)
    assert "6 problem(s)" in message
    assert "store_pth" in message
    assert "RETUSCHE_QUEUE_DEPTHS" in message
    assert "marking_enabld" in message
    assert "queue_depth is 'many'" in message
    assert "library_token has no value" in message


@pytest.mark.parametrize(
    ("where", "arguments"),
    [
        ("the configuration file", {"file_text": 'store_pth = "/srv/jobs"\n'}),
        ("the overrides", {"overrides": {"store_pth": "/srv/jobs"}}),
    ],
)
def test_a_name_nothing_declares_is_refused_in_each_source(
    where: str, arguments: dict[str, object]
) -> None:
    with pytest.raises(ConfigurationError) as refusal:
        load(settings=_FIXTURE, **arguments)  # type: ignore[arg-type]  # the parameters are this loader's own keywords
    message = str(refusal.value)
    assert f"store_pth, in {where}," in message
    assert "queue_depth" in message


def test_a_prefixed_environment_variable_naming_no_setting_is_refused() -> None:
    with pytest.raises(ConfigurationError) as refusal:
        load(
            file_text=_COMPLETE_FILE,
            environment={"RETUSCHE_STORE_PTH": "/srv/jobs"},
            settings=_FIXTURE,
        )
    message = str(refusal.value)
    assert "RETUSCHE_STORE_PTH is set and names no setting" in message
    assert "RETUSCHE_STORE_PATH" in message


def test_an_environment_variable_outside_the_prefix_is_not_read_at_all() -> None:
    """The limit of the check above, asserted rather than left implied.

    A variable misspelled outside the prefix is invisible, and a check that read
    every variable on the host would refuse the host's own.
    """
    configuration = load(
        file_text=_COMPLETE_FILE,
        environment={"RETUSHE_STORE_PATH": "/elsewhere", "PATH": "/usr/bin"},
        settings=_FIXTURE,
    )
    assert configuration.path("store_path") == Path("/srv/retusche/jobs.sqlite3")


def test_the_environment_overrides_the_file_and_the_overrides_win() -> None:
    """The declared precedence, at the one place it can be seen."""
    from_file = load(file_text=_COMPLETE_FILE, settings=_FIXTURE)
    assert from_file.text("instance_name") == "retusche"
    from_environment = load(
        file_text=_COMPLETE_FILE + 'instance_name = "from-file"\n',
        environment={"RETUSCHE_INSTANCE_NAME": "from-environment"},
        settings=_FIXTURE,
    )
    assert from_environment.text("instance_name") == "from-environment"
    from_overrides = load(
        file_text=_COMPLETE_FILE + 'instance_name = "from-file"\n',
        environment={"RETUSCHE_INSTANCE_NAME": "from-environment"},
        overrides={"instance_name": "from-the-command-line"},
        settings=_FIXTURE,
    )
    assert from_overrides.text("instance_name") == "from-the-command-line"


def test_a_file_that_is_not_toml_is_refused_by_name_rather_than_ignored() -> None:
    with pytest.raises(ConfigurationError) as refusal:
        load(file_text="store_path = ", settings=_FIXTURE)
    assert "not readable as TOML" in str(refusal.value)


@pytest.mark.parametrize(
    ("written", "name"),
    [
        ("many", "queue_depth"),
        ("6.5", "queue_depth"),
        ("yes", "marking_enabled"),
        ("True", "marking_enabled"),
        ("12_000", "queue_depth"),
        (" 12", "queue_depth"),
    ],
)
def test_a_value_that_is_not_its_declared_kind_is_refused(
    written: str, name: str
) -> None:
    """Including the two forms `int()` would have accepted on its own.

    `int("12_000")` is twelve thousand and `int(" 12")` is twelve, so a check
    written as a bare call inside a try would read a number an operator did not
    write, in a field where the number is a limit somebody is relying on.
    """
    with pytest.raises(ConfigurationError) as refusal:
        load(file_text=_COMPLETE_FILE, overrides={name: written}, settings=_FIXTURE)
    assert f"{name} is {written!r}" in str(refusal.value)


def test_a_number_written_in_digits_that_are_not_ascii_is_refused() -> None:
    """The near miss `isdigit` alone lets through, written as code points.

    FULLWIDTH DIGIT ONE and TWO. Both satisfy `str.isdigit`, and `int()` reads
    the pair as twelve, so a check that asked only whether the characters were
    digits would accept a limit an operator did not type. The two are built from
    their code points rather than pasted, so this file stays readable as ASCII.
    """
    written = chr(0xFF11) + chr(0xFF12)
    assert written.isdigit()
    assert int(written) == 12
    with pytest.raises(ConfigurationError) as refusal:
        load(
            file_text=_COMPLETE_FILE,
            overrides={"queue_depth": written},
            settings=_FIXTURE,
        )
    assert "queue_depth is" in str(refusal.value)


def test_a_negative_whole_number_is_read_as_one() -> None:
    configuration = load(
        file_text=_COMPLETE_FILE, overrides={"queue_depth": "-4"}, settings=_FIXTURE
    )
    assert configuration.integer("queue_depth") == -4


@pytest.mark.parametrize(("written", "expected"), [("true", True), ("false", False)])
def test_a_boolean_written_as_text_is_read_in_both_directions(
    written: str, expected: bool
) -> None:
    """Both arms, because a source outside the file carries strings and not bools."""
    configuration = load(
        file_text=_COMPLETE_FILE,
        overrides={"marking_enabled": written},
        settings=_FIXTURE,
    )
    assert configuration.boolean("marking_enabled") is expected


def test_a_boolean_written_as_a_number_in_the_file_is_refused() -> None:
    """TOML carries types, so this arrives as an `int` rather than as a string."""
    with pytest.raises(ConfigurationError) as refusal:
        load(
            file_text=_COMPLETE_FILE + "marking_enabled = 1\n",
            settings=_FIXTURE,
        )
    assert "marking_enabled is 1" in str(refusal.value)


def test_an_integer_written_as_a_boolean_in_the_file_is_refused() -> None:
    """`True` is an `int` in this language, and it is not a queue depth."""
    with pytest.raises(ConfigurationError) as refusal:
        load(
            file_text=_COMPLETE_FILE + "queue_depth = true\n",
            settings=_FIXTURE,
        )
    assert "not true or false" in str(refusal.value)


def test_a_path_written_as_a_number_in_the_file_is_refused() -> None:
    with pytest.raises(ConfigurationError) as refusal:
        load(file_text="store_path = 7\nlibrary_token = 'x'\n", settings=_FIXTURE)
    assert "store_path is 7" in str(refusal.value)


def test_the_file_may_carry_the_native_types_toml_has() -> None:
    configuration = load(
        file_text=_COMPLETE_FILE + "queue_depth = 12\nmarking_enabled = false\n",
        settings=_FIXTURE,
    )
    assert configuration.integer("queue_depth") == 12
    assert configuration.boolean("marking_enabled") is False


def test_no_secret_survives_the_rendering_of_the_effective_configuration() -> None:
    """The whole rendering is searched, not the line the secret was expected on.

    A test asserting that the credential's own line reads `<redacted>` passes
    over a rendering that repeats the value in a summary underneath it.
    """
    written_credential = "hunter2-and-then-some"
    configuration = load(file_text=_COMPLETE_FILE, settings=_FIXTURE)
    rendered = configuration.effective_lines()
    assert f"library_token = {REDACTED}" in rendered
    assert written_credential not in "\n".join(rendered)
    assert f"store_path = {Path('/srv/retusche/jobs.sqlite3')}" in rendered


def test_the_rendering_carries_one_line_per_declared_setting() -> None:
    configuration = load(file_text=_COMPLETE_FILE, settings=_FIXTURE)
    rendered = configuration.effective_lines()
    assert len(rendered) == len(_FIXTURE)
    assert [line.split(" = ")[0] for line in rendered] == [
        setting.name for setting in _FIXTURE
    ]


def test_reading_a_setting_as_the_wrong_kind_is_refused_naming_both() -> None:
    configuration = load(file_text=_COMPLETE_FILE, settings=_FIXTURE)
    with pytest.raises(ConfigurationError) as refusal:
        configuration.integer("store_path")
    assert "declared as path" in str(refusal.value)
    assert "read as integer" in str(refusal.value)


def test_reading_a_setting_that_is_not_declared_is_refused() -> None:
    configuration = load(file_text=_COMPLETE_FILE, settings=_FIXTURE)
    with pytest.raises(ConfigurationError) as refusal:
        configuration.text("device")
    assert "device is not a setting this project declares" in str(refusal.value)


def test_a_secret_is_read_back_through_the_text_accessor() -> None:
    configuration = load(file_text=_COMPLETE_FILE, settings=_FIXTURE)
    assert configuration.text("library_token") == "hunter2-and-then-some"


def test_an_environment_name_is_the_prefix_and_the_name_in_upper_case() -> None:
    assert environment_name(_FIXTURE[0]) == f"{ENVIRONMENT_PREFIX}STORE_PATH"


def test_the_reference_page_carries_every_setting_and_its_environment_name() -> None:
    page = reference_markdown(_FIXTURE)
    for setting in _FIXTURE:
        assert f"### `{setting.name}`" in page
        assert setting.summary in page
        assert setting.unit in page
        assert environment_name(setting) in page
    assert "- Default: none, and the service does not start without it" in page
    assert "- Default: `64`" in page
    assert "text, and never printed" in page


def test_the_committed_reference_page_is_what_the_declaration_produces() -> None:
    """The page cannot drift, because this is the check that says so.

    It reads the file on disk. The committed copy is what a reader sees, and a
    generator that agrees with itself proves nothing about it.
    """
    committed = (_REPO_ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    assert committed == reference_markdown()


def test_every_default_this_tree_declares_parses_as_its_own_kind() -> None:
    """A default is a value, and it is written in the same form as any other."""
    without_defaults = tuple(setting for setting in SETTINGS if setting.default is None)
    with_defaults = tuple(
        setting for setting in SETTINGS if setting.default is not None
    )
    if with_defaults:
        load(settings=with_defaults)
    assert all(setting.default is None for setting in without_defaults)


def test_every_declared_setting_carries_a_unit_and_a_sentence() -> None:
    """An assertion over the set this tree declares, which is two today."""
    assert SETTINGS
    for setting in SETTINGS:
        assert setting.name == setting.name.lower()
        assert setting.unit.strip()
        assert setting.summary.strip().endswith(".")
        assert len(setting.summary) > 40
